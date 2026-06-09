"""Управление фоновыми задачами: память + персистентность на диск."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config.llm import OLLAMA_MODEL
from app.config.paths import JOBS_DIR
from app.config.settings import PipelineSettings
from app.pipeline import run_pipeline
from app.progress import PIPELINE_STEPS, initial_steps, overall_progress
from app.report import load_report_json
from app.summary import build_district_report_summary
from schemas import PipelineOptions

_jobs: dict[str, dict] = {}
_progress_persist_ts: dict[str, float] = {}

_STALE_JOB_MESSAGE = "Прервано перезапуском сервера"
_PROGRESS_PERSIST_INTERVAL_SEC = 0.75


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finalize_step_timing(step: dict) -> None:
    if step.get("ended_at"):
        return
    ended = datetime.now(timezone.utc)
    step["ended_at"] = ended.isoformat()
    started_at = step.get("started_at")
    if started_at and step.get("duration_sec") is None:
        started = datetime.fromisoformat(started_at)
        step["duration_sec"] = round((ended - started).total_seconds(), 1)


def job_path(task_id: str) -> Path:
    return JOBS_DIR / task_id


def output_dir(task_id: str) -> Path:
    return job_path(task_id) / "output"


def persist_job(task_id: str) -> None:
    if task_id not in _jobs:
        return
    path = job_path(task_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "job_status.json").write_text(
        json.dumps(_jobs[task_id], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _reconcile_job_on_load(job: dict) -> bool:
    """Помечает прерванные задачи и выравнивает шаги после сбоя."""
    changed = False
    status = job.get("status")
    if status in ("running", "queued"):
        job["status"] = "failed"
        job["message"] = _STALE_JOB_MESSAGE
        changed = True
    if job.get("status") == "failed":
        for step in job.get("steps") or []:
            if step.get("status") == "running":
                step["status"] = "error"
                if not step.get("detail"):
                    step["detail"] = job.get("message") or "ошибка"
                changed = True
    return changed


def load_jobs_from_disk() -> None:
    if not JOBS_DIR.exists():
        return
    for job_dir in sorted(JOBS_DIR.iterdir()):
        if not job_dir.is_dir():
            continue
        status_path = job_dir / "job_status.json"
        if not status_path.exists():
            continue
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
            task_id = data.get("task_id") or job_dir.name
            if _reconcile_job_on_load(data):
                _jobs[task_id] = data
                persist_job(task_id)
            else:
                _jobs[task_id] = data
        except (json.JSONDecodeError, KeyError, OSError):
            continue


def normalize_job_steps(job: dict) -> list[dict]:
    """Всегда возвращает полный список шагов пайплайна (6 этапов)."""
    existing = {step["id"]: step for step in (job.get("steps") or [])}
    normalized: list[dict] = []
    for step_id, label in PIPELINE_STEPS:
        step = dict(existing.get(step_id, {}))
        step.setdefault("id", step_id)
        step.setdefault("label", label)
        step.setdefault("status", "pending")
        step.setdefault("detail", "")
        normalized.append(step)
    return normalized


def get_job(task_id: str) -> dict | None:
    job = _jobs.get(task_id)
    if job is None:
        return None
    job = dict(job)
    job["steps"] = normalize_job_steps(job)
    return job


def list_jobs() -> list[dict]:
    return list(_jobs.values())


def update_job_step(
    task_id: str,
    step_id: str,
    status: str,
    detail: str = "",
    *,
    step_fraction: float | None = None,
) -> None:
    steps = _jobs[task_id].get("steps") or initial_steps()
    order = [s[0] for s in PIPELINE_STEPS]
    if status == "running" and step_id in order:
        idx = order.index(step_id)
        for step in steps:
            if step["id"] in order[:idx] and step["status"] == "running":
                step["status"] = "done"
                step["progress"] = 100.0
                _finalize_step_timing(step)
    for step in steps:
        if step["id"] == step_id:
            step["status"] = status
            if detail:
                step["detail"] = detail
            elif status == "running" and not step.get("detail"):
                step["detail"] = "выполняется…"
            if status == "running" and not step.get("started_at"):
                step["started_at"] = _now_iso()
            if status in ("done", "error"):
                step["progress"] = 100.0
                _finalize_step_timing(step)
            elif step_fraction is not None:
                step["progress"] = round(max(0.0, min(100.0, step_fraction * 100)), 1)
            break
    _jobs[task_id]["steps"] = steps
    if status == "done":
        _jobs[task_id]["progress"] = overall_progress(step_id, step_done=True)
    elif step_fraction is not None:
        _jobs[task_id]["progress"] = round(
            overall_progress(step_id, step_fraction=step_fraction),
            1,
        )
    if detail:
        _jobs[task_id]["message"] = detail

    force_persist = status in ("done", "error") or step_fraction is None
    now = time.perf_counter()
    last = _progress_persist_ts.get(task_id, 0.0)
    if force_persist or now - last >= _PROGRESS_PERSIST_INTERVAL_SEC:
        _progress_persist_ts[task_id] = now
        persist_job(task_id)


def run_job(task_id: str, input_path: Path, options: PipelineOptions) -> None:
    out = output_dir(task_id)
    out.mkdir(parents=True, exist_ok=True)
    _jobs[task_id]["status"] = "running"
    _jobs[task_id]["steps"] = initial_steps()
    _jobs[task_id]["message"] = "Обработка…"
    persist_job(task_id)

    started = time.perf_counter()

    def on_progress(
        step_id: str,
        status: str,
        detail: str = "",
        step_fraction: float | None = None,
    ) -> None:
        update_job_step(task_id, step_id, status, detail, step_fraction=step_fraction)

    try:
        cfg = PipelineSettings(
            input_path=input_path,
            output_dir=out,
            cache_dir=job_path(task_id) / "cache",
            batch_size=options.batch_size,
            skip_summary=options.skip_summary,
            nrows=options.nrows,
            ollama_model=options.model or OLLAMA_MODEL,
            llm_fast_mode=options.llm_fast_mode,
        )
        result = run_pipeline(cfg, on_progress=on_progress)
        elapsed = round(time.perf_counter() - started, 1)
        stats = {
            "elapsed_sec": elapsed,
            "rows_processed": result.rows_processed,
            "problem_count": result.problem_count,
            "municipality_count": result.municipality_count,
            "report_file": result.report_path.name,
        }
        _jobs[task_id]["status"] = "completed"
        _jobs[task_id]["progress"] = 100.0
        _jobs[task_id]["rows_processed"] = result.rows_processed
        _jobs[task_id]["stats"] = stats
        _jobs[task_id]["message"] = (
            f"Готово за {elapsed} с · {result.rows_processed} строк · "
            f"{result.municipality_count} МО"
        )
        persist_job(task_id)
    except Exception as exc:
        _jobs[task_id]["status"] = "failed"
        _jobs[task_id]["message"] = str(exc)
        update_job_step(task_id, "report", "error", str(exc))
        persist_job(task_id)


def require_job(task_id: str) -> dict:
    job = get_job(task_id)
    if job is None:
        raise KeyError(task_id)
    return job


class JobNotReadyError(Exception):
    def __init__(self, status: str):
        self.status = status
        super().__init__(status)


def require_completed(task_id: str) -> Path:
    job = require_job(task_id)
    if job["status"] != "completed":
        raise JobNotReadyError(job["status"])
    return output_dir(task_id)


def get_report(task_id: str) -> dict:
    out = require_completed(task_id)
    path = out / "report.json"
    if not path.exists():
        raise FileNotFoundError("report.json")
    return load_report_json(path)


def get_labeled_df(task_id: str):
    cache_path = job_path(task_id) / "cache" / "labeled.parquet"
    if not cache_path.exists():
        return None
    import pandas as pd

    return pd.read_parquet(cache_path)


def generate_district_report(
    task_id: str,
    district_id: int,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    model: str | None = None,
) -> str:
    out = require_completed(task_id)
    report = get_report(task_id)
    all_rows = report.get("all", [])
    target = next(
        (r for r in all_rows if int(r.get("district_id", r.get("rank", -1))) == district_id),
        None,
    )
    if target is None:
        raise ValueError(f"Район с id={district_id} не найден")

    cache_path = job_path(task_id) / "cache" / "labeled.parquet"
    if not cache_path.exists():
        raise FileNotFoundError("Размеченные данные не найдены")

    import pandas as pd

    labeled = pd.read_parquet(cache_path)
    cfg = PipelineSettings(
        input_path=out / "input.xlsx",
        output_dir=out,
        cache_dir=job_path(task_id) / "cache",
        ollama_model=model or OLLAMA_MODEL,
    )
    summary = build_district_report_summary(
        labeled,
        target["муниципалитет"],
        cfg,
        start_date=start_date,
        end_date=end_date,
    )

    district_reports = out / "district_reports"
    district_reports.mkdir(parents=True, exist_ok=True)
    report_path = district_reports / f"district_{district_id}.json"
    payload = {
        "district_id": district_id,
        "district_name": target["муниципалитет"],
        "analytical_summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def get_district_summary(task_id: str, district_id: int) -> str | None:
    path = output_dir(task_id) / "district_reports" / f"district_{district_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("analytical_summary")


def create_job(task_id: str, filename: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "task_id": task_id,
        "status": "queued",
        "message": "В очереди",
        "created_at": now,
        "filename": filename,
        "rows_processed": None,
        "stats": None,
        "steps": initial_steps(),
        "progress": 0.0,
    }
    _jobs[task_id] = job
    job_path(task_id).mkdir(parents=True, exist_ok=True)
    persist_job(task_id)
    return job
