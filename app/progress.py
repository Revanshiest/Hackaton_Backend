"""Шаги пайплайна для отображения прогресса в API."""

from __future__ import annotations

PIPELINE_STEPS: list[tuple[str, str]] = [
    ("load", "Загрузка Excel"),
    ("classify", "Классификация ONNX"),
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
