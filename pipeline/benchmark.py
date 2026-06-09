#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Бенчмарк для замера скорости инференса на GPU."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd

if __name__ == "__main__" and str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.inference import DEFAULT_MODEL_DIR, run_inference
from training_utils import format_input_text


def parse_args():
    parser = argparse.ArgumentParser(description="Бенчмарк инференса на GPU.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--model-dir", default=None, help="Оставьте пустым для автовыбора (fast_rubert)")
    parser.add_argument("--batch-size", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not os.path.exists(args.input):
        print(f"[Ошибка] Файл не найден: {args.input}")
        return 1

    print("Загрузка датасета и подготовка текстов...")
    df = pd.read_excel(args.input)
    texts = df.apply(format_input_text, axis=1).tolist()
    num_samples = len(texts)
    print(f"Всего записей для обработки: {num_samples}")
    
    print("\nНачало инференса (загрузка модели в VRAM + прогон)...")
    start_time = time.perf_counter()
    
    try:
        result = run_inference(
            texts,
            model_dir=args.model_dir,
            batch_size=args.batch_size,
            device="cuda", # Жестко передаем cuda
        )
    except Exception as e:
        print(f"Ошибка при инференсе: {e}", file=sys.stderr)
        return 1
        
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    
    throughput = num_samples / elapsed_time if elapsed_time > 0 else 0
    
    print("\n" + "="*40)
    print("РЕЗУЛЬТАТЫ БЕНЧМАРКА (GPU):")
    print("="*40)
    print(f"Обработано записей : {num_samples}")
    print(f"Размер батча       : {args.batch_size}")
    print(f"Общее время        : {elapsed_time:.3f} секунд")
    print(f"Скорость           : {throughput:.2f} записей в секунду")
    print("="*40)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
