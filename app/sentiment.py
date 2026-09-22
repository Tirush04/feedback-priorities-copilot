"""Lightweight lexicon-based sentiment scoring.

Not a real sentiment model — a small, auditable word list. It exists to
split a theme's quotes into "this is a problem" (supporting evidence for
an opportunity) versus "this is already fine" (conflicting evidence),
per the PRD. Good enough for that binary; not a general-purpose sentiment
classifier.
"""

from __future__ import annotations

import re
from typing import Literal

Sentiment = Literal["positive", "negative", "neutral"]

NEGATIVE_WORDS = {
    "slow", "late", "delayed", "delay", "broken", "confusing", "confused",
    "expensive", "overpriced", "bug", "buggy", "crash", "crashes", "bad",
    "terrible", "annoying", "difficult", "frustrating", "frustrated", "poor",
    "hate", "worst", "fail", "fails", "failed", "cannot", "cant", "wont",
    "complicated", "hard", "unclear", "missing", "lacking", "disappointed",
    "disappointing", "unreliable", "clunky", "awkward", "painful", "issue",
    "issues", "problem", "problems", "never", "unusable", "laggy",
}

POSITIVE_WORDS = {
    "love", "loved", "great", "good", "easy", "fast", "smooth", "excellent",
    "amazing", "perfect", "helpful", "intuitive", "reliable", "happy",
    "satisfied", "best", "awesome", "simple", "quick", "seamless", "nice",
    "works", "working", "solid", "delightful", "pleasant", "convenient",
}

_WORD_RE = re.compile(r"[a-z']+")


def _tokenize(text: str) -> list[str]:
    # Drop apostrophes entirely (not just at the edges) so "can't" -> "cant",
    # matching the lexicon below, instead of surviving as "can't".
    return [w.replace("'", "") for w in _WORD_RE.findall(text.lower())]


def score(text: str) -> float:
    """Return a value in [-1, 1]; 0 for neutral or lexicon-free text."""
    words = _tokenize(text)
    if not words:
        return 0.0
    negative = sum(1 for w in words if w in NEGATIVE_WORDS)
    positive = sum(1 for w in words if w in POSITIVE_WORDS)
    total = negative + positive
    if total == 0:
        return 0.0
    return (positive - negative) / total


def classify(text: str, threshold: float = 0.0) -> Sentiment:
    value = score(text)
    if value > threshold:
        return "positive"
    if value < -threshold:
        return "negative"
    return "neutral"
