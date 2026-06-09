"""Формирование Excel-отчётов и JSON для API / фронтенда."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.config.settings import PipelineSettings
from app.llm_text import is_complete_summary, normalize_llm_summary
from app.text_samples import clean_appeal_text, sample_problem_texts
from schemas import (
    CriticalDistrictCard,
    DashboardResponse,
    DistrictReport,
    DistrictReportResponse,
    DistrictShortInfo,
    IncidentExample,
    SeverityStat,
    ThematicGroupStat,
    ThemeCount,
)

SEVERITY_LABELS: dict[int, str] = {
    0: "Не инцидент",
    1: "Низкая",
    2: "Средняя",
    3: "Высокая",
    4: "Критическая",
}


def _build_incident_examples(
    reason: dict,
    muni: str,
    labeled_df: pd.DataFrame | None = None,
    *,
    limit: int = 5,
) -> list[IncidentExample]:
    raw = reason.get("примеры_обращений")
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        examples: list[IncidentExample] = []
        for item in raw:
            sev = _safe_int(item.get("severity", 0))
            if sev <= 0:
                continue
            text = clean_appeal_text(item.get("text", ""))
            if len(text) < 40:
                continue
            examples.append(
                IncidentExample(
                    text=text,
                    severity=sev,
                    label=str(item.get("label", SEVERITY_LABELS.get(sev, ""))),
                )
            )
        if examples:
            return examples[:limit]

    if labeled_df is not None and not labeled_df.empty and "текст" in labeled_df.columns:
        problems = labeled_df
        if "severity" in labeled_df.columns:
            problems = labeled_df.loc[labeled_df["severity"].fillna(0) > 0]
        samples = sample_problem_texts(problems, muni, n=limit)
        if samples:
            return [
                IncidentExample(
                    text=s["text"],
                    severity=_safe_int(s["severity"]),
                    label=str(s.get("label", SEVERITY_LABELS.get(_safe_int(s["severity"]), ""))),
                )
                for s in samples
            ]

    legacy = [e.strip() for e in str(reason.get("примеры_текстов", "")).split(" || ") if e.strip()]
    return [
        IncidentExample(text=text, severity=1, label=SEVERITY_LABELS[1])
        for text in legacy[:limit]
    ]


def build_severity_breakdown(labeled_df: pd.DataFrame) -> list[dict]:
    """Счётчики по классам 0–4 для каждого муниципалитета."""
    if labeled_df.empty or "severity" not in labeled_df.columns:
        return []
    rows: list[dict] = []
    for muni, sub in labeled_df.groupby("муниципалитет"):
        for sev in range(5):
            count = int((sub["severity"] == sev).sum())
            rows.append(
                {
                    "муниципалитет": str(muni),
                    "severity": sev,
                    "label": SEVERITY_LABELS[sev],
                    "count": count,
                }
            )
    return rows


def write_excel_report(
    cfg: PipelineSettings,
    top_all: pd.DataFrame,
    top10: pd.DataFrame,
    top3: pd.DataFrame,
    topics_df: pd.DataFrame,
    groups_df: pd.DataFrame,
    reasons_df: pd.DataFrame | None = None,
    labeled_df: pd.DataFrame | None = None,
    muni_summaries: pd.DataFrame | None = None,
    top3_summaries: pd.DataFrame | None = None,
) -> Path:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = cfg.output_dir / "report_top_districts.xlsx"

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        top3.to_excel(writer, sheet_name="Top3", index=False)
        top10.to_excel(writer, sheet_name="Top10", index=False)
        top_all.to_excel(writer, sheet_name="AllMunicipalities", index=False)
        if reasons_df is not None and not reasons_df.empty:
            reasons_df.to_excel(writer, sheet_name="Причины_Top", index=False)
        if not topics_df.empty:
            topics_df.to_excel(writer, sheet_name="Темы", index=False)
        if not groups_df.empty:
            groups_df.to_excel(writer, sheet_name="Группы", index=False)
        if labeled_df is not None:
            sample = labeled_df.head(5000)
            sample.to_excel(writer, sheet_name="Размеченные_примеры", index=False)

        meta = pd.DataFrame(
            {
                "parameter": ["input", "classifier", "summary", "top_hotspots", "top_municipalities"],
                "value": [
                    str(cfg.input_path),
                    "onnx/xlm-roberta",
                    f"ollama/{cfg.ollama_model}",
                    str(cfg.top_hotspots),
                    str(cfg.top_municipalities),
                ],
            }
        )
        meta.to_excel(writer, sheet_name="Config", index=False)

    write_top10_excel(
        cfg.output_dir,
        top10=top10,
        top3=top3,
        topics_df=topics_df,
        groups_df=groups_df,
        reasons_df=reasons_df,
        muni_summaries=muni_summaries,
        top3_summaries=top3_summaries,
    )
    return out_path


def write_top10_excel(
    output_dir: Path,
    *,
    top10: pd.DataFrame,
    top3: pd.DataFrame,
    topics_df: pd.DataFrame,
    groups_df: pd.DataFrame,
    reasons_df: pd.DataFrame | None = None,
    muni_summaries: pd.DataFrame | None = None,
    top3_summaries: pd.DataFrame | None = None,
) -> Path:
    """Excel только по Top-10 (и Top-3): рейтинг, темы, причины, примеры."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "report_top10.xlsx"

    top_names = set(top10["муниципалитет"].astype(str))
    reasons_top = (
        reasons_df[reasons_df["муниципалитет"].astype(str).isin(top_names)].copy()
        if reasons_df is not None and not reasons_df.empty
        else pd.DataFrame()
    )
    topics_top = (
        topics_df[topics_df["муниципалитет"].astype(str).isin(top_names)].copy()
        if not topics_df.empty
        else pd.DataFrame()
    )
    groups_top = (
        groups_df[groups_df["муниципалитет"].astype(str).isin(top_names)].copy()
        if not groups_df.empty
        else pd.DataFrame()
    )

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        top10.to_excel(writer, sheet_name="Top10", index=False)
        if not top3.empty:
            top3.to_excel(writer, sheet_name="Top3", index=False)
        if not reasons_top.empty:
            reasons_top.to_excel(writer, sheet_name="Причины", index=False)
        if not topics_top.empty:
            topics_top.to_excel(writer, sheet_name="Темы", index=False)
        if not groups_top.empty:
            groups_top.to_excel(writer, sheet_name="Группы", index=False)
        if muni_summaries is not None and not muni_summaries.empty:
            muni_summaries.to_excel(writer, sheet_name="Top10_справки", index=False)
        if top3_summaries is not None and not top3_summaries.empty:
            top3_summaries.to_excel(writer, sheet_name="Top3_справки", index=False)
        elif muni_summaries is not None and not muni_summaries.empty:
            muni_summaries.to_excel(writer, sheet_name="LLM_справки", index=False)

    return out_path


