"""Derive suggested product opportunities from themes.

The one rule every function here must never break: every `Evidence.quote`
must be the *exact* text of a real `FeedbackItem`. Nothing here is allowed
to summarize, paraphrase, or invent a quote — that's what makes the
decision brief's evidence trustworthy. See the traceability tests in
tests/test_opportunities.py.
"""

from __future__ import annotations

from app import sentiment
from app.models import Evidence, FeedbackItem, Opportunity, Theme

TOP_N_OPPORTUNITIES = 3
MAX_EVIDENCE_PER_SIDE = 5


def _evidence_for(item: FeedbackItem) -> Evidence:
    return Evidence(item_id=item.id, quote=item.text, source_row=item.source_row)


def opportunity_title_for_theme(theme: Theme) -> str:
    return f"Address: {theme.label}"


def derive_opportunities(
    themes: list[Theme],
    items_by_id: dict[str, FeedbackItem],
    top_n: int = TOP_N_OPPORTUNITIES,
) -> list[Opportunity]:
    scored: list[tuple[float, Theme, list[FeedbackItem], list[FeedbackItem]]] = []

    for theme in themes:
        members = [items_by_id[item_id] for item_id in theme.item_ids]
        negative = [m for m in members if sentiment.classify(m.text) == "negative"]
        positive = [m for m in members if sentiment.classify(m.text) == "positive"]
        # More complaints raise the score; praise pulls it down and can push
        # it negative on its own (an all-praise theme should rank below a
        # mixed or neutral one, not just lower among problems).
        opportunity_score = len(negative) - 0.5 * len(positive)
        scored.append((opportunity_score, theme, negative, positive))

    # Deterministic ordering: score desc, then raw member count desc, then id
    # (ties are common on small datasets and tests rely on a stable order).
    scored.sort(key=lambda row: (-row[0], -row[1].count, row[1].id))

    opportunities: list[Opportunity] = []
    for index, (_, theme, negative, positive) in enumerate(scored[:top_n]):
        opportunities.append(
            Opportunity(
                id=f"opp-{index}",
                theme_id=theme.id,
                title=opportunity_title_for_theme(theme),
                supporting_evidence=[_evidence_for(m) for m in negative[:MAX_EVIDENCE_PER_SIDE]],
                conflicting_evidence=[_evidence_for(m) for m in positive[:MAX_EVIDENCE_PER_SIDE]],
                count=theme.count,
            )
        )
    return opportunities
