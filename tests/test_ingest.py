from __future__ import annotations

import pytest

from app.ingest import MAX_ITEM_LENGTH, MAX_ROWS, IngestError, parse_feedback_csv
from tests.conftest import VALID_ROWS, _csv_bytes


def test_parses_valid_csv(valid_csv_bytes):
    items = parse_feedback_csv(valid_csv_bytes)
    assert len(items) == len(VALID_ROWS)
    assert [item.text for item in items] == VALID_ROWS
    # source_row is 1-based and excludes the header
    assert [item.source_row for item in items] == [1, 2, 3]
    # ids are unique and stable
    assert len({item.id for item in items}) == len(items)


@pytest.mark.parametrize("header", ["text", "Comment", "FEEDBACK", "Body", "Message", "review"])
def test_recognizes_text_column_variants(header):
    items = parse_feedback_csv(_csv_bytes(header, ["Some feedback here."]))
    assert len(items) == 1
    assert items[0].text == "Some feedback here."


def test_missing_text_column_raises(missing_text_column_csv_bytes):
    with pytest.raises(IngestError, match="No feedback-text column"):
        parse_feedback_csv(missing_text_column_csv_bytes)


def test_empty_file_raises(empty_csv_bytes):
    with pytest.raises(IngestError, match="empty"):
        parse_feedback_csv(empty_csv_bytes)


def test_header_only_file_raises(header_only_csv_bytes):
    with pytest.raises(IngestError, match="No usable feedback rows"):
        parse_feedback_csv(header_only_csv_bytes)


def test_blank_rows_are_skipped_but_row_numbers_track_original_position():
    raw = _csv_bytes("comment", ["First comment.", "", "  ", "Second comment."])
    items = parse_feedback_csv(raw)
    assert [item.text for item in items] == ["First comment.", "Second comment."]
    # Row 2 and 3 were blank; "Second comment." is really row 4 in the file.
    assert [item.source_row for item in items] == [1, 4]


def test_whitespace_is_stripped():
    raw = _csv_bytes("comment", ["   padded text.   "])
    items = parse_feedback_csv(raw)
    assert items[0].text == "padded text."


def test_utf8_bom_is_handled():
    raw = b"\xef\xbb\xbfcomment\nHello with a BOM.\n"
    items = parse_feedback_csv(raw)
    assert items[0].text == "Hello with a BOM."


def test_bom_only_file_has_no_header_row():
    # A BOM with nothing after it decodes to "", which is non-empty at the
    # byte level (so it passes the empty-file check) but has no CSV header.
    with pytest.raises(IngestError, match="no header row"):
        parse_feedback_csv(b"\xef\xbb\xbf")


def test_non_utf8_bytes_raise_clear_error():
    raw = "comment\nBonjour à tous\n".encode("latin-1")
    with pytest.raises(IngestError, match="UTF-8"):
        parse_feedback_csv(raw)


def test_row_limit_is_enforced(monkeypatch):
    monkeypatch.setattr("app.ingest.MAX_ROWS", 3)
    raw = _csv_bytes("comment", [f"Comment number {i}." for i in range(5)])
    with pytest.raises(IngestError, match="more than 3 rows"):
        parse_feedback_csv(raw)


def test_overlong_item_is_truncated_not_dropped(monkeypatch):
    monkeypatch.setattr("app.ingest.MAX_ITEM_LENGTH", 20)
    raw = _csv_bytes("comment", ["x" * 50])
    items = parse_feedback_csv(raw)
    assert len(items) == 1
    assert items[0].text.endswith("…")
    assert len(items[0].text) <= 21  # 20 chars + ellipsis
    # The kept prefix must still be a real prefix of the original text —
    # truncation never fabricates content, it only cuts it short.
    assert ("x" * 50).startswith(items[0].text.rstrip("…"))
