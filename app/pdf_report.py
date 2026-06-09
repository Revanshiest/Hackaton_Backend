"""PDF-отчёт по муниципалитету: текст, таблицы, графики matplotlib."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.pdf_map import render_region_map_figure
from schemas import DistrictReport, IncidentExample, SeverityStat, ThematicGroupStat

FONT_REG = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
BRAND_NAME = "ZeroProblems"
EXAMPLES_PER_REPORT = 3

MARGIN_L = 18 * mm
MARGIN_R = 18 * mm
MARGIN_T = 24 * mm
MARGIN_B = 18 * mm
CONTENT_W = A4[0] - MARGIN_L - MARGIN_R
CARD_RADIUS = 3.5 * mm
PAGE_HEADER_H = 16 * mm
LOGO_SIZE = 5.5 * mm
LOGO_RADIUS = 1.2 * mm

# Палитра ZeroProblems — как на фронтенде (index.css + DrilldownScreen)
C_BRAND = "#dc2626"
C_BRAND_LIGHT = "#fff1f2"
C_BG_CARD = "#ffffff"
C_HERO_SUBTITLE = "#fecaca"
C_ACCENT = "#ea580c"
C_SUMMARY_BG = "#fff7ed"
C_SUMMARY_BORDER = "#fdba74"
C_TEXT = "#0f172a"
C_TEXT_MUTED = "#94a3b8"
C_TEXT_BODY = "#475569"
C_BORDER = "#e2e8f0"
C_ROW_ALT = "#f8fafc"
C_BG_SUB = "#f1f5f9"
C_HEADER_BG = "#1e293b"
C_HEADER_FG = "#f8fafc"

SEVERITY_BAR_COLORS = {
    0: "#94a3b8",
    1: "#84cc16",
    2: "#eab308",
    3: "#f97316",
    4: "#dc2626",
}
CATEGORY_BAR_COLORS = ["#dc2626", "#ea580c", "#f59e0b", "#94a3b8", "#cbd5e1"]

_fonts_registered = False
_mpl_configured = False


def _ensure_fonts() -> None:
    global _fonts_registered
    if _fonts_registered:
        return
    regular = fm.findfont("DejaVu Sans")
    bold_path = Path(regular).parent / "DejaVuSans-Bold.ttf"
    if not bold_path.exists():
        bold_path = Path(regular)
    pdfmetrics.registerFont(TTFont(FONT_REG, regular))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold_path)))
    _fonts_registered = True


def _ensure_mpl() -> None:
    global _mpl_configured
    if _mpl_configured:
        return
    _ensure_fonts()
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.facecolor": "#fafafa",
            "figure.facecolor": "white",
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#475569",
            "xtick.color": "#64748b",
            "ytick.color": "#64748b",
            "grid.color": "#e2e8f0",
            "grid.linestyle": "-",
            "grid.linewidth": 0.6,
        }
    )
    _mpl_configured = True


def _hex(color: str):
    return colors.HexColor(color)


class RoundedCard(Flowable):
    """Обёртка с фоном и скруглёнными углами для Table/flowable."""

    def __init__(
        self,
        inner,
        *,
        bg_color,
        border_color,
        border_width: float = 0.8,
        radius: float = CARD_RADIUS,
        accent_color=None,
        accent_width: float = 0,
    ):
        self.inner = inner
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
        self.radius = radius
        self.accent_color = accent_color
        self.accent_width = accent_width
        self.width = 0
        self.height = 0

    def wrap(self, availWidth, availHeight):
        w, h = self.inner.wrap(availWidth, availHeight)
        self.width = w
        self.height = h
        return w, h

    def draw(self):
        c = self.canv
        c.saveState()
        clip = c.beginPath()
        clip.roundRect(0, 0, self.width, self.height, self.radius)
        c.clipPath(clip, stroke=0, fill=0)
        c.setFillColor(self.bg_color)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        if self.accent_color and self.accent_width > 0:
            c.setFillColor(self.accent_color)
            c.rect(0, 0, self.accent_width, self.height, fill=1, stroke=0)
        self.inner.drawOn(c, 0, 0)
        c.restoreState()

        c.saveState()
        c.setStrokeColor(self.border_color)
        c.setLineWidth(self.border_width)
        c.roundRect(0, 0, self.width, self.height, self.radius, fill=0, stroke=1)
        c.restoreState()


class RoundedLogo(Flowable):
    """Красный логотип Z со скруглёнными углами (как на фронтенде)."""

    def __init__(self, size: float = LOGO_SIZE, radius: float = LOGO_RADIUS):
        super().__init__()
        self.size = size
        self.radius = radius
        self.width = size
        self.height = size

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        c.setFillColor(_hex(C_BRAND))
        c.roundRect(0, 0, self.size, self.size, self.radius, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont(FONT_BOLD, 6.5)
        c.drawCentredString(self.size / 2, self.size / 2 - 2.2, "Z")
        c.restoreState()


def _rounded_card(
    inner,
    *,
    bg: str,
    border: str,
    border_width: float = 0.8,
    radius: float = CARD_RADIUS,
    accent: str | None = None,
    accent_width: float = 0,
) -> RoundedCard:
    return RoundedCard(
        inner,
        bg_color=_hex(bg),
        border_color=_hex(border),
        border_width=border_width,
        radius=radius,
        accent_color=_hex(accent) if accent else None,
        accent_width=accent_width,
    )


def _score_palette(score: int) -> tuple[str, str]:
    if score >= 75:
        return "#fef2f2", "#991b1b"
    if score >= 60:
        return "#fef2f2", "#ef4444"
    if score >= 50:
        return "#fff7ed", "#f97316"
    if score >= 35:
        return "#ecfccb", "#84cc16"
    return "#f0fdf4", "#22c55e"


def _styles() -> dict[str, ParagraphStyle]:
    _ensure_fonts()
    return {
        "brand": ParagraphStyle(
            "brand",
            fontName=FONT_BOLD,
            fontSize=9,
            leading=11,
            textColor=_hex(C_BRAND),
            letterSpacing=0.4,
        ),
        "title": ParagraphStyle(
            "title",
            fontName=FONT_BOLD,
            fontSize=22,
            leading=26,
            textColor=_hex(C_TEXT),
            spaceAfter=4,
        ),
        "hero_brand": ParagraphStyle(
            "hero_brand",
            fontName=FONT_BOLD,
            fontSize=11,
            leading=13,
            textColor=_hex(C_TEXT),
            letterSpacing=0.2,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName=FONT_REG,
            fontSize=10,
            leading=14,
            textColor=_hex(C_TEXT_MUTED),
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName=FONT_BOLD,
            fontSize=11,
            leading=14,
            textColor=_hex(C_TEXT),
            spaceBefore=2,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=FONT_REG,
            fontSize=9,
            leading=13,
            textColor=_hex(C_TEXT_BODY),
        ),
        "summary": ParagraphStyle(
            "summary",
            fontName=FONT_REG,
            fontSize=10,
            leading=15,
            textColor=_hex("#9a3412"),
        ),
        "example": ParagraphStyle(
            "example",
            fontName=FONT_REG,
            fontSize=8.5,
            leading=12,
            textColor=_hex(C_TEXT_BODY),
        ),
        "badge": ParagraphStyle(
            "badge",
            fontName=FONT_BOLD,
            fontSize=7.5,
            leading=9,
            textColor=_hex(C_ACCENT),
        ),
        "kpi_value": ParagraphStyle(
            "kpi_value",
            fontName=FONT_BOLD,
            fontSize=14,
            leading=16,
            textColor=_hex(C_TEXT),
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label",
            fontName=FONT_REG,
            fontSize=8,
            leading=10,
            textColor=_hex(C_TEXT_MUTED),
        ),
        "score_big": ParagraphStyle(
            "score_big",
            fontName=FONT_BOLD,
            fontSize=20,
            leading=22,
            alignment=TA_CENTER,
        ),
        "score_caption": ParagraphStyle(
            "score_caption",
            fontName=FONT_REG,
            fontSize=7.5,
            leading=9,
            textColor=_hex(C_TEXT_MUTED),
            alignment=TA_CENTER,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName=FONT_REG,
            fontSize=7.5,
            leading=9,
            textColor=_hex(C_TEXT_MUTED),
            alignment=TA_CENTER,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            fontName=FONT_REG,
            fontSize=8,
            leading=10.5,
            textColor=_hex(C_TEXT_BODY),
        ),
        "table_cell_center": ParagraphStyle(
            "table_cell_center",
            fontName=FONT_REG,
            fontSize=8,
            leading=10.5,
            textColor=_hex(C_TEXT_BODY),
            alignment=TA_CENTER,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            fontName=FONT_BOLD,
            fontSize=8.5,
            leading=11,
            textColor=_hex(C_HEADER_FG),
        ),
        "table_header_center": ParagraphStyle(
            "table_header_center",
            fontName=FONT_BOLD,
            fontSize=8.5,
            leading=11,
            textColor=_hex(C_HEADER_FG),
            alignment=TA_CENTER,
        ),
    }


def _para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(_clean_text(text)), style)


def _table_base(
    *,
    header: bool = False,
    zebra: bool = True,
    header_bg: str = C_HEADER_BG,
) -> list:
    style: list = [
        ("FONT", (0, 0), (-1, -1), FONT_REG, 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), _hex(C_TEXT_BODY)),
        ("BOX", (0, 0), (-1, -1), 0.6, _hex(C_BORDER)),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, _hex(C_BORDER)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        style.extend(
            [
                ("FONT", (0, 0), (-1, 0), FONT_BOLD, 8.5),
                ("BACKGROUND", (0, 0), (-1, 0), _hex(header_bg)),
                ("TEXTCOLOR", (0, 0), (-1, 0), _hex(C_HEADER_FG)),
            ]
        )
    if zebra and not header:
        style.append(("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _hex(C_ROW_ALT)]))
    elif zebra:
        style.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _hex(C_ROW_ALT)]))
    return style


def _section_heading(title: str, styles: dict) -> Table:
    tbl = Table([[Paragraph(title, styles["h2"])]], colWidths=[CONTENT_W])
    tbl.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("LINELEFT", (0, 0), (-1, -1), 3, _hex(C_BRAND)),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return tbl


def _draw_page_header(canvas, w: float, h: float) -> None:
    header_bottom = h - PAGE_HEADER_H
    text_y = header_bottom + PAGE_HEADER_H / 2 - 3.2

    canvas.setFillColor(colors.white)
    canvas.rect(0, header_bottom, w, PAGE_HEADER_H, fill=1, stroke=0)

    canvas.setStrokeColor(_hex(C_BORDER))
    canvas.setLineWidth(0.75)
    canvas.line(0, header_bottom, w, header_bottom)

    logo_x = MARGIN_L
    logo_y = header_bottom + (PAGE_HEADER_H - LOGO_SIZE) / 2
    canvas.setFillColor(_hex(C_BRAND))
    canvas.roundRect(logo_x, logo_y, LOGO_SIZE, LOGO_SIZE, LOGO_RADIUS, fill=1, stroke=0)

    canvas.setFillColor(colors.white)
    canvas.setFont(FONT_BOLD, 6.5)
    canvas.drawCentredString(logo_x + LOGO_SIZE / 2, logo_y + LOGO_SIZE / 2 - 2.2, "Z")

    canvas.setFillColor(_hex(C_TEXT))
    canvas.setFont(FONT_BOLD, 9.5)
    canvas.drawString(logo_x + LOGO_SIZE + 2.5 * mm, text_y, BRAND_NAME)

    canvas.setFillColor(_hex(C_TEXT_MUTED))
    canvas.setFont(FONT_REG, 7.5)
    canvas.drawRightString(w - MARGIN_R, text_y, "Аналитика обращений граждан")


def _draw_page_footer(canvas, w: float, doc) -> None:
    footer_line_y = 13.5 * mm
    canvas.setStrokeColor(_hex(C_BORDER))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, footer_line_y, w - MARGIN_R, footer_line_y)

    text_y = 7.5 * mm
    canvas.setFillColor(_hex(C_TEXT_MUTED))
    canvas.setFont(FONT_REG, 7)
    canvas.drawString(MARGIN_L, text_y, datetime.now().strftime("%d.%m.%Y"))
    canvas.drawCentredString(w / 2, text_y, f"Страница {doc.page}")

    canvas.setFillColor(_hex(C_BRAND))
    canvas.setFont(FONT_BOLD, 7)
    canvas.drawRightString(w - MARGIN_R, text_y, BRAND_NAME)


def _draw_page(canvas, doc) -> None:
    _ensure_fonts()
    canvas.saveState()
    w, h = A4
    _draw_page_header(canvas, w, h)
    _draw_page_footer(canvas, w, doc)
    canvas.restoreState()


def _clean_text(text: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", str(text), flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.strip().lstrip("'\"«»")
    return re.sub(r"\s+", " ", s)


def _truncate_label(text: str, max_len: int = 42) -> str:
    s = _clean_text(text)
    return s if len(s) <= max_len else f"{s[: max_len - 1]}…"


def _chart_label(text: str, max_len: int = 58) -> str:
    """Подпись для графика: полный текст или перенос на две строки."""
    s = _clean_text(text)
    if len(s) <= max_len:
        return s
    cut = s.rfind(" ", 0, max_len)
    if cut < max_len // 2:
        cut = max_len
    return f"{s[:cut]}\n{s[cut:].strip()}"


def _fig_to_image(fig, width: float, *, max_height: float | None = None) -> Image:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    # пропорции из сохранённого PNG (bbox_inches='tight' меняет соотношение сторон)
    iw, ih = img.imageWidth, img.imageHeight
    aspect = (ih / iw) if iw else 0.55
    img.drawWidth = width
    img.drawHeight = width * aspect
    if max_height and img.drawHeight > max_height:
        scale = max_height / img.drawHeight
        img.drawHeight = max_height
        img.drawWidth *= scale
    return img


def _categories_chart(themes: list[ThematicGroupStat], width_mm: float) -> Image | None:
    if not themes:
        return None
    _ensure_mpl()
    labels = [_chart_label(t.group_name) for t in themes]
    counts = [t.count for t in themes]
    bar_colors = [CATEGORY_BAR_COLORS[min(i, len(CATEGORY_BAR_COLORS) - 1)] for i in range(len(themes))]

    bar_h = 0.58
    fig_h = max(3.2, len(themes) * bar_h + 1.2)
    fig_w = 7.4
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    y_pos = list(range(len(labels)))
    bars = ax.barh(y_pos, counts, color=bar_colors, height=0.72, edgecolor="white", linewidth=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel("Количество обращений", fontsize=9, labelpad=6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.9)
    ax.margins(x=0.08)
    for bar, val in zip(bars, counts):
        ax.text(
            bar.get_width() + max(counts) * 0.012,
            bar.get_y() + bar.get_height() / 2,
            str(val),
            va="center",
            fontsize=8,
            color="#475569",
        )
    fig.subplots_adjust(left=0.38, right=0.96, top=0.96, bottom=0.10)
    return _fig_to_image(fig, width_mm)


def _severity_chart(stats: list[SeverityStat], width_mm: float) -> Image | None:
    filtered = [s for s in stats if s.severity > 0]
    if not filtered:
        return None
    _ensure_mpl()
    labels = [s.label for s in filtered]
    counts = [s.count for s in filtered]
    bar_colors = [SEVERITY_BAR_COLORS.get(s.severity, "#94a3b8") for s in filtered]

    fig, ax = plt.subplots(figsize=(7.0, 3.0))
    bars = ax.bar(labels, counts, color=bar_colors, width=0.58, edgecolor="white", linewidth=0.6)
    ax.set_ylabel("Количество", fontsize=9, labelpad=6)
    ax.tick_params(axis="x", labelsize=8.5, rotation=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.9)
    for bar, val in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(counts) * 0.02,
            str(val),
            ha="center",
            fontsize=8,
            color="#475569",
        )
    fig.tight_layout(pad=0.8)
    return _fig_to_image(fig, width_mm)


def _kpi_table(report: DistrictReport, styles: dict) -> Table:
    score_bg, score_fg = _score_palette(int(report.score))
    cells = [
        [
            Paragraph("Всего обращений", styles["kpi_label"]),
            Paragraph("Типов проблем", styles["kpi_label"]),
            Paragraph("Топ-категория", styles["kpi_label"]),
            Paragraph("Индекс", styles["kpi_label"]),
        ],
        [
            Paragraph(str(report.total_incidents), styles["kpi_value"]),
            Paragraph(str(report.categories_count), styles["kpi_value"]),
            _para(report.top_category, styles["table_cell"]),
            Paragraph(
                f'<font color="{score_fg}"><b>{report.score}</b></font>',
                ParagraphStyle(
                    f"score_cell_{report.district_id}",
                    parent=styles["kpi_value"],
                    alignment=TA_CENTER,
                    textColor=_hex(score_fg),
                ),
            ),
        ],
    ]
    col_w = CONTENT_W / 4
    table = Table(cells, colWidths=[col_w] * 4)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _hex("#f1f5f9")),
                ("BACKGROUND", (0, 1), (2, 1), colors.white),
                ("BACKGROUND", (3, 1), (3, 1), _hex(score_bg)),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, _hex(C_BORDER)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (3, 0), (3, 1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
                ("TOPPADDING", (0, 1), (-1, 1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
            ]
        )
    )
    return _rounded_card(table, bg="#ffffff", border=C_BORDER)


def _shares_table(themes: list[ThematicGroupStat], total: int, styles: dict) -> Table | None:
    if not themes or total <= 0:
        return None
    rows = [
        [
            _para("Категория", styles["table_header"]),
            _para("Обращений", styles["table_header_center"]),
            _para("Доля", styles["table_header_center"]),
        ]
    ]
    for t in themes:
        rows.append(
            [
                _para(t.group_name, styles["table_cell"]),
                _para(str(t.count), styles["table_cell_center"]),
                _para(f"{t.percentage:.1f}%", styles["table_cell_center"]),
            ]
        )
    table = Table(rows, colWidths=[CONTENT_W - 58 * mm, 28 * mm, 30 * mm])
    style = _table_base(header=True, zebra=True)
    style.append(("VALIGN", (0, 0), (-1, -1), "TOP"))
    style.append(("ALIGN", (1, 1), (-1, -1), "CENTER"))
    table.setStyle(TableStyle(style))
    return table


def _example_card(i: int, ex: IncidentExample, styles: dict) -> Table:
    severity_color = SEVERITY_BAR_COLORS.get(ex.severity, "#94a3b8")
    text = escape(_clean_text(ex.text))
    content_rows: list[list] = []
    if ex.severity > 0 and ex.label:
        badge = (
            f'<font name="{FONT_BOLD}" color="{severity_color}">'
            f"{escape(ex.label)} · {ex.severity}</font>"
        )
        content_rows.append([Paragraph(badge, styles["example"])])
    content_rows.append([Paragraph(text, styles["example"])])
    content = Table(content_rows, colWidths=[CONTENT_W - 28 * mm])
    content.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -2), 2),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    number = Paragraph(
        f'<font name="{FONT_BOLD}" color="{C_TEXT_BODY}">{i}</font>',
        styles["example"],
    )
    inner = Table([[number, content]], colWidths=[8 * mm, CONTENT_W - 28 * mm])
    inner.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    card = Table([[inner]], colWidths=[CONTENT_W])
    card.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return _rounded_card(card, bg=C_BG_SUB, border=C_BORDER, border_width=0.5)


def _examples_block(
    examples: list[IncidentExample],
    styles: dict,
    *,
    limit: int | None = None,
) -> list:
    flow: list = [_section_heading("Примеры обращений", styles), Spacer(1, 4 * mm)]
    items = examples[:limit] if limit else examples
    if not items:
        flow.append(Paragraph("Нет примеров проблемных обращений.", styles["body"]))
        return flow
    for i, ex in enumerate(items, 1):
        flow.append(_example_card(i, ex, styles))
        flow.append(Spacer(1, 3 * mm))
    return flow


def pdf_attachment_names(district_id: int, district_name: str) -> tuple[str, str]:
    ascii_name = f"zeroproblems_report_{district_id}.pdf"
    clean = re.sub(r'[<>:"/\\|?*]', "", str(district_name)).strip() or f"MO_{district_id}"
    utf8_name = f"zeroproblems_{clean.replace(' ', '_')[:60]}.pdf"
    return ascii_name, utf8_name


def build_region_executive_summary(districts: list[DistrictReport]) -> str:
    """Краткая сводка по всей области из агрегированных данных МО."""
    if not districts:
        return ""
    ordered = sorted(districts, key=lambda d: d.score, reverse=True)
    total_incidents = sum(int(d.total_incidents) for d in districts)
    scores = [int(d.score) for d in districts]
    worst = ordered[:3]

    theme_weights: Counter[str] = Counter()
    for d in districts:
        if d.top_category:
            theme_weights[str(d.top_category)] += int(d.total_incidents)
    top_themes = theme_weights.most_common(3)

    total_fmt = f"{total_incidents:,}".replace(",", " ")
    parts = [
        (
            f"Сводный анализ по {len(districts)} муниципалитетам Омской области: "
            f"всего {total_fmt} обращений. "
            f"Индекс проблемности — от {min(scores)} до {max(scores)} баллов "
            f"(чем ниже, тем выше нагрузка)."
        ),
        (
            "Территории с наибольшей проблемностью: "
            + "; ".join(
                f"{d.district_name} (индекс {d.score}, «{d.top_category}»)"
                for d in worst
            )
            + "."
        ),
    ]
    if top_themes:
        parts.append(
            "Системно повторяющиеся темы: "
            + "; ".join(f"«{name}»" for name, _ in top_themes)
            + "."
        )
    return " ".join(parts)


def _is_usable_region_summary(text: str, districts: list[DistrictReport]) -> bool:
    cleaned = _clean_text(text)
    if len(cleaned) < 120:
        return False
    # обрезанный или незаконченный LLM-ответ
    if cleaned.endswith(("Основная тема", "…", "...", "тема", "группа")):
        return False
    if len(districts) <= 1:
        return True
    # одна случайная сводка по одному МО вместо обзора области
    mentioned = [d for d in districts if d.district_name and d.district_name in cleaned]
    regional_markers = ("област", "регион", "сводн", "муниципалитет", "top-", "топ-")
    has_regional_context = any(m in cleaned.lower() for m in regional_markers)
    if len(mentioned) == 1 and not has_regional_context:
        return False
    return True


def _resolve_region_summary(districts: list[DistrictReport], executive_summary: str) -> str:
    candidate = str(executive_summary or "").strip()
    if _is_usable_region_summary(candidate, districts):
        return candidate
    return build_region_executive_summary(districts)


def _summary_block(
    summary_text: str,
    styles: dict,
    *,
    title: str = "Аналитическая сводка",
    keep_together: bool = True,
) -> list:
    if not summary_text or not str(summary_text).strip():
        return []
    summary = escape(_clean_text(summary_text))
    body = Table([[Paragraph(summary, styles["summary"])]], colWidths=[CONTENT_W - 14 * mm])
    body.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    card = Table([[body]], colWidths=[CONTENT_W])
    card.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    card = _rounded_card(
        card,
        bg=C_SUMMARY_BG,
        border=C_SUMMARY_BORDER,
    )
    block = [
        _section_heading(title, styles),
        Spacer(1, 3 * mm),
        card,
    ]
    if keep_together:
        return [KeepTogether(block), Spacer(1, 8 * mm)]
    return [*block, Spacer(1, 8 * mm)]


def _hero_header(
    title: str,
    subtitle: str,
    meta: str,
    styles: dict,
    *,
    show_brand: bool = True,
) -> list:
    inner_w = CONTENT_W - 28 * mm
    title_style = ParagraphStyle("hero_title_c", parent=styles["title"], alignment=TA_CENTER)
    subtitle_style = ParagraphStyle("hero_sub_c", parent=styles["subtitle"], alignment=TA_CENTER)

    rows: list[list] = []
    table_style = [
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
    ]

    if show_brand:
        brand_style = ParagraphStyle("hero_brand_c", parent=styles["hero_brand"], alignment=TA_LEFT)
        brand_inner = Table(
            [[RoundedLogo(), Paragraph(BRAND_NAME, brand_style)]],
            colWidths=[7 * mm, 34 * mm],
        )
        brand_inner.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (1, 0), (1, 0), 2.5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        brand_row = Table([[brand_inner]], colWidths=[inner_w])
        brand_row.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        rows.append([brand_row])
        table_style.extend(
            [
                ("TOPPADDING", (0, 0), (-1, 0), 12),
                ("TOPPADDING", (0, 1), (-1, 1), 4),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, _hex(C_BORDER)),
            ]
        )
    else:
        table_style.append(("TOPPADDING", (0, 0), (-1, 0), 12))

    title_row = len(rows)
    rows.append([Paragraph(escape(title), title_style)])
    rows.append([Paragraph(escape(subtitle), subtitle_style)] if subtitle else [Spacer(1, 1)])
    rows.append([Paragraph(meta, subtitle_style)])
    if not show_brand:
        table_style.append(("TOPPADDING", (0, title_row + 1), (-1, title_row + 1), 4))

    tbl = Table(rows, colWidths=[CONTENT_W])
    tbl.setStyle(TableStyle(table_style))
    hero = _rounded_card(tbl, bg=C_BG_CARD, border=C_BORDER, radius=4 * mm)
    return [hero, Spacer(1, 8 * mm)]


def _district_story(
    report: DistrictReport,
    content_width: float,
    styles: dict,
    *,
    compact: bool = False,
    section_title: bool = True,
) -> list:
    story: list = []
    themes = report.themes_stat[:5] if compact else report.themes_stat
    examples_limit = EXAMPLES_PER_REPORT
    score_bg, score_fg = _score_palette(int(report.score))

    if section_title:
        meta = (
            f"Индекс {report.score} из 100 · обращений {report.total_incidents} · "
            f"сформирован {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        story.extend(
            _hero_header(
                report.district_name,
                "Отчёт по муниципалитету",
                meta,
                styles,
                show_brand=False,
            )
        )
        score_label_style = ParagraphStyle(
            f"score_chip_label_{report.district_id}",
            parent=styles["score_caption"],
            alignment=TA_LEFT,
            fontSize=9,
            leading=11,
            textColor=_hex(C_TEXT_MUTED),
        )
        score_chip = Table(
            [[
                Paragraph(f'<font color="{score_fg}"><b>{report.score}</b></font>', styles["score_big"]),
                Paragraph("<nobr>индекс проблемности</nobr>", score_label_style),
            ]],
            colWidths=[26 * mm, CONTENT_W - 26 * mm],
        )
        score_chip.setStyle(
            TableStyle(
                [
                    ("LINEAFTER", (0, 0), (0, 0), 0.5, _hex(score_fg)),
                    ("ALIGN", (0, 0), (0, 0), "CENTER"),
                    ("ALIGN", (1, 0), (1, 0), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (0, 0), 10),
                    ("RIGHTPADDING", (0, 0), (0, 0), 6),
                    ("LEFTPADDING", (1, 0), (1, 0), 10),
                    ("RIGHTPADDING", (1, 0), (1, 0), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(_rounded_card(score_chip, bg=score_bg, border=score_fg))
        story.append(Spacer(1, 6 * mm))

    story.extend(_summary_block(report.analytical_summary, styles))
    story.append(_kpi_table(report, styles))
    story.append(Spacer(1, 8 * mm))

    cat_chart = _categories_chart(themes, content_width)
    if cat_chart:
        story.append(
            KeepTogether(
                [_section_heading("Обращения по категориям", styles), Spacer(1, 3 * mm), cat_chart]
            )
        )
        story.append(Spacer(1, 6 * mm))

    shares = _shares_table(themes, report.total_incidents, styles)
    if shares:
        story.append(
            KeepTogether([_section_heading("Доли категорий", styles), Spacer(1, 3 * mm), shares])
        )
        story.append(Spacer(1, 8 * mm))

    sev_chart = _severity_chart(report.severity_stat, content_width)
    if sev_chart:
        story.append(
            KeepTogether(
                [_section_heading("Распределение по тяжести", styles), Spacer(1, 3 * mm), sev_chart]
            )
        )
        story.append(Spacer(1, 8 * mm))

    story.extend(_examples_block(report.incident_examples, styles, limit=examples_limit))
    return story


def _region_map_block(districts: list[DistrictReport], styles: dict) -> list:
    try:
        fig = render_region_map_figure(districts)
        map_img = _fig_to_image(fig, CONTENT_W, max_height=108 * mm)
    except Exception:
        return []
    return [
        _section_heading("Карта индекса проблемности", styles),
        Spacer(1, 3 * mm),
        map_img,
        Spacer(1, 8 * mm),
    ]


def _overview_table(districts: list[DistrictReport], styles: dict) -> Table:
    col_num = 12 * mm
    col_score = 16 * mm
    col_count = 24 * mm
    col_name = 54 * mm
    col_category = CONTENT_W - col_num - col_score - col_count - col_name

    rows = [
        [
            "№",
            _para("Муниципалитет", styles["table_header"]),
            _para("Индекс", styles["table_header_center"]),
            _para("Обращений", styles["table_header_center"]),
            _para("Топ-категория", styles["table_header"]),
        ]
    ]
    for i, d in enumerate(districts, 1):
        _, fg = _score_palette(int(d.score))
        score_style = ParagraphStyle(
            f"overview_score_{i}",
            parent=styles["table_cell_center"],
            fontName=FONT_BOLD,
            textColor=_hex(fg),
        )
        rows.append(
            [
                str(i),
                _para(d.district_name, styles["table_cell"]),
                Paragraph(f"<b>{d.score}</b>", score_style),
                str(d.total_incidents),
                _para(d.top_category, styles["table_cell"]),
            ]
        )

    table = Table(
        rows,
        colWidths=[col_num, col_name, col_score, col_count, col_category],
        repeatRows=1,
    )
    style = _table_base(header=True, zebra=True)
    style.extend(
        [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("FONT", (0, 0), (0, 0), FONT_BOLD, 8.5),
            ("TEXTCOLOR", (0, 0), (0, 0), _hex(C_HEADER_FG)),
            ("FONT", (0, 1), (0, -1), FONT_REG, 8.5),
            ("ALIGN", (2, 1), (3, -1), "CENTER"),
            ("FONT", (3, 1), (3, -1), FONT_REG, 8.5),
        ]
    )
    table.setStyle(TableStyle(style))
    return table


def _build_pdf(story: list, title: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title=title,
    )
    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return buffer.getvalue()


def build_district_pdf(report: DistrictReport) -> bytes:
    styles = _styles()
    story = _district_story(report, CONTENT_W, styles, compact=False)
    return _build_pdf(story, f"Отчёт — {report.district_name}")


def build_region_pdf(
    districts: list[DistrictReport],
    *,
    executive_summary: str = "",
) -> bytes:
    if not districts:
        raise ValueError("Нет данных по муниципалитетам")

    styles = _styles()
    ordered = sorted(districts, key=lambda d: d.score, reverse=True)

    story: list = _hero_header(
        "Все муниципалитеты",
        "Сводный отчёт по Омской области",
        f"Сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')} · "
        f"Муниципалитетов: {len(ordered)}",
        styles,
    )
    region_summary = _resolve_region_summary(ordered, executive_summary)
    story.extend(
        _summary_block(
            region_summary,
            styles,
            title="Сводка по области",
            keep_together=False,
        ),
    )
    story.extend(_region_map_block(ordered, styles))
    story.append(_section_heading("Сводная таблица", styles))
    story.append(Spacer(1, 3 * mm))
    story.append(_overview_table(ordered, styles))
    story.append(PageBreak())

    for idx, report in enumerate(ordered):
        story.extend(
            _district_story(
                report,
                CONTENT_W,
                styles,
                compact=True,
                section_title=True,
            )
        )
        if idx < len(ordered) - 1:
            story.append(PageBreak())

    return _build_pdf(story, "Сводный отчёт — Омская область")


def content_disposition_header(district_id: int, district_name: str) -> str:
    from urllib.parse import quote

    ascii_name, utf8_name = pdf_attachment_names(district_id, district_name)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(utf8_name)}"


def content_disposition_region_header() -> str:
    from urllib.parse import quote

    ascii_name = "zeroproblems_all_municipalities.pdf"
    utf8_name = "zeroproblems_vse_municipalitety.pdf"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(utf8_name)}"
