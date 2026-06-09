"""Сопоставление «Группа тем» → ведомство Омской области."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

MAPPING_PATH = Path(__file__).resolve().parents[1] / "data" / "agency_mapping.json"
_UNSAFE_PATH = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@lru_cache(maxsize=1)
def load_agency_mapping() -> dict:
    with MAPPING_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def resolve_agency(group: str) -> str:
    """Возвращает полное название ведомства для группы тем."""
    mapping = load_agency_mapping()
    key = str(group or "").strip()
    if not key:
        return mapping.get("fallback_agency", "Иные ведомства")
    return mapping.get("group_to_agency", {}).get(key, mapping.get("fallback_agency", key))


def region_name() -> str:
    return str(load_agency_mapping().get("region", "Омская область"))


def safe_path_segment(name: str, *, max_len: int = 80) -> str:
    """Безопасное имя папки/файла в ZIP."""
    cleaned = _UNSAFE_PATH.sub("_", str(name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        cleaned = "unnamed"
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1].rstrip() + "…"
    return cleaned
