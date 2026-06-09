"""Выборка текстов обращений для справок."""

from __future__ import annotations

import re

import pandas as pd

SEVERITY_LABELS: dict[int, str] = {
    0: "Не инцидент",
    1: "Низкая",
    2: "Средняя",
    3: "Высокая",
    4: "Критическая",
}


def clean_appeal_text(text: str) -> str:
    s = str(text)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.strip().lstrip("'\"«»")
    return " ".join(s.split())


def truncate_text(text: str, max_len: int = 220) -> str:
    s = clean_appeal_text(text)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def sample_problem_texts(
    problems: pd.DataFrame,
    muni: str,
    n: int = 3,
    max_len: int = 500,
    min_len: int = 40,
) -> list[dict]:
    if problems.empty or "текст" not in problems.columns:
        return []
    sub = problems.loc[problems["муниципалитет"].astype(str) == str(muni)].copy()
    if "severity" in sub.columns:
        sub = sub[sub["severity"].fillna(0) > 0]
    sub = sub[sub["текст"].astype(str).map(lambda t: len(clean_appeal_text(t)) >= min_len)]
    if sub.empty:
        return []
    if "severity" in sub.columns:
        sub = sub.sort_values("severity", ascending=False)
    seen: set[str] = set()
    out: list[dict] = []
    for _, row in sub.iterrows():
        raw = clean_appeal_text(row["текст"])
        norm = raw.lower()[:80]
        if norm in seen:
            continue
        seen.add(norm)
        sev = int(row["severity"]) if "severity" in sub.columns else 1
        out.append(
            {
                "text": truncate_text(raw, max_len),
                "severity": sev,
                "label": SEVERITY_LABELS.get(sev, str(sev)),
            }
        )
        if len(out) >= n:
            break
    return out
