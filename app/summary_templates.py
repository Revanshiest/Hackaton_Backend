"""Шаблонные справки по структурированным данным — быстро и с цифрами."""

from __future__ import annotations

import pandas as pd


def _safe_int(val, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _first_theme(key_topics: str) -> str:
    part = str(key_topics or "").split(";")[0].strip()
    if "(" in part:
        part = part.rsplit("(", 1)[0].strip()
    return part


def _as_series(row: pd.Series | pd.DataFrame | None, fallback: pd.Series) -> pd.Series:
    if row is None:
        return fallback
    if isinstance(row, pd.DataFrame):
        return row.iloc[0]
    return row


def template_district_sentence(rank_row: pd.Series, reason_row: pd.Series | None = None) -> str:
    """Одно предложение для карточки / reasons — с цифрами и топ-темой."""
    reason_row = _as_series(reason_row, rank_row)
    muni = str(rank_row.get("муниципалитет", ""))
    problems = _safe_int(rank_row.get("problem_count"))
    total = _safe_int(rank_row.get("total_incidents"))
    share = _safe_float(rank_row.get("problem_share"))
    critical = _safe_int(rank_row.get("critical_count"))
    score = _safe_int(rank_row.get("score", rank_row.get("health_score")))
    top_theme = str(reason_row.get("топ_тема") or _first_theme(reason_row.get("ключевые_темы", "")))
    top_group = str(reason_row.get("топ_группа", "")).strip()

    crit = f", критических обращений — {critical}" if critical else ""
    theme = f"ключевая тема — «{top_theme}»" if top_theme else "тематика разнородная"
    group = f", группа «{top_group}»" if top_group else ""
    return (
        f"Муниципалитет «{muni}» (скор {score}): {problems} проблемных обращений "
        f"из {total} ({share:.0%}){crit}; {theme}{group}."
    )


def template_municipality_paragraph(rank_row: pd.Series, reason_row: pd.Series | None = None) -> str:
    """Абзац для отчётности / municipality_summaries.xlsx."""
    reason_row = _as_series(reason_row, rank_row)
    muni = str(rank_row.get("муниципалитет", ""))
    rank = _safe_int(rank_row.get("rank"))
    score = _safe_int(rank_row.get("score", rank_row.get("health_score")))
    problems = _safe_int(rank_row.get("problem_count"))
    total = _safe_int(rank_row.get("total_incidents"))
    share = _safe_float(rank_row.get("problem_share"))
    critical = _safe_int(rank_row.get("critical_count"))
    sev = _safe_float(rank_row.get("severity_mean"))
    top_theme = str(reason_row.get("топ_тема") or _first_theme(reason_row.get("ключевые_темы", "")))
    top_group = str(reason_row.get("топ_группа", "")).strip()
    key_themes = str(reason_row.get("ключевые_темы", "")).strip()

    s1 = (
        f"«{muni}» занимает {rank}-е место по индексу проблемности области "
        f"(health score {score} из 100)."
    )
    s2 = (
        f"В выборке {total} обращений, из них {problems} классифицированы как проблемные "
        f"({share:.0%}), средняя тяжесть {sev:.1f} балла"
        + (f", критических (класс 4) — {critical}." if critical else ".")
    )
    s3_parts = []
    if top_theme:
        s3_parts.append(f"Доминирует тема «{top_theme}»")
    if top_group:
        s3_parts.append(f"в группе «{top_group}»")
    if key_themes:
        extras = [t.strip() for t in key_themes.split(";")[1:3] if t.strip()]
        if extras:
            s3_parts.append("также в топе: " + "; ".join(extras))
    s3 = ". ".join(s3_parts) + "." if s3_parts else ""
    return " ".join(x for x in (s1, s2, s3) if x)


def template_top3_paragraph(rank_row: pd.Series, reason_row: pd.Series | None = None) -> str:
    """Развёрнутый абзац для критических Top-3 (отчётность)."""
    reason_row = _as_series(reason_row, rank_row)
    base = template_municipality_paragraph(rank_row, reason_row)
    score = _safe_int(rank_row.get("score", rank_row.get("health_score")))
    critical = _safe_int(rank_row.get("critical_count"))
    top_theme = str(reason_row.get("топ_тема") or _first_theme(reason_row.get("ключевые_темы", "")))
    key_groups = str(reason_row.get("ключевые_группы", "")).strip()

    if score <= 15 or critical >= 3:
        risk = "Статус: критический — требуется оперативное реагирование."
    elif score <= 30:
        risk = "Статус: очень высокий уровень проблемности."
    else:
        risk = "Статус: повышенное внимание руководства."

    rec = (
        f"Приоритетное направление вмешательства — «{top_theme}»"
        + (f" (группа «{key_groups.split(';')[0].split('(')[0].strip()}»)." if key_groups else ".")
    )
    return f"{base} {risk} {rec}"


def enrich_reasons_with_templates(
    reasons_df: pd.DataFrame,
    rankings_df: pd.DataFrame,
) -> pd.DataFrame:
    """summary_text по шаблону для каждого МО из Top-N."""
    if reasons_df.empty:
        return reasons_df
    rank_by_muni = rankings_df.set_index("муниципалитет") if not rankings_df.empty else pd.DataFrame()
    out = reasons_df.copy()
    texts: list[str] = []
    for _, row in out.iterrows():
        muni = row["муниципалитет"]
        rank_row = rank_by_muni.loc[muni] if muni in rank_by_muni.index else row
        texts.append(template_district_sentence(rank_row, row))
    out["summary_text"] = texts
    return out


def build_municipality_summaries_from_templates(
    top_df: pd.DataFrame,
    reasons_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    reason_by_muni = reasons_df.set_index("муниципалитет") if not reasons_df.empty else pd.DataFrame()
    for _, row in top_df.iterrows():
        muni = row["муниципалитет"]
        reason = reason_by_muni.loc[muni] if muni in reason_by_muni.index else None
        rows.append(
            {
                "district_id": int(row["district_id"]),
                "муниципалитет": muni,
                "rank": int(row["rank"]),
                "problem_count": int(row["problem_count"]),
                "summary": template_municipality_paragraph(row, reason),
            }
        )
    return pd.DataFrame(rows)


def build_top3_summaries_from_templates(
    top3_df: pd.DataFrame,
    reasons_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    reason_by_muni = reasons_df.set_index("муниципалитет") if not reasons_df.empty else pd.DataFrame()
    for _, row in top3_df.iterrows():
        muni = row["муниципалитет"]
        reason = reason_by_muni.loc[muni] if muni in reason_by_muni.index else None
        rows.append(
            {
                "district_id": int(row["district_id"]),
                "муниципалитет": muni,
                "rank": int(row["rank"]),
                "problem_count": int(row["problem_count"]),
                "summary": template_top3_paragraph(row, reason),
            }
        )
    return pd.DataFrame(rows)
