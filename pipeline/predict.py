#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Быстрый инференс без полного формата разметки."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

if __name__ == "__main__" and str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.inference import DEFAULT_MODEL_DIR, run_inference
from training_utils import format_input_text


def parse_args():
    parser = argparse.ArgumentParser(description="Предсказание класса тяжести.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--model-dir", default=None, help="Оставьте пустым для автовыбора (fast_rubert)")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not os.path.exists(args.input):
        print(f"[Ошибка] Файл не найден: {args.input}")
        return 1

    df = pd.read_excel(args.input)
    texts = df.apply(format_input_text, axis=1).tolist()
    
    device = None if args.device == "auto" else args.device
    try:
        result = run_inference(
            texts,
            model_dir=args.model_dir,
            batch_size=args.batch_size,
            device=device,
        )
    except Exception as e:
        import json
        error_msg = f"Произошла ошибка при обработке модели. Если вы используете CPU, возможно не хватило памяти. Детали: {str(e)}"
        print(json.dumps({"status": "error", "message": error_msg}, ensure_ascii=False))
        return 1

    out = df.copy()
    out["Метка_Предсказание"] = result.labels
    out["Класс_Название"] = result.class_names
    out["Уверенность"] = result.confidences.round(4)

    output = args.output or args.input.replace(".xlsx", "_predictions.xlsx")
    out.to_excel(output, index=False)
    print(f"Сохранено: {output} ({len(out)} строк)")
    print(out["Метка_Предсказание"].value_counts().sort_index().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
