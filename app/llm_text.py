"""Нормализация ответов LLM: убираем «варианты», преамбулы и markdown-обёртку."""

from __future__ import annotations

import re

_META_PATTERNS = (
    r"учитывая\s+что",
    r"вот\s+несколько\s+вариантов",
    r"в\s+зависимости\s+от\s+того",
    r"можно\s+использовать\s+следующ",
    r"для\s+руководства[,:\s]",
    r"рекомендация\s*:",
    r"почему\s+этот\s+вариант",
    r"вот\s+несколько\s+вариантов",
)

_VARIANT_BLOCK = re.compile(
    r"###\s*Вариант\s*1[^\n]*\n+(?:>\s*)?\*\*(.+?)\*\*",
    re.IGNORECASE | re.DOTALL,
)
_BLOCKQUOTE_BOLD = re.compile(r">\s*\*\*(.+?)\*\*", re.DOTALL)
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def _strip_markdown(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^#+\s*.+$", "", t, flags=re.MULTILINE)
    t = re.sub(r"^>\s?", "", t, flags=re.MULTILINE)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"\*(.+?)\*", r"\1", t)
    t = re.sub(r"^---+.*$", "", t, flags=re.MULTILINE)
    t = re.sub(r"\[Текущая дата\]", "", t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()


def _looks_like_meta(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in _META_PATTERNS) or "вариант 2" in low


def _extract_core(text: str) -> str:
    m = _VARIANT_BLOCK.search(text)
    if m:
        return m.group(1).strip()

    quotes = _BLOCKQUOTE_BOLD.findall(text)
    if quotes:
        return quotes[0].strip()

    bolds = _BOLD.findall(text)
    if bolds and _looks_like_meta(text):
        return max(bolds, key=len).strip()

    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(parts) >= 2 and _looks_like_meta(parts[0]):
        return parts[-1]

    return text


def normalize_llm_summary(text: str, *, one_sentence: bool = True, max_chars: int = 800) -> str:
    """Приводит ответ модели к готовому тексту для UI."""
    if not text or not str(text).strip():
        return ""

    raw = str(text).strip()
    if not _looks_like_meta(raw) and not raw.startswith("###") and "**" not in raw[:80]:
        core = _strip_markdown(raw)
    else:
        core = _strip_markdown(_extract_core(raw))

    if not core:
        core = _strip_markdown(raw)

    if one_sentence:
        sentences = [s.strip() for s in _SENTENCE_END.split(core) if s.strip()]
        if sentences:
            core = sentences[0]
            if not core.endswith((".", "!", "?", "…")):
                core += "."

    if len(core) > max_chars:
        chunk = core[:max_chars]
        sentences = [s.strip() for s in _SENTENCE_END.split(chunk) if s.strip()]
        if len(sentences) > 1:
            core = " ".join(sentences[:-1])
            if not core.endswith((".", "!", "?", "…")):
                core += "."
        else:
            core = chunk.rsplit(" ", 1)[0] + "…"

    return core


def is_complete_summary(text: str, *, min_len: int = 40) -> bool:
    t = str(text or "").strip()
    return len(t) >= min_len and t[-1] in ".!?…"
