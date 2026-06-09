"""Сборка frontend/src/data/demoSnapshot.json из report.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.progress import PIPELINE_STEPS
from app.report import (
    build_dashboard,
    build_district_report,
    build_severity_breakdown,
    enrich_report_period,
    load_report_json,
)
from app.text_samples import sample_problem_texts

EXAMPLES_PER_MUNI = 6

STEP_DESCRIPTIONS: dict[str, str] = {
    "load": "Чтение обращений и муниципалитетов из Excel",
    "classify": "ONNX-модель определяет тяжесть обращений (классы 0–4)",
    "aggregate": "Расчёт Health Score и ранжирование муниципалитетов",
    "topics": "Группировка обращений по темам и причинам",
    "summary": "LLM-справки для критических районов (Ollama)",
    "report": "Формирование JSON и Excel отчётов",
}

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "frontend" / "src" / "data" / "demoSnapshot.json"


def _dump_model(obj) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


def find_latest_report(jobs_dir: Path | None = None) -> Path:
    jobs_dir = jobs_dir or (ROOT / "cache" / "jobs")
    reports = sorted(jobs_dir.glob("*/output/report.json"), key=lambda p: p.stat().st_mtime)
    if not reports:
        raise FileNotFoundError(f"Нет report.json в {jobs_dir}")
    return reports[-1]


def _looks_like_municipality(name: str) -> bool:
    n = str(name or "").strip().lower()
    if not n or n in {"nan", "none", "<na>"}:
        return False
    if n.startswith("улица") or "переулок" in n or n.startswith("мост "):
        return False
    return "район" in n or "г.о." in n or "область" in n or n.endswith(" округ")


def _report_quality(path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("all", [])
    valid = sum(1 for r in rows if _looks_like_municipality(r.get("муниципалитет", "")))
    return valid, len(rows)


def find_fullest_report(jobs_dir: Path | None = None) -> Path:
    """Report с max числом валидных муниципалитетов (без улиц из битого парсинга)."""
    jobs_dir = jobs_dir or (ROOT / "cache" / "jobs")
    reports = list(jobs_dir.glob("*/output/report.json"))
    if not reports:
        raise FileNotFoundError(f"Нет report.json в {jobs_dir}")
    return max(reports, key=_report_quality)


def resolve_report_path(job_id: str | None = None, report_path: Path | None = None) -> Path:
    if report_path is not None:
        path = Path(report_path)
        if not path.exists():
            raise FileNotFoundError(path)
        return path
    if job_id:
        path = ROOT / "cache" / "jobs" / job_id / "output" / "report.json"
        if not path.exists():
            raise FileNotFoundError(path)
        return path
    return find_fullest_report()


def build_demo_snapshot(
    *,
    job_id: str | None = None,
    report_path: Path | None = None,
    out_path: Path | None = None,
) -> Path:
    report_file = resolve_report_path(job_id=job_id, report_path=report_path)
    report = load_report_json(report_file)
    labeled_df = None
    labeled_path = report_file.parent.parent / "cache" / "labeled.parquet"
    if labeled_path.exists():
        import pandas as pd

        labeled_df = pd.read_parquet(labeled_path)
        if not report.get("severity_breakdown"):
            report["severity_breakdown"] = build_severity_breakdown(labeled_df)
        if labeled_df is not None and not labeled_df.empty:
            for reason in report.get("reasons", []):
                if not reason.get("примеры_обращений"):
                    muni = str(reason.get("муниципалитет", ""))
                    problems = labeled_df
                    if "severity" in labeled_df.columns:
                        problems = labeled_df.loc[labeled_df["severity"].fillna(0) > 0]
                    examples = sample_problem_texts(problems, muni, n=EXAMPLES_PER_MUNI)
                    reason["примеры_обращений"] = examples
                    if examples and not reason.get("примеры_текстов"):
                        reason["примеры_текстов"] = " || ".join(e["text"] for e in examples)
    enrich_report_period(report, report_file.parent.parent / "cache")
    dashboard = build_dashboard(report)
    dash_dump = _dump_model(dashboard)

    district_reports: dict[str, dict] = {}
    for row in report.get("all", []):
        district_id = int(row.get("district_id", row.get("rank", 0)))
        built = build_district_report(report, district_id, labeled_df=labeled_df)
        if built is not None:
            district_reports[str(district_id)] = _dump_model(built)

    payload = {
        "meta": {
            "source_job": report_file.parent.parent.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rows_total": dash_dump.get("total_incidents")
            or sum(int(r.get("total_incidents", 0)) for r in report.get("all", [])),
            "municipalities": len(report.get("all", [])),
            "start_date": dash_dump.get("start_date"),
            "end_date": dash_dump.get("end_date"),
            "problem_count": dash_dump.get("problem_count"),
        },
        "pipeline_steps": [
            {
                "id": step_id,
                "label": label,
                "description": STEP_DESCRIPTIONS.get(step_id, ""),
            }
            for step_id, label in PIPELINE_STEPS
        ],
        "dashboard": dash_dump,
        "district_reports": district_reports,
    }

    destination = out_path or DEFAULT_OUT
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination
