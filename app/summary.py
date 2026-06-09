"""LLM-справки через Ollama + быстрые шаблоны по структурированным данным."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from app.config.llm import OLLAMA_BASE_URL, OLLAMA_MODEL
from app.config.settings import PipelineSettings
from app.llm_text import is_complete_summary, normalize_llm_summary
from app.summary_templates import (
    _as_series,
    template_municipality_paragraph,
    template_top3_paragraph,
)
from app.text_samples import sample_problem_texts, truncate_text

_SYSTEM_PROMPT = (
    "Ты аналитик для руководства Омской области. "
    "Пиши только готовый текст для доклада: без вариантов, без пояснений модели, без markdown. "
    "Обязательно указывай цифры из данных. Простой деловой русский язык. "
    "Без персональных данных, адресов и цитат граждан."
)


def _chat(
    cfg: PipelineSettings,
    prompt: str,
    *,
    one_sentence: bool = False,
    num_predict: int | None = None,
    max_chars: int = 800,
) -> str:
    url = f"{cfg.ollama_base_url.rstrip('/')}/api/chat"
    predict = num_predict if num_predict is not None else (96 if one_sentence else 400)
    payload = {
        "model": cfg.ollama_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.15,
            "num_predict": predict,
        },
    }
    resp = requests.post(url, json=payload, timeout=300)
    if resp.status_code == 404:
        try:
            err = resp.json().get("error", "")
        except ValueError:
            err = resp.text
        if "not found" in err.lower():
            raise RuntimeError(
                f"Модель Ollama «{cfg.ollama_model}» не найдена. "
                f"Выполните: ollama pull {cfg.ollama_model}"
            ) from None
    resp.raise_for_status()
    data = resp.json()
    message = data.get("message", {})
    raw = str(message.get("content", "")).strip()
    return normalize_llm_summary(raw, one_sentence=one_sentence, max_chars=max_chars)


def _leadership_prompt(row: pd.Series, reason_row: pd.Series | None, *, extended: bool = False) -> str:
    reason = _as_series(reason_row, row)
    muni = str(row.get("муниципалитет", ""))
    rank = int(row.get("rank", 0) or 0)
    score = int(row.get("score", row.get("health_score", 0)) or 0)
    problems = int(row.get("problem_count", 0) or 0)
    total = int(row.get("total_incidents", 0) or 0)
    share = float(row.get("problem_share", 0) or 0)
    critical = int(row.get("critical_count", 0) or 0)
    sev = float(row.get("severity_mean", 0) or 0)
    top_theme = str(reason.get("топ_тема") or row.get("топ_тема") or "")
    top_group = str(reason.get("топ_группа") or row.get("топ_группа") or "")
    key_themes = str(reason.get("ключевые_темы") or row.get("ключевые_темы") or "")

    sentences = "4–5 предложений" if extended else "3–4 предложения"
    extra = (
        "\nДополнительно: укажи уровень критичности и одно конкретное управленческое действие."
        if extended
        else ""
    )
    return (
        f"Сводка для руководства по муниципалитету «{muni}».\n"
        f"Место в рейтинге: {rank}, индекс проблемности: {score} из 100 (чем ниже — тем хуже).\n"
        f"Проблемных обращений: {problems} из {total} ({share:.0%}).\n"
        f"Средняя тяжесть: {sev:.1f}, критических (класс 4): {critical}.\n"
        f"Главная тема: {top_theme}. Группа: {top_group}.\n"
        f"Топ темы: {key_themes}.\n\n"
        f"Напиши ровно {sentences} для заместителя губернатора.\n"
        "Правила:\n"
        f"- Первое предложение начни с «{muni}».\n"
        "- Используй только русский язык (не пиши health score).\n"
        "- Называй конкретную тему жалоб, без общих фраз вроде «социальная стабильность» или «качество жизни».\n"
        "- Последнее предложение — что сделать органам власти.\n"
        "- Закончи текст точкой. Без списков и заголовков."
        f"{extra}\n"
    )


def _summarize_municipality_llm(
    cfg: PipelineSettings,
    row: pd.Series,
    reason_row: pd.Series | None,
    *,
    extended: bool = False,
) -> str:
    prompt = _leadership_prompt(row, reason_row, extended=extended)
    max_chars = 1100 if extended else 900
    num_predict = 480 if cfg.llm_fast_mode else 640
    if extended:
        num_predict = 600 if cfg.llm_fast_mode else 800
    try:
        text = _chat(
            cfg,
            prompt,
            one_sentence=False,
            num_predict=num_predict,
            max_chars=max_chars,
        )
        if is_complete_summary(text):
            return text
        fallback = template_top3_paragraph(row, reason_row) if extended else template_municipality_paragraph(row, reason_row)
        return fallback
    except Exception:
        if extended:
            return template_top3_paragraph(row, reason_row)
        return template_municipality_paragraph(row, reason_row)


def summary_to_one_liner(text: str) -> str:
    """Краткая строка для таблицы Top-10 — не для блока «Аналитическая сводка»."""
    return normalize_llm_summary(text, one_sentence=True, max_chars=220)


def _parallel_municipality_summaries(
    rank_df: pd.DataFrame,
    reasons_df: pd.DataFrame,
    cfg: PipelineSettings,
    *,
    extended: bool = False,
) -> pd.DataFrame:
    if rank_df.empty:
        return pd.DataFrame()

    reason_by_muni = reasons_df.set_index("муниципалитет") if not reasons_df.empty else pd.DataFrame()
    workers = max(1, min(cfg.llm_workers, len(rank_df)))
    rows_map: dict[str, dict] = {}

    def _one(row: pd.Series) -> tuple[str, dict]:
        muni = str(row["муниципалитет"])
        reason = reason_by_muni.loc[muni] if muni in reason_by_muni.index else None
        summary = _summarize_municipality_llm(cfg, row, reason, extended=extended)
        return muni, {
            "district_id": int(row["district_id"]),
            "муниципалитет": muni,
            "rank": int(row["rank"]),
            "problem_count": int(row["problem_count"]),
            "summary": summary,
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, row) for _, row in rank_df.iterrows()]
        for fut in as_completed(futures):
            muni, payload = fut.result()
            rows_map[muni] = payload

    ordered = [rows_map[str(m)] for m in rank_df["муниципалитет"] if str(m) in rows_map]
    return pd.DataFrame(ordered)


def build_municipality_summaries(
    top10: pd.DataFrame,
    reasons_df: pd.DataFrame,
    cfg: PipelineSettings,
) -> pd.DataFrame:
    """ИИ-сводки по Top-10 для руководства (параллельно через Ollama)."""
    return _parallel_municipality_summaries(top10, reasons_df, cfg, extended=False)


def build_top3_summaries(
    top3: pd.DataFrame,
    reasons_df: pd.DataFrame,
    cfg: PipelineSettings,
) -> pd.DataFrame:
    """Развёрнутые ИИ-сводки по критическим Top-3."""
    return _parallel_municipality_summaries(top3, reasons_df, cfg, extended=True)


def attach_summary_text_from_paragraphs(
    reasons_df: pd.DataFrame,
    summaries_df: pd.DataFrame,
) -> pd.DataFrame:
    """Краткая строка для таблицы — первое предложение из ИИ-сводки."""
    if reasons_df.empty or summaries_df.empty or "summary" not in summaries_df.columns:
        return reasons_df
    short = summaries_df[["муниципалитет", "summary"]].copy()
    short["summary_text"] = short["summary"].astype(str).map(summary_to_one_liner)
    out = reasons_df.drop(columns=["summary_text"], errors="ignore").merge(
        short[["муниципалитет", "summary_text"]],
        on="муниципалитет",
        how="left",
    )
    return out


def _attach_summary_paragraphs(
    rank_df: pd.DataFrame,
    summaries_df: pd.DataFrame,
) -> pd.DataFrame:
    if rank_df.empty or summaries_df.empty or "summary" not in summaries_df.columns:
        return rank_df
    merged = summaries_df[["муниципалитет", "summary"]].rename(columns={"summary": "summary_paragraph"})
    out = rank_df.merge(merged, on="муниципалитет", how="left")
    return out


def _region_stats_block(problems_df: pd.DataFrame, top_all: pd.DataFrame) -> str:
    total = len(problems_df)
    prob = int(problems_df.get("is_problem", problems_df["severity"] > 0).sum()) if total else 0
    critical = int((problems_df["severity"] >= 4).sum()) if "severity" in problems_df.columns else 0
    muni_n = len(top_all) if top_all is not None and not top_all.empty else 0
    return (
        f"Всего проблемных обращений в срезе: {prob}. "
        f"Критических (класс 4): {critical}. "
        f"Муниципалитетов в рейтинге: {muni_n}."
    )


def build_executive_summary(
    problems_df: pd.DataFrame,
    top3: pd.DataFrame,
    top10: pd.DataFrame,
    reasons_df: pd.DataFrame,
    cfg: PipelineSettings,
    top_all: pd.DataFrame | None = None,
) -> str:
    ref_top_all = top_all if top_all is not None else pd.DataFrame()
    blocks: list[str] = [_region_stats_block(problems_df, ref_top_all)]

    blocks.append("\nTop-3 (критические муниципалитеты):")
    for _, row in top3.iterrows():
        muni = row["муниципалитет"]
        blocks.append(
            f"- #{row['rank']} {muni}: скор {int(row.get('score', 0))}, "
            f"{int(row['problem_count'])} проблем из {int(row.get('total_incidents', 0))} "
            f"({float(row.get('problem_share', 0)):.0%}), "
            f"критических {int(row.get('critical_count', 0))}, "
            f"ср.тяжесть {float(row.get('severity_mean', 0)):.1f}"
        )
        blocks.append(f"  топ-тема: {row.get('топ_тема', '')}")
        blocks.append(f"  топ-группа: {row.get('топ_группа', '')}")
        if not reasons_df.empty:
            sub = reasons_df[reasons_df["муниципалитет"] == muni]
            if len(sub) and sub.iloc[0].get("summary_text"):
                blocks.append(f"  вывод: {sub.iloc[0]['summary_text']}")

    blocks.append("\nTop-10 (все проблемные муниципалитеты):")
    for _, row in top10.iterrows():
        muni = row["муниципалитет"]
        blocks.append(
            f"- #{int(row['rank'])} {muni}: скор {int(row.get('score', 0))}, "
            f"{int(row['problem_count'])} проблем из {int(row.get('total_incidents', 0))} "
            f"({float(row.get('problem_share', 0)):.0%}), "
            f"тема «{row.get('топ_тема', '')}», группа «{row.get('топ_группа', '')}»"
        )
        if not reasons_df.empty:
            sub = reasons_df[reasons_df["муниципалитет"] == muni]
            if len(sub) and sub.iloc[0].get("summary_text"):
                blocks.append(f"  вывод: {sub.iloc[0]['summary_text']}")
        if row.get("summary_paragraph") is not None and str(row.get("summary_paragraph", "")).strip():
            blocks.append(f"  абзац: {row['summary_paragraph']}")

    context = "\n".join(blocks)
    prompt = (
        "Составь справку для руководства по мониторингу обращений граждан Омской области.\n"
        "Структура (markdown допустим):\n"
        "1) Заголовок\n"
        "2) Общая картина по области — 1 абзац с цифрами\n"
        "3) Top-3 (критические) — по 3–4 предложения на муниципалитет с темами и рисками\n"
        "4) Top-10 — нумерованный список всех 10 МО: место, скор, проблемы, главная тема, краткий вывод (1 предложение)\n"
        "5) Системные риски — маркированный список (3–5 пунктов)\n"
        "6) Рекомендации — нумерованный список (3 пункта), привязанных к данным\n\n"
        f"Данные:\n{context}\n"
    )
    return _chat(cfg, prompt, one_sentence=False)


def build_district_report_summary(
    df: pd.DataFrame,
    district_name: str,
    cfg: PipelineSettings,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    work = df[df["муниципалитет"].astype(str) == str(district_name)].copy()
    if start_date and "дата_создания" in work.columns:
        work = work[work["дата_создания"].astype(str) >= start_date]
    if end_date and "дата_создания" in work.columns:
        work = work[work["дата_создания"].astype(str) <= end_date]

    problems = work.loc[work.get("is_problem", work["severity"] > 0).fillna(False)]
    if problems.empty:
        return f"В муниципалитете «{district_name}» проблемных обращений не выявлено."

    theme_stats = (
        problems.groupby("тема")
        .agg(count=("row_id", "count"), severity_mean=("severity", "mean"))
        .reset_index()
        .sort_values("count", ascending=False)
        .head(6)
    )
    groups_block = (
        problems.groupby("группа")
        .agg(count=("row_id", "count"))
        .reset_index()
        .sort_values("count", ascending=False)
        .head(4)
    )
    themes_block = "\n".join(
        f"- {r['тема']}: {int(r['count'])} (ср. {r['severity_mean']:.1f})"
        for _, r in theme_stats.iterrows()
    )
    groups_lines = "\n".join(f"- {r['группа']}: {int(r['count'])}" for _, r in groups_block.iterrows())
    examples = sample_problem_texts(problems, district_name, n=3)

    prompt = (
        f"Сводка для руководства по муниципалитету «{district_name}».\n"
        f"Проблемных: {len(problems)} из {len(work)}, ср.тяжесть {problems['severity'].mean():.2f}, "
        f"критических: {(problems['severity'] >= 4).sum()}\n\n"
        f"Темы:\n{themes_block}\n\nГруппы:\n{groups_lines}\n\n"
        f"Примеры (обезличенно): "
        + "; ".join(truncate_text(e["text"]) for e in examples)
        + "\n\n"
        "Напиши 4–5 предложений: ситуация, ключевые проблемы, причины, 2 управленческих шага. "
        "Простой деловой язык, без списков."
    )
    return _chat(cfg, prompt, one_sentence=False, num_predict=560, max_chars=900)


def save_summary_artifacts(
    output_dir: Path,
    executive_summary: str,
    top3_df: pd.DataFrame,
    top10_df: pd.DataFrame,
    cfg: PipelineSettings,
    meta: dict,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    executive_path = output_dir / "executive_summary.md"
    executive_path.write_text(executive_summary, encoding="utf-8")

    briefs_lines = ["# Справки по муниципалитетам\n", "## Top-3 (критические)\n"]
    for _, row in top3_df.iterrows():
        briefs_lines.append(f"### {row.get('rank')}. {row['муниципалитет']}\n")
        briefs_lines.append(f"{row.get('summary', '')}\n")
    briefs_lines.append("\n## Top-10\n")
    for _, row in top10_df.iterrows():
        briefs_lines.append(f"### {row.get('rank')}. {row['муниципалитет']}\n")
        briefs_lines.append(f"{row.get('summary', '')}\n")
    (output_dir / "municipality_briefs.md").write_text("\n".join(briefs_lines), encoding="utf-8")

    top3_path = output_dir / "top3_summaries.xlsx"
    top3_df.to_excel(top3_path, index=False, engine="openpyxl")
    top10_path = output_dir / "top10_summaries.xlsx"
    top10_df.to_excel(top10_path, index=False, engine="openpyxl")
    # обратная совместимость
    top10_df.to_excel(output_dir / "municipality_summaries.xlsx", index=False, engine="openpyxl")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": cfg.ollama_model or OLLAMA_MODEL,
        "llm_fast_mode": cfg.llm_fast_mode,
        "executive_summary": executive_summary,
        "top3": top3_df.fillna("").to_dict(orient="records"),
        "top10": top10_df.fillna("").to_dict(orient="records"),
        "municipalities": top10_df.fillna("").to_dict(orient="records"),
        "meta": meta,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
