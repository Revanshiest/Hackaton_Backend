"""Агрегация и ранжирование муниципалитетов по количеству и тяжести проблем."""

from __future__ import annotations

import pandas as pd

from app.config.settings import PipelineSettings


def _health_score(rating_score: float, max_rating: float) -> int:
    """Индекс благополучия района: 100 — нет проблем, 0 — критично."""
    if max_rating <= 0:
        return 50
    ratio = min(1.0, rating_score / max_rating)
    return max(5, int(100 - ratio * 95))


def build_municipality_rankings(
    df: pd.DataFrame,
    cfg: PipelineSettings,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = df.copy()
    work["is_problem"] = work.get("is_problem", work["severity"] > 0)
    problems = work.loc[work["is_problem"].fillna(False)].copy()

    if problems.empty:
        empty = pd.DataFrame(columns=[
            "муниципалитет", "problem_count", "severity_sum", "severity_mean",
            "severity_p90", "critical_count", "high_count", "total_incidents",
            "problem_share", "rating_score", "rank", "district_id", "score",
        ])
        return empty, empty, empty

    agg = (
        problems.groupby("муниципалитет", dropna=False)
        .agg(
            problem_count=("row_id", "count"),
            severity_sum=("severity", "sum"),
            severity_mean=("severity", "mean"),
            severity_p90=("severity", lambda s: s.quantile(0.9) if len(s) else 0),
            critical_count=("severity", lambda s: (s >= 4).sum()),
            high_count=("severity", lambda s: (s >= 3).sum()),
        )
        .reset_index()
    )

    totals = work.groupby("муниципалитет")["row_id"].count().rename("total_incidents")
    agg = agg.merge(totals, on="муниципалитет", how="left")
    agg["problem_share"] = (agg["problem_count"] / agg["total_incidents"].clip(lower=1)).round(4)

    agg["rating_score"] = (
        agg["problem_count"] * agg["severity_mean"]
        + agg["critical_count"] * 2.0
    ).round(2)

    agg = agg.sort_values(
        ["rating_score", "problem_count", "severity_p90"],
        ascending=False,
    ).reset_index(drop=True)
    agg["rank"] = range(1, len(agg) + 1)

    max_rating = float(agg["rating_score"].max()) if len(agg) else 1.0
    agg["district_id"] = agg["rank"]
    agg["score"] = agg["rating_score"].apply(lambda x: _health_score(x, max_rating))

    top_n = agg.head(cfg.top_municipalities).copy()
    top_hot = agg.head(cfg.top_hotspots).copy()
    return agg, top_n, top_hot
