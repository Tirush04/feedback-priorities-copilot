"""CSV ingestion.

Deliberately uses the stdlib `csv` module rather than pandas: it is enough
for one text column, keeps the dependency footprint small, and sidesteps
pandas's more permissive type-sniffing on untrusted input.
"""

from __future__ import annotations

import csv
import io

MAX_ROWS = 5000
MAX_ITEM_LENGTH = 2000

# Header names we recognize as "the feedback text", checked case-insensitively.
TEXT_COLUMN_CANDIDATES = ("text", "comment", "feedback", "body", "message", "review")


class IngestError(ValueError):
    """Raised when a CSV can't be turned into feedback items."""


def _find_text_column(fieldnames: list[str]) -> str:
    lowered = {name.strip().lower(): name for name in fieldnames if name}
    for candidate in TEXT_COLUMN_CANDIDATES:
        if candidate in lowered:
            return lowered[candidate]
    raise IngestError(
        "No feedback-text column found. Expected one of: "
        + ", ".join(TEXT_COLUMN_CANDIDATES)
    )


def parse_feedback_csv(raw: bytes) -> list["FeedbackItem"]:
    """Parse raw CSV bytes into a list of FeedbackItem.

    Raises IngestError for anything that would make downstream analysis
    meaningless or unsafe: no text column, no usable rows, or a file too
    large to process synchronously.
    """
    from app.models import FeedbackItem  # local import avoids a cycle at module load

    if not raw or not raw.strip():
        raise IngestError("The file is empty.")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestError("The file is not valid UTF-8 text.") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise IngestError("The file has no header row.")

    text_column = _find_text_column(list(reader.fieldnames))

    items: list[FeedbackItem] = []
    for source_row, row in enumerate(reader, start=1):
        if source_row > MAX_ROWS:
            raise IngestError(
                f"This file has more than {MAX_ROWS} rows. Split it into smaller "
                "batches and upload separately."
            )
        raw_value = (row.get(text_column) or "").strip()
        if not raw_value:
            continue
        if len(raw_value) > MAX_ITEM_LENGTH:
            raw_value = raw_value[:MAX_ITEM_LENGTH].rstrip() + "…"
        items.append(
            FeedbackItem(id=f"item-{source_row}", text=raw_value, source_row=source_row)
        )

    if not items:
        raise IngestError("No usable feedback rows were found in the file.")

    return items
