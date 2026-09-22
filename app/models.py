"""Core data model.

Every quote that ever reaches a theme, an opportunity, or the exported
decision brief is carried as an `Evidence` object that points back at the
original `FeedbackItem` it came from. Nothing downstream is allowed to
paraphrase or fabricate a quote — see `app/opportunities.py` and the
evidence-integrity tests in `tests/test_opportunities.py` /
`tests/test_priorities_export.py` for the contract this enforces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, get_args

Priority = Literal["High", "Medium", "Low", "Unset"]

# Derived from the Literal itself (not re-typed) so the two can never drift apart.
VALID_PRIORITIES: tuple[Priority, ...] = get_args(Priority)


@dataclass(frozen=True)
class FeedbackItem:
    """One row of the uploaded CSV, normalized."""

    id: str
    text: str
    source_row: int  # 1-based row number in the original CSV (header excluded)


@dataclass
class Theme:
    """A cluster of feedback items with an editable, human-facing label."""

    id: str
    label: str
    keywords: list[str]
    item_ids: list[str]

    @property
    def count(self) -> int:
        return len(self.item_ids)


@dataclass(frozen=True)
class Evidence:
    """A verbatim quote, traceable to its source row."""

    item_id: str
    quote: str
    source_row: int


@dataclass
class Opportunity:
    """A suggested product opportunity derived from one theme."""

    id: str
    theme_id: str
    title: str
    supporting_evidence: list[Evidence]
    conflicting_evidence: list[Evidence]
    count: int
    priority: Priority = "Unset"
    notes: str = ""


@dataclass
class DecisionBrief:
    """The exportable artifact a PM hands to the team."""

    session_id: str
    generated_at: str
    total_feedback_items: int
    opportunities: list[Opportunity] = field(default_factory=list)
