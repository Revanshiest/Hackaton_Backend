"""Загрузка Excel: T,U,V,W + AI (текст) по ТЗ хакатона и альтернативные выгрузки."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd

LAYOUT_PREVIEW_ROWS = 501

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

# Выгрузка кабинета: R/S — даты, T,U,V,W — тема/МО, AI — текст
CABINET_EXPORT_COLUMN_LETTERS = {
    "created_at": "R",
    "closed_at": "S",
    "group": "T",
    "topic": "U",
    "region": "V",
    "municipality": "W",
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


def _resolve_excel_engine() -> str:
    """calamine (Rust) обычно в 3–5× быстрее openpyxl на больших .xlsx."""
    pref = os.environ.get("EXCEL_ENGINE", "auto").strip().lower()
    if pref == "openpyxl":
        return "openpyxl"
    if pref == "calamine":
        return "calamine"
    try:
        import python_calamine  # noqa: F401

        return "calamine"
    except ImportError:
        return "openpyxl"


def _layout_usecols(layout: dict[str, str]) -> list[int]:
    letters = set(layout.values())
    letters.add("AI")
    return sorted(excel_col_to_index(letter) for letter in letters)


def _column_layout_attr(layout: dict[str, str]) -> str:
    if layout.get("created_at") == "R":
        return "cabinet_export"
    if "region" in layout and "created_at" not in layout:
        return "hackathon"
    if layout.get("municipality") == "W" and "created_at" in layout:
        return "monitoring_export"
    return "legacy"


def _dataframe_from_layout(raw: pd.DataFrame, layout: dict[str, str], usecols: list[int]) -> pd.DataFrame:
    pos = {idx: i for i, idx in enumerate(usecols)}
    data = {key: raw.iloc[:, pos[excel_col_to_index(letter)]] for key, letter in layout.items()}
    data["text"] = raw.iloc[:, pos[excel_col_to_index("AI")]]
    out = pd.DataFrame(data)
    out.attrs["column_layout"] = _column_layout_attr(layout)
    return out


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


def _is_named_export_header(row: pd.Series) -> bool:
    """Строка заголовков выгрузки кабинета (Дата создания, Текст инцидента, …)."""
    text = " ".join(str(v).lower() for v in row.values)
    has_dates = "дата создания" in text
    has_body = sum(
        m in text for m in ("муниципал", "текст инцидента", "группа тем", "номер инцидента")
    ) >= 2
    return has_dates and has_body


def _header_row_layout(row: pd.Series) -> dict[str, str] | None:
    """Распознаёт схему по подписи первой строки (T,U,V,W,R)."""
    idx = {
        "R": excel_col_to_index("R"),
        "T": excel_col_to_index("T"),
        "U": excel_col_to_index("U"),
        "V": excel_col_to_index("V"),
        "W": excel_col_to_index("W"),
    }
    if max(idx.values()) >= len(row):
        return None
    labels = {k: str(row.iloc[i]).lower() for k, i in idx.items()}
    if "дата создания" in labels.get("R", ""):
        return dict(CABINET_EXPORT_COLUMN_LETTERS)
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

    r_idx = excel_col_to_index("R")
    t_idx = excel_col_to_index("T")
    w_idx = excel_col_to_index("W")
    y_idx = excel_col_to_index("Y")
    if w_idx >= df.shape[1]:
        return dict(HACKATON_COLUMN_LETTERS)

    r_dates = _date_signal(sample.iloc[:, r_idx]) if r_idx < df.shape[1] else 0.0
    t_dates = _date_signal(sample.iloc[:, t_idx]) if t_idx < df.shape[1] else 0.0
    w_muni = _municipality_signal(sample.iloc[:, w_idx])

    # R — даты создания, T — группы тем → выгрузка кабинета
    if r_dates >= 0.3 and t_dates < 0.2:
        return dict(CABINET_EXPORT_COLUMN_LETTERS)

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
    if len(df) > 1 and _row_looks_like_headers(df.iloc[0]) and not _is_named_export_header(df.iloc[0]):
        return df.iloc[1:].reset_index(drop=True)
    return df


def _has_named_columns(df: pd.DataFrame) -> bool:
    cols = " ".join(str(c).lower() for c in df.columns)
    markers = ("муниципал", "текст", "регион", "улица", "насел", "инцидент", "групп", "тем", "дата создания")
    return sum(m in cols for m in markers) >= 2


def _load_by_header_names(df: pd.DataFrame) -> pd.DataFrame:
    mapping: dict[str, str] = {}
    for col in df.columns:
        c = str(col).lower().strip()
        c_compact = c.replace(" ", "")
        if c_compact == "датасоздания" or c == "дата создания":
            mapping[col] = "created_at"
        elif c_compact in ("датаокончания", "датазакрытия") or c in ("дата окончания", "дата закрытия"):
            mapping[col] = "closed_at"
        elif "закрыт" in c and "дата" in c:
            mapping[col] = "closed_at"
        elif c in ("t",):
            mapping[col] = "created_at"
        elif c in ("u",):
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
        elif c == "тема":
            mapping[col] = "topic"
        elif ("тип инц" in c or "тип обращ" in c) and "topic" not in mapping.values():
            mapping[col] = "topic"
        elif "тег" in c:
            mapping[col] = "tags"
        elif "тем" in c and "topic" not in mapping.values():
            mapping[col] = "topic"
        elif c == "текст инцидента" or ("текст" in c and "инцидент" in c and "ответ" not in c):
            mapping[col] = "text"
        elif c in ("ai", "ak"):
            mapping[col] = "text"

    out = df.rename(columns=mapping)
    return _normalize_loaded(out)


def _load_by_column_letters(df: pd.DataFrame) -> pd.DataFrame:
    layout = detect_column_layout(df)
    usecols = _layout_usecols(layout)
    max_idx = max(usecols)
    if df.shape[1] <= max_idx:
        raise ValueError(
            f"В файле {df.shape[1]} колонок, нужна колонка с индексом {max_idx}."
        )
    return _normalize_loaded(_dataframe_from_layout(df, layout, usecols))


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

    engine = _resolve_excel_engine()

    if header_row is None:
        preview = pd.read_excel(
            path,
            header=None,
            engine=engine,
            nrows=LAYOUT_PREVIEW_ROWS,
        )
        if len(preview) > 0 and _is_named_export_header(preview.iloc[0]):
            raw = pd.read_excel(path, header=0, engine=engine)
            if _has_named_columns(raw):
                out = _load_by_header_names(raw)
                out.attrs["column_layout"] = "cabinet_export"
                return out

        preview = _drop_header_row(preview)
        layout = detect_column_layout(preview)
        usecols = _layout_usecols(layout)
        raw = pd.read_excel(path, header=None, engine=engine, usecols=usecols)
        raw = _drop_header_row(raw)
        return _normalize_loaded(_dataframe_from_layout(raw, layout, usecols))

    raw = pd.read_excel(path, header=header_row, engine=engine)
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
        "created_at": "дата создания (R/T)",
        "closed_at": "дата закрытия (S/U)",
        "text": "текст инцидента (AI)",
    }
    result = {labels.get(k, k): letter for k, letter in layout.items()}
    result["текст инцидента"] = "AI"
    return result
