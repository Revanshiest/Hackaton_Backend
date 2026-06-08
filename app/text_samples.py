"""Выборка текстов обращений для справок."""

from __future__ import annotations

import pandas as pd


def truncate_text(text: str, max_len: int = 220) -> str:
    s = " ".join(str(text).split())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def sample_problem_texts(
    problems: pd.DataFrame,
    muni: str,
    n: int = 3,
    max_len: int = 220,
) -> list[str]:
    if problems.empty or "текст" not in problems.columns:
        return []
    sub = problems.loc[problems["муниципалитет"].astype(str) == str(muni)].copy()
    sub = sub[sub["текст"].astype(str).str.len() > 12]
    if sub.empty:
        return []
    if "severity" in sub.columns:
        sub = sub.sort_values("severity", ascending=False)
    seen: set[str] = set()
    out: list[str] = []
    for raw in sub["текст"].astype(str):
        norm = raw.strip().lower()[:80]
        if norm in seen:
            continue
        seen.add(norm)
        out.append(truncate_text(raw, max_len))
        if len(out) >= n:
            break
    return out
