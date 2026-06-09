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

INCIDENT_COLUMNS = tuple(RENAME_MAP.values()) + ("row_id",)
LABEL_COLUMNS = ("Метка_Класса", "Уровень_тяжести", "Уверенность", "severity", "is_problem")
LABELED_COLUMNS = INCIDENT_COLUMNS + LABEL_COLUMNS
ALLOWED_INTERNAL = frozenset(RENAME_MAP.keys())

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


def _is_response_time_column(name: str) -> bool:
    c = str(name).lower().strip()
    return "время" in c and ("ответ" in c or "перв" in c)


def _map_header_column(col: str, mapping: dict[str, str]) -> str | None:
    """Сопоставляет заголовок Excel с внутренним полем; None — колонку игнорируем."""
    c = str(col).lower().strip()
    c_compact = c.replace(" ", "")

    if _is_response_time_column(c):
        return None
    if c_compact == "датасоздания" or c == "дата создания":
        return "created_at"
    if c_compact in ("датаокончания", "датазакрытия") or c in ("дата окончания", "дата закрытия"):
        return "closed_at"
    if "закрыт" in c and "дата" in c:
        return "closed_at"
    if c in ("t",):
        return "created_at"
    if c in ("u",):
        return "closed_at"
    if "регион" in c and "муниципал" not in c:
        return "region"
    if "групп" in c and "group" not in mapping.values():
        return "group"
    if "муниципал" in c:
        return "municipality"
    if "насел" in c:
        return "settlement"
    if re.search(r"\bулиц", c):
        return "street"
    if c in ("дом", "house") or c.startswith("дом "):
        return "house"
    if c == "тема" or c.startswith("тема "):
        return "topic"
    if ("тип инц" in c or "тип обращ" in c) and "topic" not in mapping.values():
        return "topic"
    if "тег" in c:
        return "tags"
    if c == "текст инцидента" or ("текст" in c and "инцидент" in c and "ответ" not in c):
        return "text"
    if c in ("ai", "ak"):
        return "text"
    return None


def _load_cabinet_export(path: Path, engine: str) -> pd.DataFrame:
    """Выгрузка кабинета: только R,S,T,U,V,W,AI — дата создания строго из колонки R."""
    layout = dict(CABINET_EXPORT_COLUMN_LETTERS)
    usecols = _layout_usecols(layout)
    raw = pd.read_excel(path, header=0, engine=engine, usecols=usecols)
    out = _normalize_loaded(_dataframe_from_layout(raw, layout, usecols))
    out.attrs["column_layout"] = "cabinet_export"
    return out


def _load_by_header_names(df: pd.DataFrame) -> pd.DataFrame:
    mapping: dict[str, str] = {}
    for col in df.columns:
        target = _map_header_column(col, mapping)
        if target is None:
            continue
        if target in mapping.values():
            continue
        mapping[col] = target

    if not mapping:
        raise ValueError("Не удалось сопоставить колонки Excel с полями инцидента")

    out = df.rename(columns=mapping)
    out = out[[c for c in out.columns if c in ALLOWED_INTERNAL]]
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
    keep = [c for c in LABELED_COLUMNS if c in out.columns and c != "row_id"]
    out = out[keep]
    out["row_id"] = range(len(out))
    return out


def select_labeled_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Оставляет только канонические колонки инцидента и разметки."""
    keep = [c for c in LABELED_COLUMNS if c in df.columns]
    return df[keep].copy() if keep else df.copy()


def parquet_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Приводит DataFrame к типам, совместимым с pyarrow/parquet."""
    out = select_labeled_columns(df)
    for col in out.columns:
        if col in ("row_id", "severity", "Метка_Класса") or col == "is_problem":
            continue
        if pd.api.types.is_bool_dtype(out[col]):
            continue
        if pd.api.types.is_numeric_dtype(out[col]):
            continue
        out[col] = out[col].map(lambda x: "" if pd.isna(x) else str(x))
    return out


def read_labeled_parquet(path: Path | str) -> pd.DataFrame:
    """Читает labeled.parquet, не загружая лишние колонки (важно для старых файлов)."""
    import pyarrow.parquet as pq

    path = Path(path)
    pf = pq.ParquetFile(path)
    names = [name for name in pf.schema_arrow.names if name in LABELED_COLUMNS]
    if not names:
        raise ValueError(f"В {path} нет известных колонок разметки")
    return pf.read(columns=names).to_pandas()


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
            return _load_cabinet_export(path, engine)

        preview = _drop_header_row(preview)
        layout = detect_column_layout(preview)
        if layout.get("created_at") == "R":
            return _load_cabinet_export(path, engine)
        usecols = _layout_usecols(layout)
        raw = pd.read_excel(path, header=None, engine=engine, usecols=usecols)
        raw = _drop_header_row(raw)
        return _normalize_loaded(_dataframe_from_layout(raw, layout, usecols))

    raw = pd.read_excel(path, header=header_row, engine=engine)
    if _has_named_columns(raw):
        if header_row == 0 and len(raw) > 0:
            first = " ".join(str(v).lower() for v in raw.columns)
            if "дата создания" in first and "текст инцидента" in first:
                return _load_cabinet_export(path, engine)
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
