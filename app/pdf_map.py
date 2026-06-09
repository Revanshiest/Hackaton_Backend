"""Карта муниципалитетов для PDF (GeoJSON + matplotlib)."""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.lines import Line2D

from app.config.paths import PROJECT_ROOT

BOUNDARIES_PATH = PROJECT_ROOT / "frontend" / "src" / "data" / "omsk_boundaries.json"

CITY_MARKER = {
    "lat": 54.9893,
    "lon": 73.3682,
    "match": re.compile(r"омск\s*г\.?\s*о\.?", re.I),
}

OSM_ALIASES = {"омский": "омский"}


def _normalize_district_name(name: str) -> str:
    s = str(name or "").lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r",\s*другое$", "", s)
    s = re.sub(r"\s+(район|округ)\s*$", "", s)
    s = re.sub(r"\s+г\.?\s*о\.?\s*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _root_token(norm: str) -> str:
    token = (norm.split() or [""])[0]
    token = re.sub(r"(ский|ской)$", "", token)
    return token.replace("цев", "цев")


def _roots_compatible(osm_norm: str, api_norm: str) -> bool:
    if osm_norm == api_norm:
        return True
    osm_root = _root_token(osm_norm)
    api_root = _root_token(api_norm)
    if len(osm_root) < 5 or len(api_root) < 5:
        return False
    return osm_root == api_root


def match_district(osm_name: str, districts: list[Any]) -> Any | None:
    if not osm_name or not districts:
        return None
    osm_norm = _normalize_district_name(osm_name)
    if not osm_norm:
        return None

    for d in districts:
        name = getattr(d, "district_name", None) or getattr(d, "name", "")
        if _normalize_district_name(name) == osm_norm:
            return d

    alias = OSM_ALIASES.get(osm_norm)
    if alias:
        for d in districts:
            name = getattr(d, "district_name", None) or getattr(d, "name", "")
            if _normalize_district_name(name) == alias:
                return d

    for d in districts:
        name = getattr(d, "district_name", None) or getattr(d, "name", "")
        if _roots_compatible(osm_norm, _normalize_district_name(name)):
            return d
    return None


def find_city_marker_district(districts: list[Any]) -> Any | None:
    for d in districts:
        name = getattr(d, "district_name", None) or getattr(d, "name", "")
        if CITY_MARKER["match"].search(str(name or "")):
            return d
    return None


def score_to_color(score: int | None) -> str:
    if score is None:
        return "#cbd5e1"
    if score >= 75:
        return "#991b1b"
    if score >= 60:
        return "#ef4444"
    if score >= 50:
        return "#f97316"
    if score >= 35:
        return "#84cc16"
    return "#22c55e"


@lru_cache(maxsize=1)
def _load_boundaries() -> dict:
    if not BOUNDARIES_PATH.exists():
        raise FileNotFoundError(f"GeoJSON не найден: {BOUNDARIES_PATH}")
    return json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))


def _iter_rings(geometry: dict) -> list[list[tuple[float, float]]]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    rings: list[list[tuple[float, float]]] = []
    if gtype == "Polygon":
        if coords:
            rings.append([(float(lon), float(lat)) for lon, lat in coords[0]])
    elif gtype == "MultiPolygon":
        for poly in coords:
            if poly:
                rings.append([(float(lon), float(lat)) for lon, lat in poly[0]])
    return rings


def render_region_map_figure(districts: list[Any]):
    """Matplotlib figure: карта области с раскраской по индексу."""
    geo = _load_boundaries()
    fig, ax = plt.subplots(figsize=(7.4, 5.6))
    ax.set_facecolor("#f8fafc")

    for feature in geo.get("features", []):
        props = feature.get("properties") or {}
        osm_name = props.get("name") or props.get("name:ru") or ""
        district = match_district(osm_name, districts)
        score = int(getattr(district, "score", 0)) if district else None
        color = score_to_color(score)
        for ring in _iter_rings(feature.get("geometry") or {}):
            ax.add_patch(
                MplPolygon(
                    ring,
                    closed=True,
                    facecolor=color,
                    edgecolor="#9ca3af",
                    linewidth=0.55,
                    alpha=0.78,
                )
            )

    city = find_city_marker_district(districts)
    if city:
        # scatter — круг в пикселях, не сплющивается из-за aspect карты
        ax.scatter(
            [CITY_MARKER["lon"]],
            [CITY_MARKER["lat"]],
            s=58,
            marker="o",
            c=score_to_color(int(city.score)),
            edgecolors="#7f1d1d",
            linewidths=1.2,
            zorder=5,
            clip_on=False,
        )

    ax.set_xlim(68.0, 78.0)
    ax.set_ylim(52.5, 59.5)
    # поправка широты: 1° долготы на ~56° с.ш. короче 1° широты
    ax.set_aspect(1 / math.cos(math.radians(55.8)), adjustable="box")
    ax.axis("off")

    legend_items = [
        ("75+", "#22c55e"),
        ("60–74", "#84cc16"),
        ("50–59", "#f97316"),
        ("35–49", "#ef4444"),
        ("<35", "#991b1b"),
        ("нет данных", "#cbd5e1"),
    ]
    handles = [
        Line2D([0], [0], marker="s", color="w", markerfacecolor=c, markersize=8, label=label)
        for label, c in legend_items
    ]
    ax.legend(
        handles=handles,
        loc="lower left",
        fontsize=7,
        framealpha=0.92,
        title="Индекс (чем ниже — хуже)",
        title_fontsize=7,
    )
    fig.tight_layout(pad=0.4)
    return fig
