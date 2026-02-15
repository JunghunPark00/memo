from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from .config import SummarizationConfig
from .models import StageItem, SummaryResult
from .utils import normalize_for_similarity


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)
ACTION_RE = re.compile(r"^\s*[-*]?\s*(?:\[[ xX]\]\s*)?((?:do|build|write|ship|fix|review|plan|draft|call|email)\b.+)$", re.IGNORECASE)


def load_existing_summary_texts(root: Path) -> list[str]:
    summary_dir = root / "vault" / "summaries"
    if not summary_dir.exists():
        return []
    texts: list[str] = []
    for path in sorted(summary_dir.glob("*.md")):
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return texts


def _word_count(text: str) -> int:
    return len([part for part in re.split(r"\s+", text.strip()) if part])


def _max_similarity(text: str, existing_texts: list[str]) -> float:
    if not existing_texts:
        return 0.0

    candidate = normalize_for_similarity(text)
    best = 0.0
    for existing in existing_texts:
        score = SequenceMatcher(None, candidate, normalize_for_similarity(existing)).ratio()
        if score > best:
            best = score
    return best


def summarization_signals(
    item: StageItem,
    pending_count: int,
    config: SummarizationConfig,
    existing_summary_texts: list[str],
) -> tuple[list[str], float]:
    if not config.enabled:
        return [], 0.0

    signals: list[str] = []
    words = _word_count(item.body)
    if words >= config.min_words:
        signals.append("long_entry")
    if pending_count >= config.batch_trigger_count:
        signals.append("batch_threshold")

    similarity = _max_similarity(item.body, existing_summary_texts)
    if similarity >= config.redundancy_similarity_threshold:
        signals.append("high_redundancy")

    return signals, similarity


def _extract_sentences(text: str) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    return [segment.strip() for segment in SENTENCE_SPLIT_RE.split(normalized) if segment.strip()]


def _extract_key_points(text: str) -> list[str]:
    bullets = [match.strip() for match in BULLET_RE.findall(text)]
    if bullets:
        return bullets[:5]

    sentences = _extract_sentences(text)
    if not sentences:
        return []
    return sentences[:5]


def _extract_actions(text: str) -> list[str]:
    actions: list[str] = []
    for line in text.splitlines():
        match = ACTION_RE.match(line)
        if match:
            actions.append(match.group(1).strip())
        elif re.match(r"^\s*[-*]\s*\[[ xX]\]\s+", line):
            cleaned = re.sub(r"^\s*[-*]\s*\[[ xX]\]\s+", "", line).strip()
            if cleaned:
                actions.append(cleaned)
    unique_actions: list[str] = []
    seen = set()
    for action in actions:
        lowered = action.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique_actions.append(action)
    return unique_actions[:8]


def build_summary(item: StageItem, category: str, triggered_by: list[str], redundancy_score: float) -> SummaryResult:
    sentences = _extract_sentences(item.body)
    short_sentences = sentences[:3]
    short_summary = " ".join(short_sentences)[:500]

    key_points = _extract_key_points(item.body)
    actions: list[str] = []
    if category in {"todo", "idea"}:
        actions = _extract_actions(item.body)

    return SummaryResult(
        short_summary=short_summary,
        key_points=key_points,
        actions=actions,
        triggered_by=triggered_by,
        redundancy_score=round(redundancy_score, 3),
    )