def build_top10_excel_from_report(report: dict, output_dir: Path) -> Path:
    """Собрать Top-10 Excel из report.json (для старых задач без файла)."""
    return write_top10_excel(
        output_dir,
        top10=pd.DataFrame(report.get("top10", [])),
        top3=pd.DataFrame(report.get("top3", [])),
        topics_df=pd.DataFrame(report.get("topics", [])),
        groups_df=pd.DataFrame(report.get("groups", [])),
        reasons_df=pd.DataFrame(report.get("reasons", [])),
    )


def _safe_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        if isinstance(value, float) and np.isnan(value):
            return default
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    return int(round(_safe_float(value, default)))


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    out = df.copy()
    for col in out.select_dtypes(include="object").columns:
        out[col] = out[col].fillna("")
    records = out.to_dict(orient="records")
    for row in records:
        for key, val in row.items():
            if isinstance(val, float) and np.isnan(val):
                row[key] = None
    return records


def write_report_json(
    output_dir: Path,
    top_all: pd.DataFrame,
    top10: pd.DataFrame,
    top3: pd.DataFrame,
    topics_df: pd.DataFrame,
    groups_df: pd.DataFrame,
    reasons_df: pd.DataFrame,
    summary_text: str,
    stats: dict,
    severity_breakdown: list[dict] | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary_text": summary_text,
        "top3": _df_to_records(top3),
        "top10": _df_to_records(top10),
        "all": _df_to_records(top_all),
        "topics": _df_to_records(topics_df),
        "groups": _df_to_records(groups_df),
        "reasons": _df_to_records(reasons_df),
        "severity_breakdown": severity_breakdown or [],
        "stats": stats,
    }
    path = output_dir / "report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _main_problem(row: pd.Series) -> str:
    for key in ("топ_тема", "ключевые_темы", "топ_группа"):
        val = str(row.get(key, "")).strip()
        if val:
            return val.split(";")[0].split("(")[0].strip()
    return "Не определено"


