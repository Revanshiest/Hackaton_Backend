"""LLM-справки через Ollama (gemma4:e2b): Top-10 МО + общая справка + отчёт по району."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from app.config.llm import OLLAMA_BASE_URL, OLLAMA_MODEL
from app.config.settings import PipelineSettings
from app.text_samples import sample_problem_texts, truncate_text


def _chat(cfg: PipelineSettings, prompt: str) -> str:
    url = f"{cfg.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": cfg.ollama_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.2},
    }
    resp = requests.post(url, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    message = data.get("message", {})
    return str(message.get("content", "")).strip()


def enrich_reasons_with_llm(
    reasons_df: pd.DataFrame,
    cfg: PipelineSettings,
) -> pd.DataFrame:
    if reasons_df.empty:
        return reasons_df
    out = reasons_df.copy()
    texts: list[str] = []
    for _, row in out.iterrows():
        prompt = (
            "Одно предложение для руководства (без персональных данных):\n"
            f"Муниципалитет: {row['муниципалитет']}\n"
            f"Темы: {row.get('ключевые_темы', '')}\n"
            f"Группы: {row.get('ключевые_группы', '')}\n"
            f"Примеры текстов: {row.get('примеры_текстов', '')}\n"
        )
        texts.append(_chat(cfg, prompt))
    out["summary_text"] = texts
    return out


def build_executive_summary(
    problems_df: pd.DataFrame,
    top3: pd.DataFrame,
    top10: pd.DataFrame,
    reasons_df: pd.DataFrame,
    cfg: PipelineSettings,
) -> str:
    n_examples = cfg.examples_per_muni
    blocks: list[str] = []

    blocks.append("Top-3 муниципалитетов:")
    for _, row in top3.iterrows():
        muni = row["муниципалитет"]
        blocks.append(
            f"- #{row['rank']} {muni}: {int(row['problem_count'])} проблем, "
            f"рейтинг {row.get('rating_score', 0)}"
        )
        key_t = row.get("ключевые_темы") or ""
        key_g = row.get("ключевые_группы") or ""
        if key_t:
            blocks.append(f"  темы: {key_t}")
        if key_g:
            blocks.append(f"  группы: {key_g}")
        if not reasons_df.empty:
            sub = reasons_df[reasons_df["муниципалитет"] == muni]
            if len(sub) and sub.iloc[0].get("summary_text"):
                blocks.append(f"  вывод: {sub.iloc[0]['summary_text']}")
        examples = sample_problem_texts(problems_df, muni, n=n_examples)
        if examples:
            blocks.append("  примеры обращений:")
            for i, ex in enumerate(examples, 1):
                blocks.append(f"    {i}) {ex}")

    blocks.append("")
    blocks.append("Контекст Top-10:")
    for _, row in top10.iterrows():
        muni = row["муниципалитет"]
        blocks.append(
            f"- #{int(row['rank'])} {muni}: {int(row['problem_count'])} проблем, "
            f"доля {row.get('problem_share', 0):.1%}"
        )
        ex = sample_problem_texts(problems_df, muni, n=1)
        if ex:
            blocks.append(f"  пример: {ex[0]}")

    context = "\n".join(blocks)
    prompt = (
        "Составь краткую справку для руководства по данным мониторинга обращений "
        "(Омская область). Русский язык, деловой стиль, без персональных данных. "
        "Структура: заголовок, блок Top-3 с выводами, краткий контекст Top-10, "
        "итоговая рекомендация.\n\n"
        f"Данные:\n{context}\n\n"
        "Методика: ONNX-классификатор тяжести, ранжирование по муниципалитету, "
        "причины по полям «тема» и «группа»."
    )
    return _chat(cfg, prompt)


def build_municipality_summaries(
    problems_df: pd.DataFrame,
    top10: pd.DataFrame,
    reasons_df: pd.DataFrame,
    cfg: PipelineSettings,
) -> pd.DataFrame:
    rows = []
    for _, row in top10.iterrows():
        muni = row["муниципалитет"]
        reason_row = reasons_df[reasons_df["муниципалитет"] == muni]
        key_t = row.get("ключевые_темы") or (
            reason_row.iloc[0]["ключевые_темы"] if len(reason_row) else ""
        )
        key_g = row.get("ключевые_группы") or (
            reason_row.iloc[0]["ключевые_группы"] if len(reason_row) else ""
        )
        examples = sample_problem_texts(problems_df, muni, n=cfg.examples_per_muni)
        prompt = (
            f"Одним абзацем (3–4 предложения) опиши ситуацию в муниципалитете «{muni}» "
            f"для руководства. Проблемных обращений: {int(row['problem_count'])}. "
            "Без персональных данных, конкретно по темам.\n\n"
            f"Темы: {key_t}\n"
            f"Группы: {key_g}\n"
            f"Примеры: {'; '.join(examples[:3])}"
        )
        summary = _chat(cfg, prompt)
        rows.append(
            {
                "district_id": int(row["district_id"]),
                "муниципалитет": muni,
                "rank": int(row["rank"]),
                "problem_count": int(row["problem_count"]),
                "summary": summary,
            }
        )
    return pd.DataFrame(rows)


def build_district_report_summary(
    df: pd.DataFrame,
    district_name: str,
    cfg: PipelineSettings,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    work = df[df["муниципалитет"].astype(str) == str(district_name)].copy()
    if start_date and "дата_создания" in work.columns:
        work = work[work["дата_создания"].astype(str) >= start_date]
    if end_date and "дата_создания" in work.columns:
        work = work[work["дата_создания"].astype(str) <= end_date]

    problems = work.loc[work.get("is_problem", work["severity"] > 0).fillna(False)]
    if problems.empty:
        return f"В муниципалитете «{district_name}» проблемных обращений не выявлено."

    theme_stats = (
        problems.groupby("тема")
        .agg(count=("row_id", "count"), severity_mean=("severity", "mean"))
        .reset_index()
        .sort_values("count", ascending=False)
        .head(8)
    )
    group_stats = (
        problems.groupby("группа")
        .agg(count=("row_id", "count"), severity_mean=("severity", "mean"))
        .reset_index()
        .sort_values("count", ascending=False)
        .head(5)
    )

    themes_block = "\n".join(
        f"- {r['тема']}: {int(r['count'])} обращ., ср.тяжесть {r['severity_mean']:.1f}"
        for _, r in theme_stats.iterrows()
    )
    groups_block = "\n".join(
        f"- {r['группа']}: {int(r['count'])} обращ."
        for _, r in group_stats.iterrows()
    )
    examples = sample_problem_texts(problems, district_name, n=5)

    prompt = (
        f"Составь подробный аналитический отчёт по муниципалитету «{district_name}» "
        "для руководства Омской области. Русский язык, деловой стиль, без персональных данных.\n\n"
        f"Всего проблемных обращений: {len(problems)}\n"
        f"Средняя тяжесть: {problems['severity'].mean():.2f}\n"
        f"Критических (4): {(problems['severity'] >= 4).sum()}\n\n"
        f"Темы:\n{themes_block}\n\n"
        f"Группы:\n{groups_block}\n\n"
        f"Примеры обращений:\n"
        + "\n".join(f"- {truncate_text(e)}" for e in examples)
        + "\n\nСтруктура: краткая сводка, ключевые проблемы, причины, рекомендации."
    )
    return _chat(cfg, prompt)


def save_summary_artifacts(
    output_dir: Path,
    executive_summary: str,
    muni_df: pd.DataFrame,
    cfg: PipelineSettings,
    meta: dict,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    executive_path = output_dir / "executive_summary.md"
    executive_path.write_text(executive_summary, encoding="utf-8")
    muni_path = output_dir / "municipality_summaries.xlsx"
    muni_df.to_excel(muni_path, index=False, engine="openpyxl")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": cfg.ollama_model or OLLAMA_MODEL,
        "executive_summary": executive_summary,
        "municipalities": muni_df.fillna("").to_dict(orient="records"),
        "meta": meta,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
