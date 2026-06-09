#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Инференс обученной модели (ONNX)."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

BatchProgressCallback = Callable[[int, int], None]

from app.config.paths import MODEL_DIR
from training_utils import CLASS_NAMES

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = MODEL_DIR

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


def _ensure_cuda_dlls() -> None:
    """Загружает CUDA/cuDNN DLL (Windows + pip nvidia-* пакеты)."""
    try:
        import onnxruntime as ort

        preload = getattr(ort, "preload_dlls", None)
        if callable(preload):
            preload(cuda=True, cudnn=True)
    except Exception as exc:
        print(f"ONNX preload_dlls: {exc}", flush=True)


def _build_ort_inputs(session, encoded: dict) -> dict:
    """Собирает входы ONNX по именам, которые ожидает конкретная модель."""
    ort_inputs: dict[str, np.ndarray] = {}
    for input_meta in session.get_inputs():
        name = input_meta.name
        if name in encoded:
            ort_inputs[name] = encoded[name]
            continue
        if name == "token_type_ids":
            ort_inputs[name] = np.zeros_like(encoded["input_ids"], dtype=np.int64)
            continue
        raise ValueError(
            f"ONNX-модель ожидает вход '{name}', но токенизатор его не вернул. "
            f"Доступно: {list(encoded.keys())}"
        )
    return ort_inputs


def resolve_onnx_providers(device: str | None = None) -> list[str]:
    import os

    import onnxruntime as ort

    prefer_cpu = (device or os.environ.get("ONNX_DEVICE", "")).lower() == "cpu"
    if not prefer_cpu:
        _ensure_cuda_dlls()

    available = ort.get_available_providers()
    if not prefer_cpu and "CUDAExecutionProvider" in available:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def predict_onnx(
    texts: list[str],
    resolved_dir: Path,
    batch_size: int,
    device: str | None,
    on_batch_progress: BatchProgressCallback | None = None,
) -> PredictionResult:
    import onnxruntime as ort
    from transformers import AutoTokenizer

    model_dir_str = str(resolved_dir)
    tokenizer = AutoTokenizer.from_pretrained(model_dir_str)

    providers = resolve_onnx_providers(device)

    onnx_model_path = str(resolved_dir / "model.onnx")
    if not Path(onnx_model_path).exists():
        raise FileNotFoundError(
            f"Файл {onnx_model_path} не найден! Положите model.onnx в каталог fast_rubert/."
        )

    session = ort.InferenceSession(onnx_model_path, providers=providers)
    active = session.get_providers()
    print(f"ONNX inference: requested={providers} active={active}", flush=True)

    max_length = 512
    label_map_path = resolved_dir / "label_map.json"
    if label_map_path.exists():
        with label_map_path.open(encoding="utf-8") as file:
            max_length = int(json.load(file).get("max_length", max_length))

    all_labels: list[int] = []
    all_conf: list[float] = []
    batch_starts = list(range(0, len(texts), batch_size))
    total_batches = len(batch_starts)

    if on_batch_progress is None:
        try:
            from tqdm import tqdm
            loop_iterable = tqdm(batch_starts, desc="Обработка батчей (ONNX)", unit="батч")
        except ImportError:
            loop_iterable = batch_starts
    else:
        loop_iterable = batch_starts

    for batch_idx, start in enumerate(loop_iterable, start=1):
        batch = texts[start : start + batch_size]
        encoded = tokenizer(
            batch,
            truncation=True,
            padding=True,
            max_length=max_length,
            return_tensors="np",
            return_token_type_ids=True,
        )
        ort_inputs = _build_ort_inputs(session, encoded)
        
        # Инференс
        logits = session.run(None, ort_inputs)[0]
        
        # Softmax для логитов с помощью numpy
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
        
        batch_labels = np.argmax(probs, axis=1)
        all_labels.extend(batch_labels.tolist())
        all_conf.extend(probs[np.arange(len(batch_labels)), batch_labels].tolist())
        if on_batch_progress is not None:
            on_batch_progress(min(start + len(batch), len(texts)), len(texts))

    return _pack_result(np.array(all_labels, dtype=int), np.array(all_conf, dtype=float))


def run_inference(
    texts: list[str],
    *,
    model_dir: str | Path | None = None,
    batch_size: int = 16,
    device: str | None = None,
    on_batch_progress: BatchProgressCallback | None = None,
) -> PredictionResult:
    resolved_dir = resolve_model_dir(model_dir)
    return predict_onnx(texts, resolved_dir, batch_size, device, on_batch_progress)
