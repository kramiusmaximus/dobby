from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from dobby_app.config.settings import settings


class ObsidianError(RuntimeError):
    pass


class ObsidianHTTPError(ObsidianError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ObsidianConfig:
    api_url: str
    api_key: str
    verify_tls: bool


def obsidian_is_enabled() -> bool:
    return settings.effective_obsidian_enabled


def get_obsidian_client() -> "ObsidianClient":
    return ObsidianClient(
        ObsidianConfig(
            api_url=settings.obsidian_api_url.rstrip("/"),
            api_key=settings.obsidian_api_key,
            verify_tls=settings.obsidian_verify_tls,
        )
    )


class ObsidianClient:
    def __init__(self, config: ObsidianConfig) -> None:
        self.config = config

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/").json()

    def list(self, path: str = "") -> Any:
        return self._request("GET", f"/vault/{_quote_path(path)}").json()

    def read(self, path: str, *, target_type: str | None = None, target: str | None = None) -> str:
        headers = _target_headers(target_type, target)
        return self._request("GET", f"/vault/{_quote_path(path)}", headers=headers).text

    def write(self, path: str, content: str) -> str:
        return self._request(
            "PUT",
            f"/vault/{_quote_path(path)}",
            content=content,
            headers={"Content-Type": "text/plain"},
        ).text

    def append(
        self,
        path: str,
        content: str,
        *,
        target_type: str | None = None,
        target: str | None = None,
    ) -> str:
        headers = {"Content-Type": "text/plain"}
        headers.update(_target_headers(target_type, target))
        return self._request("POST", f"/vault/{_quote_path(path)}", content=content, headers=headers).text

    def patch(
        self,
        path: str,
        content: str,
        *,
        operation: str,
        target_type: str,
        target: str,
        content_type: str = "text/plain",
    ) -> str:
        headers = {
            "Content-Type": content_type,
            "Operation": operation,
            "Target-Type": target_type,
            "Target": target,
        }
        return self._request("PATCH", f"/vault/{_quote_path(path)}", content=content, headers=headers).text

    def delete(self, path: str) -> str:
        return self._request("DELETE", f"/vault/{_quote_path(path)}").text

    def search_simple(self, query: str) -> Any:
        return self._request("POST", "/search/simple/", params={"query": query}).json()

    def search_structured(self, jsonlogic: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/search/",
            json=jsonlogic,
            headers={"Content-Type": "application/vnd.olrapi.jsonlogic+json"},
        ).json()

    def tags(self) -> Any:
        return self._request("GET", "/tags/").json()

    def document_map(self, path: str) -> Any:
        return self._request(
            "GET",
            f"/vault/{_quote_path(path)}",
            headers={"Accept": "application/vnd.olrapi.document-map+json"},
        ).json()

    def active_file_path(self) -> str:
        return self._request("GET", "/active/").text

    def open_file(self, path: str) -> Any:
        response = self._request("POST", f"/open/{_quote_path(path)}")
        try:
            return response.json()
        except ValueError:
            return response.text

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if not self.config.api_key:
            raise ObsidianError("Obsidian API key is not configured.")

        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        headers.update(kwargs.pop("headers", {}) or {})
        try:
            response = httpx.request(
                method,
                f"{self.config.api_url}{path}",
                headers=headers,
                verify=self.config.verify_tls,
                timeout=10,
                **kwargs,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise ObsidianHTTPError(
                f"Obsidian API request failed with HTTP {status_code}: {exc.response.text}",
                status_code=status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise ObsidianError(f"Obsidian API request failed: {exc}") from exc
        return response


def _quote_path(path: str) -> str:
    cleaned = path.strip("/")
    return quote(cleaned, safe="/")


def _target_headers(target_type: str | None, target: str | None) -> dict[str, str]:
    if not target_type and not target:
        return {}
    if not target_type or not target:
        raise ObsidianError("Both target_type and target are required for targeted Obsidian requests.")
    return {"Target-Type": target_type, "Target": target}
