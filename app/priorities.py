"""Let a PM set priorities on suggested opportunities."""

from __future__ import annotations

from app.models import VALID_PRIORITIES, Opportunity, Priority


class OpportunityNotFound(KeyError):
    """Raised when an opportunity id doesn't exist in the given list."""


class InvalidPriority(ValueError):
    """Raised when a priority value isn't one of the allowed levels."""


def set_priority(
    opportunities: list[Opportunity],
    opportunity_id: str,
    priority: Priority,
    notes: str = "",
) -> Opportunity:
    if priority not in VALID_PRIORITIES:
        raise InvalidPriority(
            f"{priority!r} is not a valid priority; use one of {VALID_PRIORITIES}"
        )
    for opportunity in opportunities:
        if opportunity.id == opportunity_id:
            opportunity.priority = priority
            opportunity.notes = notes
            return opportunity
    raise OpportunityNotFound(opportunity_id)
