"""ZIP-архив отчётов для ведомств по муниципалитетам."""

from __future__ import annotations

import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pandas as pd

from app.agency_mapping import resolve_agency, safe_path_segment
from app.agency_pdf import AgencyReportContext, build_agency_pdf
from app.report import DATE_COLUMN_CANDIDATES, SEVERITY_LABELS, _parse_date_column, compute_incident_date_range

ProgressCallback = Callable[[int, int, str, str, str], None]

EXCEL_COLUMNS = [
    ("дата_создания", "Дата создания"),
    ("severity", "Класс"),
    ("Уровень_тяжести", "Уровень тяжести"),
    ("группа", "Группа тем"),
    ("тема", "Тема"),
    ("муниципалитет", "Муниципалитет"),
    ("текст", "Текст обращения"),
    ("row_id", "ID"),
]


def _attach_agency(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "группа" not in out.columns:
        out["группа"] = ""
    out["ведомство"] = out["группа"].map(lambda g: resolve_agency(str(g)))
    return out


def _severity_counts(sub: pd.DataFrame) -> dict[int, int]:
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    if sub.empty or "severity" not in sub.columns:
        return counts
    for sev in counts:
        counts[sev] = int((sub["severity"] == sev).sum())
    return counts


def _top_topics(sub: pd.DataFrame, limit: int = 10) -> list[tuple[str, int]]:
    if sub.empty or "тема" not in sub.columns:
        return []
    vc = sub["тема"].astype(str).str.strip().value_counts()
    return [(str(name), int(cnt)) for name, cnt in vc.head(limit).items() if str(name).strip()]


def _format_date(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    text = str(value).strip()
    return text[:10] if text else None


def _build_excel_bytes(rows: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    export = rows.copy()
    if "severity" in export.columns:
        def _severity_label(value):
            try:
                return SEVERITY_LABELS.get(int(value), value)
            except (TypeError, ValueError):
                return value

        export["severity"] = export["severity"].map(_severity_label)

    cols = [c for c, _ in EXCEL_COLUMNS if c in export.columns]
    headers = {c: h for c, h in EXCEL_COLUMNS if c in export.columns}
    export = export[cols].rename(columns=headers)

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export.to_excel(writer, sheet_name="Обращения_3_4", index=False)
    return buffer.getvalue()


@dataclass
class AgencyWorkItem:
    municipality: str
    agency: str
    agency_df: pd.DataFrame


def _prepare_problems(labeled_df: pd.DataFrame) -> pd.DataFrame:
    if labeled_df is None or labeled_df.empty:
        raise ValueError("Нет данных для формирования отчётов")

    df = _attach_agency(labeled_df)
    if "муниципалитет" not in df.columns:
        raise ValueError("В данных отсутствует колонка «муниципалитет»")
    if "severity" not in df.columns:
        raise ValueError("В данных отсутствует колонка «severity»")

    problems = df[df["severity"].isin([1, 2, 3, 4])].copy()
    if problems.empty:
        raise ValueError("Нет проблемных обращений (классы 1–4)")
    return problems


def _iter_work_items(problems: pd.DataFrame) -> list[AgencyWorkItem]:
    items: list[AgencyWorkItem] = []
    for muni, muni_df in problems.groupby("муниципалитет", sort=True):
        muni_name = str(muni).strip()
        for agency, agency_df in muni_df.groupby("ведомство", sort=True):
            agency_name = str(agency).strip()
            if agency_df.empty:
                continue
            items.append(
                AgencyWorkItem(
                    municipality=muni_name,
                    agency=agency_name,
                    agency_df=agency_df,
                )
            )
    return items


def build_department_preview(labeled_df: pd.DataFrame) -> dict[str, Any]:
    problems = _prepare_problems(labeled_df)
    period_start, period_end = compute_incident_date_range(problems)

    municipalities: list[dict[str, Any]] = []
    agencies_count = 0

    for muni, muni_df in problems.groupby("муниципалитет", sort=True):
        muni_name = str(muni).strip()
        agencies: list[dict[str, Any]] = []
        for agency, agency_df in muni_df.groupby("ведомство", sort=True):
            agency_name = str(agency).strip()
            if agency_df.empty:
                continue
            counts = _severity_counts(agency_df)
            critical = counts[3] + counts[4]
            total = sum(counts.values())
            agencies.append(
                {
                    "name": agency_name,
                    "total_count": total,
                    "critical_count": critical,
                    "counts": {str(k): v for k, v in counts.items()},
                }
            )
            agencies_count += 1
        if agencies:
            municipalities.append({"name": muni_name, "agencies": agencies})

    return {
        "municipalities_count": len(municipalities),
        "agencies_count": agencies_count,
        "reports_count": agencies_count,
        "period_start": _format_date(period_start),
        "period_end": _format_date(period_end),
        "municipalities": municipalities,
    }


def _sort_by_date(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    date_col = next((c for c in DATE_COLUMN_CANDIDATES if c in df.columns), None)
    if not date_col:
        return df
    out = df.copy()
    out["_sort_date"] = _parse_date_column(out[date_col])
    out = out.sort_values("_sort_date", ascending=True, na_position="last").drop(columns=["_sort_date"])
    return out


def build_department_reports_zip(
    labeled_df: pd.DataFrame,
    *,
    on_progress: ProgressCallback | None = None,
) -> bytes:
    """Формирует ZIP: {МО}/{ведомство}/report.pdf + incidents.xlsx."""
    problems = _prepare_problems(labeled_df)
    work_items = _iter_work_items(problems)
    if not work_items:
        raise ValueError("Нет отчётов для формирования")

    period_start, period_end = compute_incident_date_range(problems)
    period_start_s = _format_date(period_start)
    period_end_s = _format_date(period_end)
    total = len(work_items)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, item in enumerate(work_items, start=1):
            if on_progress:
                on_progress(idx, total, item.municipality, item.agency, "pdf")
            muni_dir = safe_path_segment(item.municipality)
            agency_dir = safe_path_segment(item.agency)
            base = f"{muni_dir}/{agency_dir}/"

            counts = _severity_counts(item.agency_df)
            ctx = AgencyReportContext(
                municipality=item.municipality,
                agency=item.agency,
                period_start=period_start_s,
                period_end=period_end_s,
                counts=counts,
                top_topics=_top_topics(item.agency_df),
            )
            pdf_bytes = build_agency_pdf(ctx)
            zf.writestr(f"{base}report.pdf", pdf_bytes)

            if on_progress:
                on_progress(idx, total, item.municipality, item.agency, "excel")
            critical = item.agency_df[item.agency_df["severity"].isin([3, 4])]
            critical = _sort_by_date(critical)
            excel_bytes = _build_excel_bytes(critical)
            zf.writestr(f"{base}incidents.xlsx", excel_bytes)

        if on_progress:
            on_progress(total, total, "", "", "archive")

    return buffer.getvalue()
