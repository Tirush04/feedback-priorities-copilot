"""Group feedback items into themes.

Uses TF-IDF + KMeans rather than an LLM call. That's a deliberate MVP
trade-off (see docs/DESIGN_DECISIONS.md): grouping is deterministic,
runs offline, needs no API key, and is trivial to unit-test — at the
cost of theme labels that are keyword phrases rather than fluent prose.
"""

from __future__ import annotations

import re
from collections import Counter

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

from app.models import FeedbackItem, Theme

MIN_ITEMS_FOR_CLUSTERING = 5
MIN_THEMES = 3
MAX_THEMES = 8
RANDOM_STATE = 42


def _label_for_cluster(vectorizer: TfidfVectorizer, centroid, top_n: int = 3) -> tuple[str, list[str]]:
    terms = vectorizer.get_feature_names_out()
    top_indices = centroid.argsort()[::-1][:top_n]
    keywords = [terms[i] for i in top_indices if centroid[i] > 0]
    if not keywords:
        keywords = ["general feedback"]
    label = " / ".join(word.title() for word in keywords)
    return label, keywords


def cluster_feedback(items: list[FeedbackItem]) -> list[Theme]:
    """Cluster feedback items into themes.

    Below MIN_ITEMS_FOR_CLUSTERING, clustering is statistically meaningless,
    so everything is returned as a single "General feedback" theme instead
    of forcing a fake split.
    """
    if not items:
        return []

    if len(items) < MIN_ITEMS_FOR_CLUSTERING:
        return [
            Theme(
                id="theme-0",
                label="General feedback",
                keywords=[],
                item_ids=[item.id for item in items],
            )
        ]

    texts = [item.text for item in items]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=500, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(texts)

    # len(items) >= MIN_ITEMS_FOR_CLUSTERING (5) is guaranteed by the early
    # return above, and MIN_THEMES is 3, so `lower` is always >= 3 here —
    # there is always a real range of candidate k values to search.
    upper = min(MAX_THEMES, len(items) - 1)
    lower = min(MIN_THEMES, upper)

    best_score, best_model = -2.0, None
    for candidate_k in range(lower, upper + 1):
        model = KMeans(n_clusters=candidate_k, random_state=RANDOM_STATE, n_init=10)
        candidate_labels = model.fit_predict(matrix)
        if len(set(candidate_labels)) < 2:
            continue
        score = silhouette_score(matrix, candidate_labels)
        if score > best_score:
            best_score, best_model = score, model
    if best_model is None:
        best_model = KMeans(n_clusters=lower, random_state=RANDOM_STATE, n_init=10)
        best_model.fit(matrix)
    labels = best_model.labels_
    centroids = best_model.cluster_centers_

    themes: list[Theme] = []
    for cluster_index in sorted(set(labels)):
        member_ids = [
            item.id for item, label in zip(items, labels) if label == cluster_index
        ]
        theme_label, keywords = _label_for_cluster(vectorizer, centroids[cluster_index])
        themes.append(
            Theme(
                id=f"theme-{cluster_index}",
                label=theme_label,
                keywords=keywords,
                item_ids=member_ids,
            )
        )

    # Largest theme first — reading order should match "recurring problems" framing.
    themes.sort(key=lambda t: t.count, reverse=True)
    return themes
