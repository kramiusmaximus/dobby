from __future__ import annotations

from typing import Any

from dobby_app.obsidian_client import get_obsidian_client, obsidian_is_enabled


class WikiService:
    def require_enabled(self) -> None:
        if not obsidian_is_enabled():
            raise RuntimeError("Obsidian API is not configured, so DOBBY memory queries are unavailable.")

    def health(self) -> Any:
        self.require_enabled()
        return get_obsidian_client().health()

    def list(self, path: str | None = None) -> Any:
        self.require_enabled()
        return get_obsidian_client().list(path or "")

    def search_simple(self, query: str) -> Any:
        self.require_enabled()
        return get_obsidian_client().search_simple(query)

    def search_structured(self, jsonlogic: dict[str, Any]) -> Any:
        self.require_enabled()
        return get_obsidian_client().search_structured(jsonlogic)

    def read(self, path: str, target_type: str | None = None, target: str | None = None) -> str:
        self.require_enabled()
        return get_obsidian_client().read(path, target_type=target_type, target=target)

    def document_map(self, path: str) -> Any:
        self.require_enabled()
        return get_obsidian_client().document_map(path)

    def tags(self) -> Any:
        self.require_enabled()
        return get_obsidian_client().tags()

    def active_file_path(self) -> str:
        self.require_enabled()
        return get_obsidian_client().active_file_path()

    def open_file(self, path: str) -> Any:
        self.require_enabled()
        return get_obsidian_client().open_file(path)

    def write(self, path: str, content: str) -> str:
        self.require_enabled()
        return get_obsidian_client().write(path, content)

    def append(
        self,
        path: str,
        content: str,
        target_type: str | None = None,
        target: str | None = None,
    ) -> str:
        self.require_enabled()
        return get_obsidian_client().append(path, content, target_type=target_type, target=target)

    def patch(
        self,
        path: str,
        content: str,
        *,
        operation: str,
        target_type: str,
        target: str,
        content_type: str,
    ) -> str:
        self.require_enabled()
        return get_obsidian_client().patch(
            path,
            content,
            operation=operation,
            target_type=target_type,
            target=target,
            content_type=content_type,
        )

    def delete(self, path: str) -> str:
        self.require_enabled()
        return get_obsidian_client().delete(path)


wiki_service = WikiService()
