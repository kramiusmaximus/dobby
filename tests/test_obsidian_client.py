from __future__ import annotations

import httpx

from dobby_app.obsidian_client import ObsidianClient, ObsidianConfig


def _response(status_code, **kwargs):
    return httpx.Response(status_code, request=httpx.Request("GET", "https://127.0.0.1"), **kwargs)


def test_obsidian_client_read_sends_auth_and_tls(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return _response(200, text="# Note")

    monkeypatch.setattr("dobby_app.obsidian_client.httpx.request", fake_request)
    client = ObsidianClient(
        ObsidianConfig(api_url="https://127.0.0.1:27124", api_key="secret", verify_tls=False)
    )

    assert client.read("pages/projects/studio.md") == "# Note"
    assert captured["method"] == "GET"
    assert captured["url"] == "https://127.0.0.1:27124/vault/pages/projects/studio.md"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["verify"] is False


def test_obsidian_client_patch_uses_target_headers(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return _response(200, text="")

    monkeypatch.setattr("dobby_app.obsidian_client.httpx.request", fake_request)
    client = ObsidianClient(
        ObsidianConfig(api_url="https://127.0.0.1:27124", api_key="secret", verify_tls=False)
    )

    client.patch(
        "pages/projects/studio.md",
        '"active"',
        operation="replace",
        target_type="frontmatter",
        target="status",
        content_type="application/json",
    )

    assert captured["method"] == "PATCH"
    assert captured["headers"]["Operation"] == "replace"
    assert captured["headers"]["Target-Type"] == "frontmatter"
    assert captured["headers"]["Target"] == "status"
    assert captured["headers"]["Content-Type"] == "application/json"


def test_obsidian_client_document_map_uses_accept_header(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return _response(200, json={"headings": []})

    monkeypatch.setattr("dobby_app.obsidian_client.httpx.request", fake_request)
    client = ObsidianClient(
        ObsidianConfig(api_url="https://127.0.0.1:27124", api_key="secret", verify_tls=False)
    )

    assert client.document_map("index.md") == {"headings": []}
    assert captured["headers"]["Accept"] == "application/vnd.olrapi.document-map+json"
