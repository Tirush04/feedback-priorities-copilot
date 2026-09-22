from __future__ import annotations

from app.models import Theme
from app.opportunities import TOP_N_OPPORTUNITIES, derive_opportunities


def test_returns_at_most_top_n(opportunity_fixture):
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes, items_by_id)
    assert len(opportunities) == TOP_N_OPPORTUNITIES


def test_ranking_prefers_more_complaints_and_fewer_compliments(opportunity_fixture):
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes, items_by_id)
    theme_order = [o.theme_id for o in opportunities]
    # theme-a: 3 negative/1 positive; theme-b: 2/0; theme-c: 1/2; theme-d: 0/2 (excluded)
    assert theme_order == ["theme-a", "theme-b", "theme-c"]


def test_low_signal_theme_is_excluded_when_over_capacity(opportunity_fixture):
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes, items_by_id)
    assert "theme-d" not in [o.theme_id for o in opportunities]


def test_returns_fewer_than_top_n_when_fewer_themes_exist(opportunity_fixture):
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes[:1], items_by_id)
    assert len(opportunities) == 1


def test_every_evidence_quote_is_verbatim_from_source(opportunity_fixture):
    """The core trust contract: nothing in an opportunity is paraphrased."""
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes, items_by_id)
    checked = 0
    for opportunity in opportunities:
        for evidence in opportunity.supporting_evidence + opportunity.conflicting_evidence:
            source_item = items_by_id[evidence.item_id]
            assert evidence.quote == source_item.text
            assert evidence.source_row == source_item.source_row
            checked += 1
    assert checked > 0  # sanity: the fixture actually produced evidence to check


def test_supporting_and_conflicting_buckets_are_correct(opportunity_fixture):
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes, items_by_id)
    theme_a_opp = next(o for o in opportunities if o.theme_id == "theme-a")
    assert {e.item_id for e in theme_a_opp.supporting_evidence} == {"a1", "a2", "a3"}
    assert {e.item_id for e in theme_a_opp.conflicting_evidence} == {"a4"}


def test_theme_with_no_conflicting_evidence_returns_empty_list(opportunity_fixture):
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes, items_by_id)
    theme_b_opp = next(o for o in opportunities if o.theme_id == "theme-b")
    assert theme_b_opp.conflicting_evidence == []
    assert len(theme_b_opp.supporting_evidence) == 2


def test_title_reflects_theme_label():
    items_by_id = {}
    theme = Theme(id="theme-x", label="Slow Checkout", keywords=["slow"], item_ids=[])
    opportunities = derive_opportunities([theme], items_by_id)
    assert opportunities[0].title == "Address: Slow Checkout"


def test_new_opportunity_starts_unset_priority(opportunity_fixture):
    items_by_id, themes = opportunity_fixture
    opportunities = derive_opportunities(themes, items_by_id)
    assert all(o.priority == "Unset" for o in opportunities)
