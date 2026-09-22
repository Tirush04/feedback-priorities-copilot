from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import FeedbackItem, Theme
from app.store import store

# --- Ingest fixtures ---------------------------------------------------

VALID_ROWS = [
    "Shipping is always late and tracking never updates.",
    "The subscription pricing is way too expensive for what you get.",
    "The interface is confusing, I can never find the settings.",
]


def _csv_bytes(header: str, rows: list[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([header])
    for row in rows:
        writer.writerow([row])
    return buf.getvalue().encode("utf-8")


@pytest.fixture
def valid_csv_bytes() -> bytes:
    return _csv_bytes("comment", VALID_ROWS)


@pytest.fixture
def empty_csv_bytes() -> bytes:
    return b""


@pytest.fixture
def header_only_csv_bytes() -> bytes:
    return b"comment\n"


@pytest.fixture
def missing_text_column_csv_bytes() -> bytes:
    return _csv_bytes("customer_name", ["Alice", "Bob"])


# --- Clustering fixture: three well-separated topics --------------------

SHIPPING_ROWS = [
    "Shipping is always late and the delivery tracking never updates.",
    "My package arrived a week late, shipping needs to be faster.",
    "Delivery times are terrible, I waited two weeks for shipping.",
    "The shipping delay ruined my order, package came broken too.",
    "Shipping costs are fine but delivery is always delayed.",
]

PRICING_ROWS = [
    "The subscription pricing is way too expensive for what you get.",
    "Pricing changed without warning and now it feels overpriced.",
    "I cancelled because the monthly pricing is too expensive.",
    "Your pricing tiers are confusing and expensive compared to competitors.",
    "The price increase made the subscription too expensive to justify.",
]

UI_ROWS = [
    "The interface is confusing, I can never find the settings button.",
    "Navigation in the app is confusing and the buttons are tiny.",
    "The user interface feels cluttered and buttons are hard to find.",
    "I get lost in the confusing navigation menu every time.",
    "The dashboard interface is confusing, too many buttons everywhere.",
]


@pytest.fixture
def three_topic_rows() -> dict[str, list[str]]:
    return {"shipping": SHIPPING_ROWS, "pricing": PRICING_ROWS, "ui": UI_ROWS}


@pytest.fixture
def three_topic_csv_bytes(three_topic_rows) -> bytes:
    all_rows = (
        three_topic_rows["shipping"] + three_topic_rows["pricing"] + three_topic_rows["ui"]
    )
    return _csv_bytes("feedback", all_rows)


@pytest.fixture
def three_topic_items(three_topic_rows) -> list[FeedbackItem]:
    items = []
    row_number = 1
    for rows in three_topic_rows.values():
        for text in rows:
            items.append(FeedbackItem(id=f"item-{row_number}", text=text, source_row=row_number))
            row_number += 1
    return items


# --- Hand-built fixtures for opportunity/priority/export unit tests -----


@pytest.fixture
def opportunity_fixture():
    """Four themes with known sentiment mixes, bypassing real clustering
    entirely so opportunity ranking/evidence logic can be asserted exactly.
    """
    items = [
        FeedbackItem(id="a1", text="This is broken and terrible, hate the bugs.", source_row=1),
        FeedbackItem(id="a2", text="Awful, frustrating, and slow every single time.", source_row=2),
        FeedbackItem(id="a3", text="Painful and confusing, a real problem.", source_row=3),
        FeedbackItem(id="a4", text="Actually this part works great for me.", source_row=4),
        FeedbackItem(id="b1", text="Annoying and buggy, a clear problem.", source_row=5),
        FeedbackItem(id="b2", text="Slow and frustrating experience overall.", source_row=6),
        FeedbackItem(id="c1", text="A minor issue but mostly fine.", source_row=7),
        FeedbackItem(id="c2", text="Love this, it is great and easy.", source_row=8),
        FeedbackItem(id="c3", text="Amazing, smooth, and delightful to use.", source_row=9),
        FeedbackItem(id="d1", text="Perfect, excellent, and reliable every day.", source_row=10),
        FeedbackItem(id="d2", text="Great, awesome, and simple to use.", source_row=11),
    ]
    items_by_id = {item.id: item for item in items}
    themes = [
        Theme(id="theme-a", label="Theme A", keywords=["a"], item_ids=["a1", "a2", "a3", "a4"]),
        Theme(id="theme-b", label="Theme B", keywords=["b"], item_ids=["b1", "b2"]),
        Theme(id="theme-c", label="Theme C", keywords=["c"], item_ids=["c1", "c2", "c3"]),
        Theme(id="theme-d", label="Theme D", keywords=["d"], item_ids=["d1", "d2"]),
    ]
    return items_by_id, themes


# --- API client ----------------------------------------------------------


@pytest.fixture
def client():
    store.clear()
    with TestClient(app) as test_client:
        yield test_client
    store.clear()