def _criticality_status(score: int, severity_mean: float) -> str:
    if score <= 15 or severity_mean >= 3.5:
        return "КРИТИЧНЫЙ"
    if score <= 30 or severity_mean >= 2.8:
        return "ОЧЕНЬ ВЫСОКИЙ"
    if score <= 45:
        return "ВЫСОКИЙ"
    return "ПОВЫШЕННЫЙ"


def _parse_theme_counts(key_topics: str, limit: int = 5) -> list[ThemeCount]:
    items = []
    for part in str(key_topics).split(";"):
        part = part.strip()
        if not part:
            continue
        if "(" in part and ")" in part:
            name, cnt = part.rsplit("(", 1)
            try:
                count = int(cnt.replace(")", "").strip())
            except ValueError:
                count = 0
            items.append(ThemeCount(theme=name.strip(), count=count))
        else:
            items.append(ThemeCount(theme=part, count=0))
        if len(items) >= limit:
            break
    return items


def _district_summary(row: dict, reason: dict) -> str | None:
    paragraph = str(row.get("summary_paragraph") or "").strip()
    if paragraph and is_complete_summary(paragraph, min_len=20):
        return paragraph
    one_line = str(row.get("summary_text") or reason.get("summary_text") or "").strip()
    if one_line and is_complete_summary(one_line, min_len=15):
        return one_line
    if paragraph:
        return paragraph
    return one_line or None


def build_dashboard(report: dict) -> DashboardResponse:
    top10 = report.get("top10", [])
    reasons = {r["муниципалитет"]: r for r in report.get("reasons", [])}

    map_data: list[DistrictShortInfo] = []
    for row in report.get("all", []):
        muni = row["муниципалитет"]
        reason = reasons.get(muni, {})
        map_data.append(
            DistrictShortInfo(
                district_id=_safe_int(row.get("district_id", row.get("rank", 0))),
                district_name=muni,
                score=_safe_int(row.get("score", 50)),
                main_problem=_main_problem({**row, **reason}),
            )
        )

    top_districts = []
    for row in top10:
        muni = row["муниципалитет"]
        reason = reasons.get(muni, {})
        top_districts.append(
            DistrictShortInfo(
                district_id=_safe_int(row.get("district_id", row.get("rank", 0))),
                district_name=muni,
                score=_safe_int(row.get("score", 50)),
                main_problem=_main_problem({**row, **reason}),
                analytical_summary=_district_summary(row, reason),
            )
        )

    critical_districts = []
    for row in report.get("top3", []):
        muni = row["муниципалитет"]
        reason = reasons.get(muni, {})
        merged = {**row, **reason}
        examples = str(merged.get("примеры_текстов", "")).split(" || ")
        sample = examples[0] if examples and examples[0] else ""
        critical_districts.append(
            CriticalDistrictCard(
                district_id=_safe_int(row.get("district_id", row.get("rank", 0))),
                district_name=muni,
                criticality_status=_criticality_status(
                    _safe_int(row.get("score", 50)),
                    _safe_float(row.get("severity_mean", 0)),
                ),
                score=_safe_int(row.get("score", 50)),
                top_themes=_parse_theme_counts(merged.get("ключевые_темы", "")),
                sample_incident_text=sample[:300],
                analytical_summary=_district_summary(row, reason),
                total_incidents=_safe_int(row.get("total_incidents", row.get("problem_count", 0))),
            )
        )

    return DashboardResponse(
        map_data=map_data,
        top_districts=top_districts,
        critical_districts=critical_districts,
    )


