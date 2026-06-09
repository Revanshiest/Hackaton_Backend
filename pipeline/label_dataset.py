#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пайплайн разметки: Excel как при обучении → Excel с метками классов.

Вход (как dataset/train.xlsx):
  Группа тем, Тема, Текст инцидента, Дата создания

Выход:
  + Метка_Класса, Уровень_тяжести, Уверенность, Источник_разметки
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

# Корень проекта в PYTHONPATH при запуске python -m pipeline.label_dataset
if __name__ == "__main__" and str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.inference import DEFAULT_MODEL_DIR, run_inference, validate_input_columns
from training_utils import format_input_text


def parse_args():
    parser = argparse.ArgumentParser(
        description="Разметка датасета обученным классификатором (формат как при train)."
    )
    parser.add_argument("--input", "-i", required=True, help="Входной .xlsx")
    parser.add_argument(
        "--output", "-o", default="",
        help="Выходной .xlsx (по умолчанию: <имя>_размеченный.xlsx)",
    )
    parser.add_argument(
        "--model-dir",
        default=None,
        help="Папка модели (по умолчанию авто: fast_rubert/)",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--source", default="model/xlm-roberta")
    return parser.parse_args()


def default_output_path(input_path: str) -> str:
    base, ext = os.path.splitext(input_path)
    if base.endswith("_размеченный"):
        return f"{base}_ml{ext or '.xlsx'}"
    return f"{base}_размеченный{ext or '.xlsx'}"


def main() -> int:
    args = parse_args()
    if not os.path.exists(args.input):
        print(f"[Ошибка] Файл не найден: {args.input}")
        return 1

    model_path = args.model_dir
    if model_path is not None:
        model_path = Path(model_path)
        if not model_path.is_absolute():
            model_path = Path(__file__).resolve().parents[1] / model_path
        if not model_path.is_dir():
            print(f"[Ошибка] Папка модели не найдена: {model_path}")
            return 1

    print(f"--- Разметка: {args.input} ---")
    df = pd.read_excel(args.input)
    try:
        validate_input_columns(df.columns)
    except ValueError as exc:
        print(f"[Ошибка] {exc}")
        return 1

    texts = df.apply(format_input_text, axis=1).tolist()
    empty = sum(1 for t in texts if not str(t).strip())
    if empty:
        print(f"[Предупреждение] Пустых текстов после сборки: {empty}")

    device = None if args.device == "auto" else args.device
    print(f"Модель: XLM-RoBERTa @ {model_path}")
    try:
        result = run_inference(
            texts,
            model_dir=model_path,
            batch_size=args.batch_size,
            device=device,
        )
    except Exception as e:
        import json
        error_msg = f"Произошла ошибка при обработке модели. Если вы используете CPU, возможно не хватило памяти. Детали: {str(e)}"
        print(json.dumps({"status": "error", "message": error_msg}, ensure_ascii=False))
        return 1

    out = df.copy()
    if "Метка_Класса" in out.columns:
        out = out.drop(columns=["Метка_Класса"])
    out["Метка_Класса"] = result.labels.astype(int)
    out["Уровень_тяжести"] = result.level_names
    out["Уверенность"] = result.confidences.round(4)
    out["Источник_разметки"] = args.source

    output = args.output or default_output_path(args.input)
    out.to_excel(output, index=False)

    print(f"\nСохранено: {output} ({len(out)} строк)")
    print("Распределение классов:")
    print(out["Метка_Класса"].value_counts().sort_index().to_string())
    print(f"Средняя уверенность: {out['Уверенность'].mean():.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
