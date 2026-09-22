from __future__ import annotations

import json

import pytest

from app.export import render_brief_json, render_brief_markdown
from app.models import DecisionBrief
from app.opportunities import derive_opportunities
from app.priorities import InvalidPriority, OpportunityNotFound, set_priority


def test_set_priority_updates_only_the_target_opportunity(opportunity_fixture):
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes, items_by_id)
    target_id = opportunities[0].id
    other_id = opportunities[1].id

    updated = set_priority(opportunities, target_id, "High", notes="Ship this quarter")

    assert updated.priority == "High"
    assert updated.notes == "Ship this quarter"
    other = next(o for o in opportunities if o.id == other_id)
    assert other.priority == "Unset"


def test_set_priority_unknown_id_raises(opportunity_fixture):
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes, items_by_id)
    with pytest.raises(OpportunityNotFound):
        set_priority(opportunities, "opp-does-not-exist", "High")


def test_set_priority_rejects_invalid_value(opportunity_fixture):
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes, items_by_id)
    with pytest.raises(InvalidPriority):
        set_priority(opportunities, opportunities[0].id, "Urgent!!")


def _sample_brief(opportunity_fixture) -> DecisionBrief:
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes, items_by_id)
    set_priority(opportunities, opportunities[0].id, "High", notes="Do this first")
    return DecisionBrief(
        session_id="sess-1",
        generated_at="2026-09-22T00:00:00+00:00",
        total_feedback_items=len(items_by_id),
        opportunities=opportunities,
    )


def test_markdown_brief_contains_every_quote_verbatim(opportunity_fixture):
    brief = _sample_brief(opportunity_fixture)
    markdown = render_brief_markdown(brief)
    for opportunity in brief.opportunities:
        assert opportunity.title in markdown
        for evidence in opportunity.supporting_evidence + opportunity.conflicting_evidence:
            assert evidence.quote in markdown


def test_markdown_brief_shows_the_set_priority(opportunity_fixture):
    brief = _sample_brief(opportunity_fixture)
    markdown = render_brief_markdown(brief)
    assert "**High**" in markdown
    assert "Do this first" in markdown


def test_json_brief_round_trips_and_is_serializable(opportunity_fixture):
    brief = _sample_brief(opportunity_fixture)
    payload = render_brief_json(brief)
    dumped = json.dumps(payload)  # must not raise
    reloaded = json.loads(dumped)

    assert reloaded["session_id"] == "sess-1"
    assert reloaded["total_feedback_items"] == brief.total_feedback_items
    assert len(reloaded["opportunities"]) == len(brief.opportunities)
    first = reloaded["opportunities"][0]
    assert first["priority"] == "High"
    assert first["notes"] == "Do this first"
    for evidence in first["supporting_evidence"]:
        assert "quote" in evidence and "source_row" in evidence


def test_brief_with_no_evidence_side_notes_it_clearly(opportunity_fixture):
    brief = _sample_brief(opportunity_fixture)
    markdown = render_brief_markdown(brief)
    theme_b_opp = next(o for o in brief.opportunities if o.theme_id == "theme-b")
    assert theme_b_opp.conflicting_evidence == []
    assert "none found" in markdown
