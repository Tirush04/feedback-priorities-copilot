# Design decisions and MVP trade-offs

## No LLM in the pipeline

Theme grouping is TF-IDF + KMeans (`app/clustering.py`); "supporting vs.
conflicting evidence" is a small lexicon-based sentiment scorer
(`app/sentiment.py`), not a model call.

This was a deliberate choice, not a shortcut taken for lack of time:

- **Testable.** The whole pipeline is deterministic, so `tests/` can assert
  exact behavior instead of fuzzy "looks reasonable" checks.
- **No API key, no cost, no network dependency.** The app runs fully offline.
- **Traceability by construction.** Every quote is a direct copy of a CSV
  cell — see `app/opportunities.py` — which is how the PRD's "≥95% of
  factual claims backed by evidence" target is met at 100%, not just aimed
  for. An LLM-generated summary can't give you that guarantee for free.

The real trade-off: theme labels are keyword phrases ("Shipping / Delivery /
Late"), not fluent prose, and grouping quality depends on vocabulary overlap
rather than semantic understanding. If this became a real product, the
natural next step is an LLM pass *on top of* the existing themes — to
generate a nicer label and a one-line synthesis — while keeping every quote
sourced exactly as it is now. The clustering/sentiment modules are already
isolated behind plain functions so that swap wouldn't touch the API or
frontend.

## No database, in-memory sessions

State lives in a process-wide dict (`app/store.py`), keyed by a `uuid4`
session id. Restarting the server loses every session. That's a fine
trade-off for "one weekly batch, one small team, running locally" — the
PRD's actual scope — but it's the first thing to change before this is a
shared, multi-user tool.

## No auth

There's no login. Session ids are unguessable UUIDs, which is the right
amount of protection for a local single-user tool with no persistent data,
and the wrong amount for anything deployed multi-tenant. Don't deploy this
publicly without adding auth first.

## Stdlib `csv`, not pandas

One text column, from untrusted input. `csv.DictReader` is enough, keeps
the dependency list small, and avoids pandas's more permissive type
inference on CSV content that was never meant to be trusted.

## Upload limits

2 MB per file, 5000 rows, 2000 characters per feedback item
(`app/ingest.py`, `app/main.py`). The whole file is read into memory before
the size check runs — fine at these limits, would need to become a
streaming check before raising them.
