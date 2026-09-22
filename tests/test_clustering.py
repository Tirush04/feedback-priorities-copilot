from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.clustering import MIN_ITEMS_FOR_CLUSTERING, _label_for_cluster, cluster_feedback
from app.models import FeedbackItem


def _theme_for_item(themes, item_id: str):
    for theme in themes:
        if item_id in theme.item_ids:
            return theme
    raise AssertionError(f"{item_id} was not placed in any theme")


def test_empty_input_returns_no_themes():
    assert cluster_feedback([]) == []


def test_below_minimum_returns_single_general_theme():
    items = [
        FeedbackItem(id=f"i{i}", text=f"comment {i}", source_row=i)
        for i in range(MIN_ITEMS_FOR_CLUSTERING - 1)
    ]
    themes = cluster_feedback(items)
    assert len(themes) == 1
    assert set(themes[0].item_ids) == {item.id for item in items}


def test_every_item_lands_in_exactly_one_theme(three_topic_items):
    themes = cluster_feedback(three_topic_items)
    all_placed_ids = [item_id for theme in themes for item_id in theme.item_ids]
    # No item dropped, none duplicated across themes.
    assert sorted(all_placed_ids) == sorted(item.id for item in three_topic_items)
    assert len(all_placed_ids) == len(set(all_placed_ids))


def test_well_separated_topics_cluster_together(three_topic_items, three_topic_rows):
    themes = cluster_feedback(three_topic_items)
    assert len(themes) >= 2  # at minimum it found *some* structure

    by_topic_id = {}
    row_number = 1
    for topic, rows in three_topic_rows.items():
        ids = []
        for _ in rows:
            ids.append(f"item-{row_number}")
            row_number += 1
        by_topic_id[topic] = ids

    # Purity check: every item that belongs to the same known topic must be
    # placed in the same theme as at least one other item from that topic
    # (i.e. the topic wasn't shattered across every theme individually).
    for topic, ids in by_topic_id.items():
        theme_ids_used = {_theme_for_item(themes, item_id).id for item_id in ids}
        assert len(theme_ids_used) <= 2, (
            f"{topic} feedback was scattered across {len(theme_ids_used)} themes: "
            f"expected it to mostly land in one or two"
        )


def test_theme_keywords_are_non_empty(three_topic_items):
    themes = cluster_feedback(three_topic_items)
    for theme in themes:
        assert theme.keywords, f"theme {theme.id} has no keywords"


def test_label_falls_back_when_centroid_has_no_signal():
    vectorizer = TfidfVectorizer()
    vectorizer.fit(["alpha beta", "gamma delta"])
    zero_centroid = np.zeros(len(vectorizer.get_feature_names_out()))
    label, keywords = _label_for_cluster(vectorizer, zero_centroid)
    assert keywords == ["general feedback"]
    assert label == "General Feedback"


def test_clustering_is_deterministic(three_topic_items):
    first = cluster_feedback(three_topic_items)
    second = cluster_feedback(three_topic_items)
    first_groups = sorted(tuple(sorted(t.item_ids)) for t in first)
    second_groups = sorted(tuple(sorted(t.item_ids)) for t in second)
    assert first_groups == second_groups