def build_district_report(
    report: dict,
    district_id: int,
    *,
    analytical_summary: str | None = None,
    labeled_df: pd.DataFrame | None = None,
) -> DistrictReportResponse | None:
    all_rows = report.get("all", [])
    target = next(
        (r for r in all_rows if int(r.get("district_id", r.get("rank", -1))) == district_id),
        None,
    )
    if target is None:
        return None

    muni = target["муниципалитет"]
    reason = next((r for r in report.get("reasons", []) if r["муниципалитет"] == muni), {})
    ranked = next(
        (
            r
            for r in report.get("top3", []) + report.get("top10", [])
            if int(r.get("district_id", r.get("rank", -1))) == district_id
        ),
        {},
    )
    topics = [t for t in report.get("topics", []) if t.get("муниципалитет") == muni]
    total = _safe_int(target.get("total_incidents", 0))
    themes_stat = []
    for t in sorted(topics, key=lambda x: x.get("count", 0), reverse=True)[:8]:
        count = _safe_int(t.get("count", 0))
        pct = round(count / total * 100, 1) if total else 0.0
        themes_stat.append(
            ThematicGroupStat(
                group_name=str(t.get("тема", "")),
                count=count,
                percentage=pct,
            )
        )

    examples = _build_incident_examples(reason, muni, labeled_df)

    severity_rows = [
        r for r in report.get("severity_breakdown", []) if str(r.get("муниципалитет", "")) == muni
    ]
    severity_stat: list[SeverityStat] = []
    for row in sorted(severity_rows, key=lambda x: x.get("severity", 0)):
        count = _safe_int(row.get("count", 0))
        pct = round(count / total * 100, 1) if total else 0.0
        severity_stat.append(
            SeverityStat(
                severity=_safe_int(row.get("severity", 0)),
                label=str(row.get("label", SEVERITY_LABELS.get(_safe_int(row.get("severity", 0)), ""))),
                count=count,
                percentage=pct,
            )
        )

    summary = (
        analytical_summary
        or ranked.get("summary_paragraph")
        or reason.get("summary_paragraph")
        or reason.get("summary_text")
        or (
            f"Муниципалитет «{muni}»: {_safe_int(target.get('problem_count', 0))} проблемных обращений "
            f"из {total}, индекс проблемности {_safe_int(target.get('score', 50))} из 100. "
            f"Главная тема — {reason.get('топ_тема', '') or _main_problem({**target, **reason})}."
        )
    )
    if not is_complete_summary(summary, min_len=30):
        summary = (
            f"«{muni}»: {_safe_int(target.get('problem_count', 0))} проблемных обращений из {total}, "
            f"индекс {_safe_int(target.get('score', 50))} из 100. "
            f"Основная тема — {reason.get('топ_тема', '') or _main_problem({**target, **reason})}."
        )
    summary = normalize_llm_summary(summary, one_sentence=False, max_chars=2000)

    return DistrictReportResponse(
        data=DistrictReport(
            district_id=district_id,
            district_name=muni,
            score=_safe_int(target.get("score", 50)),
            analytical_summary=summary,
            total_incidents=total,
            top_category=str(reason.get("топ_тема", "") or _main_problem({**target, **reason})),
            categories_count=len(themes_stat),
            themes_stat=themes_stat,
            severity_stat=severity_stat,
            incident_examples=examples,
        )
    )


def load_report_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
