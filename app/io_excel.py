"""Загрузка Excel: выгрузка мониторинга (T, U, V, W, Y, Z, AK) и именованные колонки."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# Колонки по ТЗ: T, U, V, W, Y, Z, AK
COLUMN_LETTERS = {
    "created_at": "T",
    "closed_at": "U",
    "group": "V",
    "topic": "W",
    "municipality": "Y",
    "settlement": "Z",
    "text": "AK",
}

TEXT_COLUMN_ALIASES = ("AI", "AK")

RENAME_MAP = {
    "created_at": "дата_создания",
    "closed_at": "дата_закрытия",
    "group": "группа",
    "topic": "тема",
    "municipality": "муниципалитет",
    "settlement": "населенный_пункт",
    "text": "текст",
}

INFERENCE_COLUMNS = {
    "группа": "Группа тем",
    "тема": "Тема",
    "текст": "Текст инцидента",
    "дата_создания": "Дата создания",
}


def excel_col_to_index(letters: str) -> int:
    n = 0
    for ch in letters.upper().strip():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def _text_density_score(df: pd.DataFrame, col_idx: int) -> int:
    if col_idx >= df.shape[1]:
        return -1
    col = (
        df.iloc[:, col_idx]
        .astype(str)
        .replace({"nan": "", "None": "", "<NA>": ""})
        .str.strip()
    )
    return int((col.str.len() > 10).sum())


def _resolve_text_column_index(df: pd.DataFrame) -> int:
    scores = {
        letter: _text_density_score(df, excel_col_to_index(letter))
        for letter in TEXT_COLUMN_ALIASES
    }
    best = max(scores, key=scores.get)
    if scores[best] >= 0:
        return excel_col_to_index(best)
    return excel_col_to_index(COLUMN_LETTERS["text"])


def _row_looks_like_headers(row: pd.Series) -> bool:
    text = " ".join(str(v).lower() for v in row.values)
    return sum(
        m in text
        for m in ("муниципал", "текст", "регион", "насел", "инцидент", "групп", "тем")
    ) >= 2


def _drop_header_row(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) > 1 and _row_looks_like_headers(df.iloc[0]):
        return df.iloc[1:].reset_index(drop=True)
    return df


def _has_named_columns(df: pd.DataFrame) -> bool:
    cols = " ".join(str(c).lower() for c in df.columns)
    markers = ("муниципал", "текст", "регион", "насел", "инцидент", "групп", "тем")
    return sum(m in cols for m in markers) >= 2


def _load_by_header_names(df: pd.DataFrame) -> pd.DataFrame:
    mapping: dict[str, str] = {}
    for col in df.columns:
        c = str(col).lower()
        if "создан" in c or c in ("t", "дата создания"):
            mapping[col] = "created_at"
        elif "закрыт" in c or c in ("u", "дата закрытия"):
            mapping[col] = "closed_at"
        elif "групп" in c and "group" not in mapping.values():
            mapping[col] = "group"
        elif "тем" in c and "topic" not in mapping.values():
            mapping[col] = "topic"
        elif "муниципал" in c:
            mapping[col] = "municipality"
        elif "насел" in c:
            mapping[col] = "settlement"
        elif "текст" in c and "инцидент" in c:
            mapping[col] = "text"
        elif "текст" in c or "обращен" in c or c in ("ai", "ak"):
            mapping[col] = "text"

    out = df.rename(columns=mapping)
    return _normalize_loaded(out)


def _load_by_column_letters(df: pd.DataFrame) -> pd.DataFrame:
    indices: dict[str, int] = {}
    for key, letter in COLUMN_LETTERS.items():
        indices[key] = excel_col_to_index(letter)
    indices["text"] = _resolve_text_column_index(df)

    max_idx = max(indices.values())
    if df.shape[1] <= max_idx:
        raise ValueError(
            f"В файле {df.shape[1]} колонок, нужна колонка с индексом {max_idx}."
        )

    data = {key: df.iloc[:, idx] for key, idx in indices.items()}
    out = pd.DataFrame(data)
    return _normalize_loaded(out)


def _normalize_loaded(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in ("group", "topic"):
        if col not in out.columns:
            out[col] = ""

    required = ("municipality", "text")
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(f"Не найдены обязательные поля: {missing}")

    str_cols = (
        "created_at",
        "closed_at",
        "group",
        "topic",
        "municipality",
        "settlement",
        "text",
    )
    for col in str_cols:
        if col in out.columns:
            out[col] = out[col].astype(str).replace({"nan": "", "None": ""}).str.strip()

    out = out.rename(columns={k: v for k, v in RENAME_MAP.items() if k in out.columns})
    out["row_id"] = range(len(out))
    return out


def load_incidents(path: Path | str, header_row: int | None = None) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    if header_row is None:
        raw = pd.read_excel(path, header=None, engine="openpyxl")
        raw = _drop_header_row(raw)
        return _load_by_column_letters(raw)

    raw = pd.read_excel(path, header=header_row, engine="openpyxl")
    if _has_named_columns(raw):
        return _load_by_header_names(raw)
    return _load_by_column_letters(raw)


def to_inference_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Приводит внутренние колонки к формату ONNX-модели."""
    out = df.copy()
    for src, dst in INFERENCE_COLUMNS.items():
        if src in out.columns:
            out[dst] = out[src]
        elif dst not in out.columns:
            out[dst] = ""
    return out
