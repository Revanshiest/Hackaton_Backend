"""Шаги пайплайна для отображения прогресса в API."""

from __future__ import annotations

PIPELINE_STEPS: list[tuple[str, str]] = [
    ("load", "Загрузка Excel"),
    ("classify", "Лейблинг (ONNX)"),
    ("aggregate", "Ранжирование муниципалитетов"),
    ("topics", "Темы и причины"),
    ("summary", "LLM-справки"),
    ("report", "Формирование отчётов"),
]


def initial_steps() -> list[dict]:
    return [
        {"id": step_id, "label": label, "status": "pending", "detail": ""}
        for step_id, label in PIPELINE_STEPS
    ]


def overall_progress(step_id: str, *, step_fraction: float = 0.0, step_done: bool = False) -> float:
    """Общий прогресс пайплайна 0–100 с учётом подпрогресса текущего шага."""
    order = [step for step, _ in PIPELINE_STEPS]
    idx = order.index(step_id)
    if step_done:
        return min(100.0, ((idx + 1) / len(order)) * 100)
    fraction = max(0.0, min(1.0, step_fraction))
    return min(100.0, ((idx + fraction) / len(order)) * 100)
