"""Агрегация по темам и группам, формирование причин по муниципалитетам."""

from __future__ import annotations

import pandas as pd

from app.config.settings import PipelineSettings
from app.text_samples import sample_problem_texts


def _agg_by_dimension(
    problems: pd.DataFrame,
    dim_col: str,
    dim_label: str,
) -> pd.DataFrame:
    if problems.empty or dim_col not in problems.columns:
        return pd.DataFrame()

    g = (
        problems.groupby(["муниципалитет", dim_col], dropna=False)
        .agg(
            count=("row_id", "count"),
            severity_mean=("severity", "mean"),
            severity_sum=("severity", "sum"),
            critical_count=("severity", lambda s: (s >= 4).sum()),
        )
        .reset_index()
    )
    g = g.rename(columns={dim_col: dim_label})
    g["rating_score"] = (
        g["count"] * g["severity_mean"]
        + g["critical_count"] * 2.0
    ).round(2)
    g = g.sort_values(
        ["муниципалитет", "rating_score", "count"],
        ascending=[True, False, False],
    )
    return g


def build_topic_group_breakdown(
    df: pd.DataFrame,
    municipalities: list[str],
    cfg: PipelineSettings,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = df.copy()
    work["is_problem"] = work.get("is_problem", work["severity"] > 0)
    problems = work.loc[work["is_problem"].fillna(False)].copy()

    topics = _agg_by_dimension(problems, "тема", "тема")
    groups = _agg_by_dimension(problems, "группа", "группа")

    reasons_rows = []
    for muni in municipalities:
        t_sub = topics[topics["муниципалитет"] == muni].head(5) if not topics.empty else pd.DataFrame()
        g_sub = groups[groups["муниципалитет"] == muni].head(5) if not groups.empty else pd.DataFrame()

        key_topics = "; ".join(
            f"{r['тема']} ({int(r['count'])})" for _, r in t_sub.iterrows()
        )
        key_groups = "; ".join(
            f"{r['группа']} ({int(r['count'])})" for _, r in g_sub.iterrows()
        )
        examples = sample_problem_texts(problems, muni, n=cfg.examples_per_muni)
        reasons_rows.append(
            {
                "муниципалитет": muni,
                "ключевые_темы": key_topics,
                "ключевые_группы": key_groups,
                "топ_тема": t_sub.iloc[0]["тема"] if len(t_sub) else "",
                "топ_группа": g_sub.iloc[0]["группа"] if len(g_sub) else "",
                "примеры_обращений": examples,
                "примеры_текстов": " || ".join(e["text"] for e in examples),
            }
        )

    reasons_df = pd.DataFrame(reasons_rows)
    return topics, groups, reasons_df


def attach_reasons_to_rankings(
    top_df: pd.DataFrame,
    reasons_df: pd.DataFrame,
) -> pd.DataFrame:
    if reasons_df.empty or top_df.empty:
        return top_df
    return top_df.merge(reasons_df, on="муниципалитет", how="left")
