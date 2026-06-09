"""PDF-отчёт для ведомства по муниципалитету (шаблон, без LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.agency_mapping import region_name
from app.pdf_report import (
    CONTENT_W,
    _build_pdf,
    _hex,
    _para,
    _section_heading,
    _severity_chart,
    _styles,
    _table_base,
)
from app.report import SEVERITY_LABELS
from schemas import SeverityStat


@dataclass
class AgencyReportContext:
    municipality: str
    agency: str
    period_start: str | None
    period_end: str | None
    counts: dict[int, int]  # severity 1-4
    top_topics: list[tuple[str, int]]


def _format_period(start: str | None, end: str | None) -> str:
    if start and end:
        return f"{start} — {end}"
    if start:
        return f"с {start}"
    if end:
        return f"по {end}"
    return "период не указан"


def _summary_text(ctx: AgencyReportContext) -> str:
    high = ctx.counts.get(4, 0) + ctx.counts.get(3, 0)
    low = ctx.counts.get(2, 0) + ctx.counts.get(1, 0)
    total = high + low
    if total == 0:
        return (
            f"По муниципалитету «{ctx.municipality}» в зоне ответственности "
            f"«{ctx.agency}» за указанный период проблемных обращений "
            f"(классы 1–4) не зафиксировано."
        )
    high_pct = round(100 * high / total)
    low_pct = 100 - high_pct
    return (
        f"В муниципалитете «{ctx.municipality}» по направлению «{ctx.agency}» "
        f"за период {_format_period(ctx.period_start, ctx.period_end)} "
        f"учтено {total} проблемных обращений (класс 0 не учитывается). "
        f"Критичные проблемы (классы 3–4): {high} ({high_pct}%), "
        f"прочие проблемы (классы 1–2): {low} ({low_pct}%). "
        f"Подробный перечень обращений классов 3 и 4 приведён в приложении (Excel)."
    )


def build_agency_pdf(ctx: AgencyReportContext) -> bytes:
    styles = _styles()
    story: list = []

    story.append(_para("ZeroProblems", styles["brand"]))
    story.append(Spacer(1, 2 * mm))
    story.append(_para("Отчёт для ведомства", styles["title"]))
    story.append(_para(ctx.agency, styles["subtitle"]))
    story.append(Spacer(1, 4 * mm))

    meta_rows = [
        [_para("Регион", styles["table_cell"]), _para(region_name(), styles["table_cell"])],
        [_para("Муниципалитет", styles["table_cell"]), _para(ctx.municipality, styles["table_cell"])],
        [_para("Период", styles["table_cell"]), _para(_format_period(ctx.period_start, ctx.period_end), styles["table_cell"])],
        [
            _para("Дата формирования", styles["table_cell"]),
            _para(datetime.now().strftime("%d.%m.%Y %H:%M"), styles["table_cell"]),
        ],
    ]
    meta_table = Table(meta_rows, colWidths=[38 * mm, CONTENT_W - 38 * mm])
    meta_table.setStyle(TableStyle(_table_base(zebra=False)))
    story.append(meta_table)
    story.append(Spacer(1, 6 * mm))

    story.append(_section_heading("Сводка", styles))
    story.append(Spacer(1, 2 * mm))
    story.append(_para(_summary_text(ctx), styles["body"]))
    story.append(Spacer(1, 5 * mm))

    counts_rows = [
        [_para("Класс", styles["table_cell"]), _para("Уровень", styles["table_cell"]), _para("Кол-во", styles["table_cell_center"])],
    ]
    for sev in (4, 3, 2, 1):
        counts_rows.append(
            [
                _para(str(sev), styles["table_cell_center"]),
                _para(SEVERITY_LABELS[sev], styles["table_cell"]),
                _para(str(ctx.counts.get(sev, 0)), styles["table_cell_center"]),
            ]
        )
    counts_table = Table(counts_rows, colWidths=[18 * mm, 55 * mm, CONTENT_W - 73 * mm])
    style = _table_base(header=True)
    style.append(("ALIGN", (0, 0), (0, -1), "CENTER"))
    style.append(("ALIGN", (2, 0), (2, -1), "CENTER"))
    counts_table.setStyle(TableStyle(style))
    story.append(counts_table)
    story.append(Spacer(1, 5 * mm))

    severity_stats = []
    total_sev = sum(ctx.counts.get(sev, 0) for sev in range(1, 5)) or 1
    for sev in range(1, 5):
        count = ctx.counts.get(sev, 0)
        severity_stats.append(
            SeverityStat(
                severity=sev,
                label=SEVERITY_LABELS[sev],
                count=count,
                percentage=round(100 * count / total_sev, 1),
            )
        )
    chart = _severity_chart(severity_stats, CONTENT_W / mm)
    if chart is not None:
        story.append(_section_heading("Распределение по классам", styles))
        story.append(Spacer(1, 2 * mm))
        story.append(chart)
        story.append(Spacer(1, 4 * mm))

    if ctx.top_topics:
        story.append(_section_heading("Основные темы", styles))
        story.append(Spacer(1, 2 * mm))
        topic_rows = [[_para("Тема", styles["table_cell"]), _para("Обращений", styles["table_cell_center"])]]
        for topic, count in ctx.top_topics[:10]:
            topic_rows.append(
                [
                    _para(topic, styles["table_cell"]),
                    _para(str(count), styles["table_cell_center"]),
                ]
            )
        topics_table = Table(topic_rows, colWidths=[CONTENT_W - 28 * mm, 28 * mm])
        t_style = _table_base(header=True)
        t_style.append(("ALIGN", (1, 0), (1, -1), "CENTER"))
        topics_table.setStyle(TableStyle(t_style))
        story.append(topics_table)

    title = f"Отчёт — {ctx.agency} — {ctx.municipality}"
    return _build_pdf(story, title)
