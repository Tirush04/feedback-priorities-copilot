"""Shared dict-serialization for API responses and the exported brief.

Both app/main.py (JSON API responses) and app/export.py (the decision
brief) need to turn an Opportunity/Evidence into a plain dict. Keeping one
copy of that logic means a future field added to those dataclasses cant
silently drift out of sync between the two call sites.
"""

from __future__ import annotations

from app.models import Evidence, Opportunity


def evidence_to_dict(evidence: Evidence) -> dict:
    return {"item_id": evidence.item_id, "quote": evidence.quote, "source_row": evidence.source_row}


def opportunity_to_dict(opportunity: Opportunity) -> dict:
    return {
        "id": opportunity.id,
        "theme_id": opportunity.theme_id,
        "title": opportunity.title,
        "priority": opportunity.priority,
        "notes": opportunity.notes,
        "count": opportunity.count,
        "supporting_evidence": [evidence_to_dict(e) for e in opportunity.supporting_evidence],
        "conflicting_evidence": [evidence_to_dict(e) for e in opportunity.conflicting_evidence],
    }