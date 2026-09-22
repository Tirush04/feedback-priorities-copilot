# Feedback-to-Priorities Copilot

A small tool for turning a batch of customer feedback into a prioritized,
evidence-backed decision brief — built from [this PRD](docs/PRD.md).

Upload a CSV of feedback → see it grouped into themes → inspect the exact
quotes behind each one → get three suggested product opportunities with
supporting and conflicting evidence → set priorities → export a Markdown
decision brief.

## Why this exists

Small-business founders and PMs collect customer feedback but struggle to
turn it into a decision. This is a weekly-batch workflow for one small team:
upload, review, prioritize, export — not a replacement for a full research
platform.

## The trust contract

Every quote shown anywhere in the app — in a theme, an opportunity, or the
exported brief — is copied **verbatim** from the uploaded CSV. Nothing is
summarized, paraphrased, or invented. That's enforced by design (see
[`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md)) and checked directly
in the test suite (`tests/test_opportunities.py`,
`tests/test_priorities_export.py`).

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/, upload a CSV with a `text` (or `comment` /
`feedback` / `body` / `message` / `review`) column, and go.

## Running the tests

```bash
pytest --cov=app --cov-report=term-missing
```

74 tests, 100% line coverage on `app/` as of this writing — unit tests for
each pipeline stage plus a full upload → rename → prioritize → export
integration test through the real HTTP layer, security-adjacent tests
(oversize upload, path-traversal filename, HTML/script content passed
through as inert data), and edge cases for the clustering/sentiment logic
(degenerate KMeans input, BOM-only files, non-UTF-8 input, etc).

## How it works

```
CSV upload
  → app/ingest.py        parse + validate rows
  → app/clustering.py    TF-IDF + KMeans → themes
  → app/opportunities.py rank themes, split evidence by sentiment
  → app/store.py         in-memory session (rename/priority mutate here)
  → app/export.py        render the decision brief
```

`app/main.py` is the FastAPI layer over that pipeline; `web/` is a
dependency-free vanilla-JS frontend served as static files.

**No LLM calls, no outbound network requests, no database.** See
[`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md) for why, and for the
MVP limitations that follow from it (in-memory sessions, no auth, 2 MB /
5000-row upload ceiling).

## Project layout

```
app/            core pipeline + FastAPI app
web/            static frontend (index.html, app.js, style.css)
tests/          pytest suite (unit + integration)
docs/           PRD, design decisions
```
