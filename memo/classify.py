from __future__ import annotations

import re
from collections import Counter

from .config import TaxonomyConfig
from .models import ClassificationResult, StageItem


TODO_KEYWORDS = {
    "todo",
    "to-do",
    "task",
    "next",
    "follow up",
    "action item",
    "deadline",
    "due",
    "must",
    "need to",
    "should",
}
IDEA_KEYWORDS = {
    "idea",
    "brainstorm",
    "concept",
    "proposal",
    "hypothesis",
    "what if",
    "could we",
    "maybe",
    "experiment",
}
REFERENCE_KEYWORDS = {
    "reference",
    "link",
    "documentation",
    "doc",
    "api",
    "guide",
    "source",
    "citation",
    "how-to",
}
LOG_KEYWORDS = {
    "today",
    "yesterday",
    "update",
    "status",
    "progress",
    "retrospective",
    "done",
    "completed",
    "blocked",
}

HASHTAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_-]{1,40})")
URL_RE = re.compile(r"https?://")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
CHECKBOX_RE = re.compile(r"^\s*[-*]\s*\[[ xX]\]", re.MULTILINE)


def _keyword_score(text: str, keywords: set[str]) -> int:
    score = 0
    for keyword in keywords:
        if keyword in text:
            score += 1
    return score


def _compute_scores(text: str) -> Counter[str]:
    lowered = text.lower()
    scores: Counter[str] = Counter({"idea": 0, "todo": 0, "reference": 0, "log": 0})

    scores["todo"] += _keyword_score(lowered, TODO_KEYWORDS)
    scores["idea"] += _keyword_score(lowered, IDEA_KEYWORDS)
    scores["reference"] += _keyword_score(lowered, REFERENCE_KEYWORDS)
    scores["log"] += _keyword_score(lowered, LOG_KEYWORDS)

    if CHECKBOX_RE.search(text):
        scores["todo"] += 3
    if URL_RE.search(text):
        scores["reference"] += 2
    if DATE_RE.search(text):
        scores["log"] += 1

    if "?" in text and any(token in lowered for token in ("could", "maybe", "what if")):
        scores["idea"] += 1

    return scores


def _extract_tags(item: StageItem, category: str, allow_custom_tags: bool) -> list[str]:
    tags: set[str] = {category}

    if category == "todo":
        lowered = item.body.lower()
        if "urgent" in lowered or "asap" in lowered:
            tags.add("priority")
        if "deadline" in lowered or "due" in lowered:
            tags.add("deadline")

    if allow_custom_tags:
        for match in HASHTAG_RE.findall(item.content):
            tags.add(match.lower())

    return sorted(tags)


def classify_item(item: StageItem, taxonomy: TaxonomyConfig) -> ClassificationResult:
    scores = _compute_scores(item.content)
    sorted_scores = scores.most_common()

    top_category, top_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0
    total = sum(scores.values())

    if top_score == 0:
        category = "reference"
        confidence = 0.25
        reasoning = "no strong lexical signal; defaulted to reference"
    else:
        category = top_category
        confidence = round(top_score / max(total, 1), 3)
        if top_score - second_score <= 1:
            confidence = min(confidence, 0.45)
            reasoning = "ambiguous lexical signal across categories"
        else:
            reasoning = f"dominant lexical signal in {top_category}"

    if category not in taxonomy.core_categories:
        category = "reference"
        confidence = min(confidence, 0.35)
        reasoning = "category outside configured taxonomy; defaulted to reference"

    tags = _extract_tags(item, category=category, allow_custom_tags=taxonomy.allow_custom_tags)

    return ClassificationResult(category=category, tags=tags, confidence=confidence, reasoning=reasoning)
