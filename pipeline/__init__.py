"""Пайплайн разметки датасета обученной моделью."""

from pipeline.inference import PredictionResult, run_inference, validate_input_columns

__all__ = ["PredictionResult", "run_inference", "validate_input_columns"]
