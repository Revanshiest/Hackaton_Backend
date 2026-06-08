"""Оркестратор: Excel → ONNX-классификация → Top-10/Top-3 → LLM-справки → отчёты."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from app.aggregate import build_municipality_rankings
from app.breakdown import attach_reasons_to_rankings, build_topic_group_breakdown
from app.config.settings import PipelineSettings
from app.io_excel import load_incidents, to_inference_frame
from app.report import write_excel_report, write_report_json
from app.summary import (
    build_executive_summary,
    build_municipality_summaries,
    enrich_reasons_with_llm,
    save_summary_artifacts,
)
from pipeline.inference import run_inference
from training_utils import format_input_text

ProgressCallback = Callable[[str, str, str], None]


@dataclass(frozen=True)
class PipelineResult:
    rows_processed: int
    problem_count: int
    municipality_count: int
    report_path: Path
    elapsed_sec: float


def run_pipeline(
    cfg: PipelineSettings,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    def step(step_id: str, status: str, detail: str = "") -> None:
        if on_progress:
            on_progress(step_id, status, detail)

    t0 = time.perf_counter()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)

    step("load", "running", f"файл: {cfg.input_path.name}")
    df = load_incidents(cfg.input_path)
    if cfg.nrows:
        df = df.head(cfg.nrows).copy()
    n_muni = int(df["муниципалитет"].nunique()) if "муниципалитет" in df.columns else 0
    step("load", "done", f"загружено {len(df)} строк, {n_muni} муниципалитетов")

    step("classify", "running", "ONNX: проблема / тяжесть")
    infer_df = to_inference_frame(df)
    texts = infer_df.apply(format_input_text, axis=1).tolist()
    result = run_inference(texts, batch_size=cfg.batch_size)

    labeled = df.copy()
    labeled["Метка_Класса"] = result.labels.astype(int)
    labeled["Уровень_тяжести"] = result.level_names
    labeled["Уверенность"] = result.confidences.round(4)
    labeled["severity"] = labeled["Метка_Класса"]
    labeled["is_problem"] = labeled["severity"] > 0
    labeled.to_parquet(cfg.cache_dir / "labeled.parquet", index=False)

    n_prob = int(labeled["is_problem"].sum())
    step("classify", "done", f"проблемных обращений: {n_prob}")

    step("aggregate", "running", "рейтинг = проблемы × тяжесть")
    top_all, top10, top3 = build_municipality_rankings(labeled, cfg)
    top3_names = ", ".join(top3["муниципалитет"].astype(str).tolist()) if len(top3) else "—"
    step("aggregate", "done", f"всего {len(top_all)} МО; Top-3: {top3_names}")

    step("topics", "running", "темы, группы, примеры обращений")
    top_munis = top10["муниципалитет"].tolist() if len(top10) else []
    topics_df, groups_df, reasons_df = build_topic_group_breakdown(labeled, top_munis, cfg)

    summary_text = ""
    muni_summaries = pd.DataFrame()
    if not cfg.skip_summary and top_munis:
        step("summary", "running", f"LLM {cfg.ollama_model}: Top-10 + справка")
        reasons_enriched = enrich_reasons_with_llm(reasons_df, cfg)
        muni_summaries = build_municipality_summaries(labeled, top10, reasons_enriched, cfg)
        summary_text = build_executive_summary(
            labeled.loc[labeled["is_problem"]],
            top3,
            top10,
            reasons_enriched,
            cfg,
        )
        save_summary_artifacts(
            cfg.output_dir,
            summary_text,
            muni_summaries,
            cfg,
            meta={
                "rows_processed": len(labeled),
                "problem_count": n_prob,
                "municipality_count": n_muni,
            },
        )
        reasons_df = reasons_enriched
        step("summary", "done", f"справка {len(summary_text)} симв., {len(muni_summaries)} МО")
    else:
        step("summary", "done", "пропуск")

    top3 = attach_reasons_to_rankings(top3, reasons_df)
    top10 = attach_reasons_to_rankings(top10, reasons_df)

    step("report", "running", "Excel и JSON")
    report_path = write_excel_report(
        cfg, top_all, top10, top3, topics_df, groups_df, reasons_df, labeled
    )
    stats = {
        "rows_processed": len(labeled),
        "problem_count": n_prob,
        "municipality_count": n_muni,
        "top3_count": len(top3),
        "top10_count": len(top10),
    }
    write_report_json(
        cfg.output_dir,
        top_all,
        top10,
        top3,
        topics_df,
        groups_df,
        reasons_df,
        summary_text,
        stats,
    )
    step("report", "done", report_path.name)

    elapsed = round(time.perf_counter() - t0, 1)
    return PipelineResult(
        rows_processed=len(labeled),
        problem_count=n_prob,
        municipality_count=n_muni,
        report_path=report_path,
        elapsed_sec=elapsed,
    )
