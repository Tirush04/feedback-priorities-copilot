from __future__ import annotations


def test_root_serves_the_frontend(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Feedback-to-Priorities Copilot" in resp.text


def test_root_404s_if_frontend_missing(client, monkeypatch, tmp_path):
    monkeypatch.setattr("app.main.WEB_DIR", tmp_path)
    resp = client.get("/")
    assert resp.status_code == 404


def test_static_assets_are_served(client):
    resp = client.get("/static/app.js")
    assert resp.status_code == 200
    resp = client.get("/static/style.css")
    assert resp.status_code == 200
