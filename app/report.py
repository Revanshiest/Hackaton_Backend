"""Формирование Excel-отчётов и JSON для API / фронтенда."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.config.settings import PipelineSettings
from schemas import (
    CriticalDistrictCard,
    DashboardResponse,
    DistrictReport,
    DistrictReportResponse,
    DistrictShortInfo,
    ThematicGroupStat,
    ThemeCount,
)


def write_excel_report(
    cfg: PipelineSettings,
    top_all: pd.DataFrame,
    top10: pd.DataFrame,
    top3: pd.DataFrame,
    topics_df: pd.DataFrame,
    groups_df: pd.DataFrame,
    reasons_df: pd.DataFrame | None = None,
    labeled_df: pd.DataFrame | None = None,
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

    return out_path


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
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary_text": summary_text,
        "top3": top3.fillna("").to_dict(orient="records"),
        "top10": top10.fillna("").to_dict(orient="records"),
        "all": top_all.fillna("").to_dict(orient="records"),
        "topics": topics_df.fillna("").to_dict(orient="records"),
        "groups": groups_df.fillna("").to_dict(orient="records"),
        "reasons": reasons_df.fillna("").to_dict(orient="records"),
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


def build_dashboard(report: dict) -> DashboardResponse:
    top10 = report.get("top10", [])
    reasons = {r["муниципалитет"]: r for r in report.get("reasons", [])}

    map_data: list[DistrictShortInfo] = []
    for row in report.get("all", []):
        muni = row["муниципалитет"]
        reason = reasons.get(muni, {})
        map_data.append(
            DistrictShortInfo(
                district_id=int(row.get("district_id", row.get("rank", 0))),
                district_name=muni,
                score=int(row.get("score", 50)),
                main_problem=_main_problem({**row, **reason}),
            )
        )

    top_districts = []
    for row in top10:
        muni = row["муниципалитет"]
        reason = reasons.get(muni, {})
        top_districts.append(
            DistrictShortInfo(
                district_id=int(row.get("district_id", row.get("rank", 0))),
                district_name=muni,
                score=int(row.get("score", 50)),
                main_problem=_main_problem({**row, **reason}),
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
                district_id=int(row.get("district_id", row.get("rank", 0))),
                district_name=muni,
                criticality_status=_criticality_status(
                    int(row.get("score", 50)),
                    float(row.get("severity_mean", 0)),
                ),
                score=int(row.get("score", 50)),
                top_themes=_parse_theme_counts(merged.get("ключевые_темы", "")),
                sample_incident_text=sample[:300],
                total_incidents=int(row.get("total_incidents", row.get("problem_count", 0))),
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
    topics = [t for t in report.get("topics", []) if t.get("муниципалитет") == muni]
    total = int(target.get("total_incidents", 0))
    themes_stat = []
    for t in sorted(topics, key=lambda x: x.get("count", 0), reverse=True)[:8]:
        count = int(t.get("count", 0))
        pct = round(count / total * 100, 1) if total else 0.0
        themes_stat.append(
            ThematicGroupStat(
                group_name=str(t.get("тема", "")),
                count=count,
                percentage=pct,
            )
        )

    examples = str(reason.get("примеры_текстов", "")).split(" || ")
    examples = [e for e in examples if e.strip()][:5]

    summary = analytical_summary or reason.get("summary_text") or (
        f"Муниципалитет «{muni}»: {int(target.get('problem_count', 0))} проблемных обращений, "
        f"средняя тяжесть {float(target.get('severity_mean', 0)):.1f}."
    )

    return DistrictReportResponse(
        data=DistrictReport(
            district_id=district_id,
            district_name=muni,
            score=int(target.get("score", 50)),
            analytical_summary=summary,
            total_incidents=total,
            top_category=str(reason.get("топ_тема", "") or _main_problem({**target, **reason})),
            categories_count=len(themes_stat),
            themes_stat=themes_stat,
            incident_examples=examples,
        )
    )


def load_report_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
