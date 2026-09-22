from __future__ import annotations

import pytest

from app.sentiment import classify, score


@pytest.mark.parametrize(
    "text",
    [
        "This is broken and terrible, I hate it.",
        "Shipping is always late and confusing.",
        "The app crashes constantly, such a frustrating bug.",
    ],
)
def test_negative_phrases(text):
    assert classify(text) == "negative"


@pytest.mark.parametrize(
    "text",
    [
        "I love this, it is great and easy to use.",
        "Amazing, smooth, and delightful experience.",
        "Works perfectly and the support team is helpful.",
    ],
)
def test_positive_phrases(text):
    assert classify(text) == "positive"


@pytest.mark.parametrize(
    "text",
    [
        "The invoice was sent on Tuesday.",
        "I contacted support about my account.",
        "",
        "   ",
    ],
)
def test_neutral_or_lexicon_free_text(text):
    assert classify(text) == "neutral"


def test_apostrophes_are_normalized():
    # "can't" should match the "cant" lexicon entry, not fail silently.
    assert classify("I can't get this to work, it's broken.") == "negative"


def test_mixed_but_net_negative():
    assert classify("It's fast but honestly pretty confusing and slow overall.") == "negative"


def test_exact_tie_is_neutral():
    assert classify("This is great but also terrible.") == "neutral"


def test_score_is_bounded():
    assert -1.0 <= score("terrible terrible terrible") <= 1.0
    assert -1.0 <= score("great great great") <= 1.0


def test_does_not_crash_on_punctuation_only():
    assert classify("!!! ??? ...") == "neutral"
