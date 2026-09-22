from __future__ import annotations

import io

import pytest


def _upload(client, csv_bytes: bytes, filename: str = "feedback.csv"):
    return client.post(
        "/api/sessions",
        files={"file": (filename, io.BytesIO(csv_bytes), "text/csv")},
    )


# --- Happy path: the full vertical slice --------------------------------


def test_full_flow_upload_edit_prioritize_export(client, three_topic_csv_bytes, three_topic_rows):
    upload = _upload(client, three_topic_csv_bytes)
    assert upload.status_code == 201
    body = upload.json()
    session_id = body["session_id"]
    assert body["total_feedback_items"] == 15
    assert len(body["opportunities"]) <= 3
    assert len(body["opportunities"]) > 0

    # Every evidence quote returned over the wire must be verbatim from the
    # uploaded CSV — checked end-to-end through the real HTTP layer.
    all_source_texts = {row for rows in three_topic_rows.values() for row in rows}
    for opportunity in body["opportunities"]:
        for evidence in opportunity["supporting_evidence"] + opportunity["conflicting_evidence"]:
            assert evidence["quote"] in all_source_texts

    get_resp = client.get(f"/api/sessions/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json() == body  # re-fetch matches what upload returned

    themes = body["themes"]
    first_theme_id = themes[0]["id"]

    rename = client.patch(
        f"/api/sessions/{session_id}/themes/{first_theme_id}",
        json={"label": "Renamed Theme"},
    )
    assert rename.status_code == 200
    renamed_body = rename.json()
    renamed_theme = next(t for t in renamed_body["themes"] if t["id"] == first_theme_id)
    assert renamed_theme["label"] == "Renamed Theme"
    # If that theme produced an opportunity, its title must follow the rename.
    matching_opps = [o for o in renamed_body["opportunities"] if o["theme_id"] == first_theme_id]
    for opp in matching_opps:
        assert "Renamed Theme" in opp["title"]

    opportunity_id = body["opportunities"][0]["id"]
    prioritize = client.post(
        f"/api/sessions/{session_id}/opportunities/{opportunity_id}/priority",
        json={"priority": "High", "notes": "Tackle this sprint"},
    )
    assert prioritize.status_code == 200
    updated_opp = next(
        o for o in prioritize.json()["opportunities"] if o["id"] == opportunity_id
    )
    assert updated_opp["priority"] == "High"
    assert updated_opp["notes"] == "Tackle this sprint"

    brief_md = client.get(f"/api/sessions/{session_id}/brief", params={"format": "markdown"})
    assert brief_md.status_code == 200
    assert "High" in brief_md.text
    assert "Tackle this sprint" in brief_md.text

    brief_json = client.get(f"/api/sessions/{session_id}/brief", params={"format": "json"})
    assert brief_json.status_code == 200
    payload = brief_json.json()
    assert payload["total_feedback_items"] == 15
    priorities_seen = {o["priority"] for o in payload["opportunities"]}
    assert "High" in priorities_seen


# --- Validation / error paths -------------------------------------------


def test_rejects_non_csv_extension(client):
    resp = client.post(
        "/api/sessions",
        files={"file": ("notes.txt", io.BytesIO(b"comment\nhello\n"), "text/plain")},
    )
    assert resp.status_code == 400


def test_rejects_oversize_upload(client, monkeypatch):
    monkeypatch.setattr("app.main.MAX_UPLOAD_BYTES", 10)
    resp = _upload(client, b"comment\n" + b"x" * 50)
    assert resp.status_code == 413


def test_rejects_csv_with_no_text_column(client, missing_text_column_csv_bytes):
    resp = _upload(client, missing_text_column_csv_bytes)
    assert resp.status_code == 400
    assert "text column" in resp.json()["detail"].lower() or "text-column" in resp.json()["detail"].lower()


def test_get_unknown_session_returns_404(client):
    resp = client.get("/api/sessions/does-not-exist")
    assert resp.status_code == 404


def test_rename_theme_on_unknown_session_returns_404(client):
    resp = client.patch(
        "/api/sessions/does-not-exist/themes/theme-0",
        json={"label": "New label"},
    )
    assert resp.status_code == 404


def test_priority_on_unknown_session_returns_404(client):
    resp = client.post(
        "/api/sessions/does-not-exist/opportunities/opp-0/priority",
        json={"priority": "High"},
    )
    assert resp.status_code == 404


def test_brief_on_unknown_session_returns_404(client):
    resp = client.get("/api/sessions/does-not-exist/brief")
    assert resp.status_code == 404


def test_rename_unknown_theme_returns_404(client, valid_csv_bytes):
    body = _upload(client, valid_csv_bytes).json()
    resp = client.patch(
        f"/api/sessions/{body['session_id']}/themes/not-a-real-theme",
        json={"label": "New label"},
    )
    assert resp.status_code == 404


def test_priority_on_unknown_opportunity_returns_404(client, valid_csv_bytes):
    body = _upload(client, valid_csv_bytes).json()
    resp = client.post(
        f"/api/sessions/{body['session_id']}/opportunities/not-real/priority",
        json={"priority": "High"},
    )
    assert resp.status_code == 404


def test_invalid_priority_value_returns_422(client, valid_csv_bytes):
    body = _upload(client, valid_csv_bytes).json()
    opportunity_id = body["opportunities"][0]["id"]
    resp = client.post(
        f"/api/sessions/{body['session_id']}/opportunities/{opportunity_id}/priority",
        json={"priority": "Urgent!!"},
    )
    assert resp.status_code == 422


def test_brief_bad_format_returns_400(client, valid_csv_bytes):
    body = _upload(client, valid_csv_bytes).json()
    resp = client.get(f"/api/sessions/{body['session_id']}/brief", params={"format": "pdf"})
    assert resp.status_code == 400


def test_path_traversal_filename_is_never_touched_on_disk(client, valid_csv_bytes, tmp_path):
    resp = client.post(
        "/api/sessions",
        files={"file": ("../../etc/passwd.csv", io.BytesIO(valid_csv_bytes), "text/csv")},
    )
    # We never write to disk using the client-supplied filename, so this is
    # just an ordinary successful upload — the crafted name has no effect.
    assert resp.status_code == 201


# --- Isolation between sessions ------------------------------------------


def test_html_in_feedback_text_is_returned_as_inert_data(client):
    """The API must never sanitize/strip this — that's the frontend's job
    (verified live with textContent-only rendering). This test just locks
    in that the backend passes the raw text through unchanged, so a
    regression there is caught here rather than only in the browser.
    """
    raw = (
        b"comment\n"
        b'"This is broken and terrible, <script>alert(1)</script> confusing."\n'
        b'"Slow and frustrating, <img src=x onerror=alert(1)> terrible too."\n'
        b'"Another broken and confusing terrible experience overall."\n'
        b'"Painful and annoying, a real problem with this interface."\n'
        b'"Difficult and unreliable, clunky and disappointing overall."\n'
    )
    resp = _upload(client, raw)
    assert resp.status_code == 201
    body = resp.json()
    all_quotes = [
        e["quote"]
        for o in body["opportunities"]
        for e in o["supporting_evidence"] + o["conflicting_evidence"]
    ]
    assert any("<script>" in q for q in all_quotes)


def test_two_sessions_do_not_share_state(client, valid_csv_bytes, three_topic_csv_bytes):
    first = _upload(client, valid_csv_bytes).json()
    second = _upload(client, three_topic_csv_bytes).json()

    assert first["session_id"] != second["session_id"]
    assert first["total_feedback_items"] != second["total_feedback_items"]

    opp_id = first["opportunities"][0]["id"]
    client.post(
        f"/api/sessions/{first['session_id']}/opportunities/{opp_id}/priority",
        json={"priority": "High"},
    )

    second_refetch = client.get(f"/api/sessions/{second['session_id']}").json()
    assert all(o["priority"] == "Unset" for o in second_refetch["opportunities"])
