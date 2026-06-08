#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Инференс обученной модели (ONNX)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from training_utils import CLASS_NAMES

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = PROJECT_ROOT / "model_onnx"

LEVEL_LABELS = {
    0: "Не инцидент",
    1: "Низкая тяжесть",
    2: "Средняя тяжесть",
    3: "Высокая тяжесть",
    4: "Критическая / ЧС",
}

REQUIRED_INPUT_COLUMNS = ("Группа тем", "Тема", "Текст инцидента", "Дата создания")


@dataclass(frozen=True)
class PredictionResult:
    labels: np.ndarray
    confidences: np.ndarray
    class_names: list[str]
    level_names: list[str]


def resolve_model_dir(model_dir: str | Path | None) -> Path:
    if model_dir is None:
        return DEFAULT_MODEL_DIR
    path = Path(model_dir)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def validate_input_columns(columns) -> None:
    missing = [c for c in REQUIRED_INPUT_COLUMNS if c not in columns]
    if missing:
        raise ValueError(
            "Входной файл должен содержать колонки как в dataset/train.xlsx:\n"
            f"  {list(REQUIRED_INPUT_COLUMNS)}\n"
            f"Не хватает: {missing}"
        )


def _pack_result(labels: np.ndarray, confidences: np.ndarray) -> PredictionResult:
    return PredictionResult(
        labels=labels,
        confidences=confidences,
        class_names=[CLASS_NAMES[int(x)] for x in labels],
        level_names=[LEVEL_LABELS.get(int(x), CLASS_NAMES[int(x)]) for x in labels],
    )


def predict_onnx(texts: list[str], resolved_dir: Path, batch_size: int, device: str | None) -> PredictionResult:
    import onnxruntime as ort
    from transformers import AutoTokenizer

    model_dir_str = str(resolved_dir)
    tokenizer = AutoTokenizer.from_pretrained(model_dir_str)
    
    # Пытаемся использовать CUDA для ONNX
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    
    # ONNX Runtime сессия
    onnx_model_path = str(resolved_dir / "model.onnx")
    if not Path(onnx_model_path).exists():
        raise FileNotFoundError(f"Файл {onnx_model_path} не найден! Сначала сконвертируйте модель с помощью convert_to_onnx.py.")
        
    session = ort.InferenceSession(onnx_model_path, providers=providers)

    max_length = 512
    label_map_path = resolved_dir / "label_map.json"
    if label_map_path.exists():
        with label_map_path.open(encoding="utf-8") as file:
            max_length = int(json.load(file).get("max_length", max_length))

    all_labels: list[int] = []
    all_conf: list[float] = []

    try:
        from tqdm import tqdm
        loop_iterable = tqdm(range(0, len(texts), batch_size), desc="Обработка батчей (ONNX)", unit="батч")
    except ImportError:
        loop_iterable = range(0, len(texts), batch_size)

    for start in loop_iterable:
        batch = texts[start : start + batch_size]
        encoded = tokenizer(
            batch,
            truncation=True,
            padding=True,
            max_length=max_length,
            return_tensors="np", # ONNX ожидает numpy массивы
        )
        
        # Подготавливаем входы для ONNX
        ort_inputs = {
            session.get_inputs()[0].name: encoded["input_ids"],
            session.get_inputs()[1].name: encoded["attention_mask"],
        }
        
        # Инференс
        logits = session.run(None, ort_inputs)[0]
        
        # Softmax для логитов с помощью numpy
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
        
        batch_labels = np.argmax(probs, axis=1)
        all_labels.extend(batch_labels.tolist())
        all_conf.extend(probs[np.arange(len(batch_labels)), batch_labels].tolist())

    return _pack_result(np.array(all_labels, dtype=int), np.array(all_conf, dtype=float))


def run_inference(
    texts: list[str],
    *,
    model_dir: str | Path | None = None,
    batch_size: int = 16,
    device: str | None = None,
) -> PredictionResult:
    resolved_dir = resolve_model_dir(model_dir)
    return predict_onnx(texts, resolved_dir, batch_size, device)
