"""Загрузка Excel: T,U,V,W + AI (текст) по ТЗ хакатона и альтернативные выгрузки."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# ТЗ / train.xlsx: T=группа тем, U=тема, V=регион, W=муниципалитет, AI=текст
HACKATON_COLUMN_LETTERS = {
    "group": "T",
    "topic": "U",
    "region": "V",
    "municipality": "W",
    "text": "AI",
}

# Выгрузка мониторинга (даты в T,U; W=МО; AC=тип; AI=текст)
MONITORING_COLUMN_LETTERS = {
    "created_at": "T",
    "closed_at": "U",
    "group": "V",
    "municipality": "W",
    "settlement": "X",
    "street": "Y",
    "house": "Z",
    "topic": "AC",
    "tags": "AR",
    "text": "AI",
}

# Legacy: T,U даты; V группа; W тема; Y МО; AI текст
LEGACY_COLUMN_LETTERS = {
    "created_at": "T",
    "closed_at": "U",
    "group": "V",
    "topic": "W",
    "municipality": "Y",
    "settlement": "Z",
    "text": "AI",
}

RENAME_MAP = {
    "created_at": "дата_создания",
    "closed_at": "дата_закрытия",
    "group": "группа",
    "topic": "тема",
    "region": "регион",
    "municipality": "муниципалитет",
    "settlement": "населенный_пункт",
    "street": "улица",
    "house": "дом",
    "tags": "теги",
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


def _row_looks_like_headers(row: pd.Series) -> bool:
    text = " ".join(str(v).lower() for v in row.values)
    return sum(
        m in text
        for m in ("муниципал", "текст", "регион", "улица", "насел", "инцидент", "групп", "тем")
    ) >= 2


def _municipality_signal(series: pd.Series) -> float:
    s = series.astype(str).str.lower().str.strip()
    s = s[s.str.len() > 2]
    if s.empty:
        return 0.0
    return float(s.str.contains(r"район|ский|округ|муниципал|г\.о\.|г о", regex=True).mean())


def _street_signal(series: pd.Series) -> float:
    s = series.astype(str).str.lower().str.strip()
    s = s[s.str.len() > 2]
    if s.empty:
        return 0.0
    return float(
        s.str.contains(
            r"^проспект|^улица|^ул\.|^бульвар|^пер\.|^площадь|^шоссе",
            regex=True,
        ).mean()
    )


def _date_signal(series: pd.Series) -> float:
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return float(parsed.notna().mean())


def _header_row_layout(row: pd.Series) -> dict[str, str] | None:
    """Распознаёт схему по подписи первой строки (T,U,V,W)."""
    idx = {
        "T": excel_col_to_index("T"),
        "U": excel_col_to_index("U"),
        "V": excel_col_to_index("V"),
        "W": excel_col_to_index("W"),
    }
    if max(idx.values()) >= len(row):
        return None
    labels = {k: str(row.iloc[i]).lower() for k, i in idx.items()}
    if "групп" in labels["T"] and "тем" in labels["U"] and "муниципал" in labels["W"]:
        return dict(HACKATON_COLUMN_LETTERS)
    if "создан" in labels["T"] or "дата" in labels["T"]:
        if "муниципал" in labels["W"]:
            return dict(MONITORING_COLUMN_LETTERS)
        if "тем" in labels["W"]:
            return dict(LEGACY_COLUMN_LETTERS)
    return None


def detect_column_layout(df: pd.DataFrame) -> dict[str, str]:
    if len(df) > 0 and _row_looks_like_headers(df.iloc[0]):
        from_header = _header_row_layout(df.iloc[0])
        if from_header is not None:
            return from_header

    start = 1 if len(df) > 1 and _row_looks_like_headers(df.iloc[0]) else 0
    sample = df.iloc[start : start + 500]

    t_idx = excel_col_to_index("T")
    w_idx = excel_col_to_index("W")
    y_idx = excel_col_to_index("Y")
    if w_idx >= df.shape[1]:
        return dict(HACKATON_COLUMN_LETTERS)

    t_dates = _date_signal(sample.iloc[:, t_idx]) if t_idx < df.shape[1] else 0.0
    w_muni = _municipality_signal(sample.iloc[:, w_idx])

    # T — не даты, W — муниципалитеты → формат хакатона (T,U,V,W,AI)
    if t_dates < 0.2 and w_muni >= 0.05:
        return dict(HACKATON_COLUMN_LETTERS)

    if y_idx < df.shape[1]:
        y_muni = _municipality_signal(sample.iloc[:, y_idx])
        y_street = _street_signal(sample.iloc[:, y_idx])
        if w_muni >= 0.08 and w_muni > y_muni:
            return dict(MONITORING_COLUMN_LETTERS)
        if y_street > 0.15 and y_muni < 0.05:
            return dict(MONITORING_COLUMN_LETTERS)
        if y_muni >= 0.08 and w_muni < 0.05:
            return dict(LEGACY_COLUMN_LETTERS)

    return dict(HACKATON_COLUMN_LETTERS)


def _drop_header_row(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) > 1 and _row_looks_like_headers(df.iloc[0]):
        return df.iloc[1:].reset_index(drop=True)
    return df


def _has_named_columns(df: pd.DataFrame) -> bool:
    cols = " ".join(str(c).lower() for c in df.columns)
    markers = ("муниципал", "текст", "регион", "улица", "насел", "инцидент", "групп", "тем")
    return sum(m in cols for m in markers) >= 2


def _load_by_header_names(df: pd.DataFrame) -> pd.DataFrame:
    mapping: dict[str, str] = {}
    for col in df.columns:
        c = str(col).lower()
        if "создан" in c or c in ("t", "дата создания"):
            mapping[col] = "created_at"
        elif "закрыт" in c or c in ("u", "дата закрытия"):
            mapping[col] = "closed_at"
        elif "регион" in c and "муниципал" not in c:
            mapping[col] = "region"
        elif "групп" in c and "group" not in mapping.values():
            mapping[col] = "group"
        elif "муниципал" in c:
            mapping[col] = "municipality"
        elif "насел" in c:
            mapping[col] = "settlement"
        elif re.search(r"\bулиц", c):
            mapping[col] = "street"
        elif c in ("дом", "house") or c.startswith("дом "):
            mapping[col] = "house"
        elif "тип инц" in c or "тип обращ" in c:
            mapping[col] = "topic"
        elif "тег" in c:
            mapping[col] = "tags"
        elif "тем" in c and "topic" not in mapping.values():
            mapping[col] = "topic"
        elif "текст" in c and "инцидент" in c:
            mapping[col] = "text"
        elif "текст" in c or "обращен" in c or c in ("ai", "ak"):
            mapping[col] = "text"

    out = df.rename(columns=mapping)
    return _normalize_loaded(out)


def _load_by_column_letters(df: pd.DataFrame) -> pd.DataFrame:
    layout = detect_column_layout(df)
    indices: dict[str, int] = {}
    for key, letter in layout.items():
        indices[key] = excel_col_to_index(letter)
    indices["text"] = excel_col_to_index("AI")

    max_idx = max(indices.values())
    if df.shape[1] <= max_idx:
        raise ValueError(
            f"В файле {df.shape[1]} колонок, нужна колонка с индексом {max_idx}."
        )

    data = {key: df.iloc[:, idx] for key, idx in indices.items()}
    out = pd.DataFrame(data)
    if "region" in layout and "created_at" not in layout:
        out.attrs["column_layout"] = "hackathon"
    elif layout.get("municipality") == "W" and "created_at" in layout:
        out.attrs["column_layout"] = "monitoring_export"
    else:
        out.attrs["column_layout"] = "legacy"
    return _normalize_loaded(out)


def _normalize_loaded(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in ("group", "topic", "tags", "region"):
        if col not in out.columns:
            out[col] = ""
    if out["topic"].astype(str).str.strip().eq("").all() and "tags" in out.columns:
        out["topic"] = out["tags"].where(out["topic"].eq(""), out["topic"])

    required = ("municipality", "text")
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(f"Не найдены обязательные поля: {missing}")

    str_cols = (
        "created_at",
        "closed_at",
        "group",
        "topic",
        "region",
        "municipality",
        "settlement",
        "street",
        "house",
        "tags",
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
    if "дата_создания" in out.columns:
        out["Дата создания"] = out["дата_создания"]
    elif "Дата создания" not in out.columns:
        out["Дата создания"] = ""
    return out


def describe_column_layout(df: pd.DataFrame) -> dict[str, str]:
    layout = detect_column_layout(df)
    labels = {
        "group": "группа тем (T)",
        "topic": "тема (U)",
        "region": "регион (V)",
        "municipality": "муниципалитет (W)",
        "created_at": "дата создания (T)",
        "closed_at": "дата закрытия (U)",
        "text": "текст инцидента (AI)",
    }
    result = {labels.get(k, k): letter for k, letter in layout.items()}
    result["текст инцидента"] = "AI"
    return result
