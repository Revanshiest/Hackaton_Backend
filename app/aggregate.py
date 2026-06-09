"""Агрегация и ранжирование муниципалитетов по индексу благополучия (Health Score)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config.settings import PipelineSettings

# Экспоненциальные веса тяжести классов 0–4
SEVERITY_WEIGHTS: dict[int, int] = {0: 0, 1: 1, 2: 5, 3: 20, 4: 100}

_INVALID_MUNI = {"", "nan", "none", "<na>"}


def _is_valid_municipality(name) -> bool:
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return False
    return str(name).strip().lower() not in _INVALID_MUNI


def _filter_valid_municipalities(df: pd.DataFrame, district_col: str) -> pd.DataFrame:
    if district_col not in df.columns:
        return df
    mask = df[district_col].map(_is_valid_municipality)
    return df.loc[mask].copy()


def _rating_score(labels: list[int]) -> float:
    raw_score = sum(SEVERITY_WEIGHTS.get(int(label), 0) for label in labels)
    return raw_score / np.log1p(len(labels))


def _health_score(rating_score: float, max_rating: float) -> int:
    """100 — нет проблем, 5 — критично (худший район в срезе).

    Логарифмическая нормализация: один крупный центр (напр. Омск г.о.)
    не сжимает все остальные муниципалитеты в диапазон 96–99.
    """
    if max_rating <= 0 or rating_score <= 0:
        return 100
    ratio = min(1.0, np.log1p(rating_score) / np.log1p(max_rating))
    return max(5, int(100 - ratio * 95))


def calculate_districts_health(
    df: pd.DataFrame,
    district_col: str = "муниципалитет",
    pred_col: str = "severity",
) -> pd.DataFrame:
    """
    Рассчитывает индекс благополучия (Health Score) для всех районов.
    100 — идеальное состояние, 5 — критическая ситуация (ЧС).
    Штраф нормируется на log(1 + N), чтобы крупные районы не доминировали только объёмом.
    Итоговый health_score переводится в шкалу 5–100 через log(1 + rating).
    """
    if district_col not in df.columns:
        raise ValueError(f"Колонка {district_col!r} не найдена")
    if pred_col not in df.columns:
        raise ValueError(f"Колонка {pred_col!r} не найдена")

    df = _filter_valid_municipalities(df, district_col)
    if df.empty:
        return pd.DataFrame()

    district_scores: dict[str, float] = {}
    for district, group in df.groupby(district_col, dropna=False):
        labels = group[pred_col].astype(int).tolist()
        if labels:
            district_scores[str(district)] = _rating_score(labels)

    max_rating = max(district_scores.values()) if district_scores else 0.0

    reports: list[dict] = []
    for district, rating in district_scores.items():
        district_data = df[df[district_col].astype(str) == district]
        labels = district_data[pred_col].astype(int)
        reports.append(
            {
                "муниципалитет": district,
                "total_incidents": len(district_data),
                "problem_count": int((labels > 0).sum()),
                "critical_count": int((labels == 4).sum()),
                "rating_score": round(rating, 4),
                "health_score": _health_score(rating, max_rating),
            }
        )

    if not reports:
        return pd.DataFrame()

    result = pd.DataFrame(reports)
    result = result.sort_values("health_score", ascending=True).reset_index(drop=True)
    result["rank"] = range(1, len(result) + 1)
    result["district_id"] = result["rank"]
    result["score"] = result["health_score"]
    return result


def build_municipality_rankings(
    df: pd.DataFrame,
    cfg: PipelineSettings,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pred_col = "severity" if "severity" in df.columns else "Метка_Класса"
    empty_cols = [
        "муниципалитет",
        "total_incidents",
        "problem_count",
        "critical_count",
        "rating_score",
        "health_score",
        "rank",
        "district_id",
        "score",
        "severity_mean",
        "severity_p90",
        "severity_sum",
        "high_count",
        "problem_share",
    ]

    health_df = calculate_districts_health(df, district_col="муниципалитет", pred_col=pred_col)
    if health_df.empty:
        empty = pd.DataFrame(columns=empty_cols)
        return empty, empty, empty

    extra = (
        df.groupby("муниципалитет", dropna=False)
        .agg(
            severity_mean=(pred_col, "mean"),
            severity_p90=(pred_col, lambda s: s.quantile(0.9) if len(s) else 0),
            severity_sum=(pred_col, "sum"),
            high_count=(pred_col, lambda s: (s.astype(int) >= 3).sum()),
        )
        .reset_index()
    )
    agg = health_df.merge(extra, on="муниципалитет", how="left")
    agg["problem_share"] = (agg["problem_count"] / agg["total_incidents"].clip(lower=1)).round(4)
    agg = agg.loc[agg["total_incidents"] > 0].reset_index(drop=True)
    agg["rank"] = range(1, len(agg) + 1)
    agg["district_id"] = agg["rank"]
    agg["score"] = agg["health_score"]

    top_n = agg.head(cfg.top_municipalities).copy()
    top_hot = agg.head(cfg.top_hotspots).copy()
    return agg, top_n, top_hot
