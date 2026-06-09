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


def select_diverse_examples(
    candidates: list[dict],
    n: int = 6,
    *,
    min_len: int = 40,
    max_len: int | None = None,
) -> list[dict]:
    """Выбрать до n примеров, по возможности с разными уровнями тяжести."""
    pool: list[dict] = []
    seen: set[str] = set()
    for item in candidates:
        raw = clean_appeal_text(str(item.get("text", "")))
        if len(raw) < min_len:
            continue
        norm = raw.lower()[:80]
        if norm in seen:
            continue
        seen.add(norm)
        sev = int(item.get("severity", 0) or 0)
        if sev <= 0:
            continue
        pool.append(
            {
                "text": raw if max_len is None else truncate_text(raw, max_len),
                "severity": sev,
                "label": str(item.get("label") or SEVERITY_LABELS.get(sev, str(sev))),
            }
        )

    if not pool:
        return []

    by_severity: dict[int, list[dict]] = {}
    for item in pool:
        by_severity.setdefault(item["severity"], []).append(item)

    severities = sorted(by_severity.keys(), reverse=True)
    out: list[dict] = []

    for sev in severities:
        if len(out) >= n:
            break
        if by_severity[sev]:
            out.append(by_severity[sev].pop(0))

    while len(out) < n:
        added = False
        for sev in severities:
            if len(out) >= n:
                break
            if by_severity[sev]:
                out.append(by_severity[sev].pop(0))
                added = True
        if not added:
            break
    return out


def sample_problem_texts(
    problems: pd.DataFrame,
    muni: str,
    n: int = 6,
    max_len: int | None = None,
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

    pool: list[dict] = []
    seen: set[str] = set()
    for _, row in sub.iterrows():
        raw = clean_appeal_text(row["текст"])
        norm = raw.lower()[:80]
        if norm in seen:
            continue
        seen.add(norm)
        sev = int(row["severity"]) if "severity" in sub.columns else 1
        pool.append(
            {
                "text": raw,
                "severity": sev,
                "label": SEVERITY_LABELS.get(sev, str(sev)),
            }
        )
    return select_diverse_examples(pool, n, min_len=min_len, max_len=max_len)
