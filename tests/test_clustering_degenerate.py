from __future__ import annotations

import pytest

from app.clustering import cluster_feedback
from app.models import FeedbackItem


@pytest.mark.filterwarnings("ignore::sklearn.exceptions.ConvergenceWarning")
def test_identical_texts_do_not_crash_kmeans():
    """All-identical feedback gives KMeans nothing to separate on — every
    candidate k can legitimately collapse to fewer than 2 real clusters.
    This must fall back gracefully instead of raising.
    """
    items = [
        FeedbackItem(id=f"item-{i}", text="Shipping is slow.", source_row=i)
        for i in range(1, 9)
    ]
    themes = cluster_feedback(items)
    assert sum(t.count for t in themes) == len(items)
    assert all(theme.item_ids for theme in themes)
