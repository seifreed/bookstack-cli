from __future__ import annotations

import builtins
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .config import BookStackConfig
from .transport import BookStackTransport, Json, RawResponse, decode_response


class BookStackClient:
    def __init__(self, config: BookStackConfig, timeout: float = 30.0) -> None:
        self.transport = BookStackTransport(config, timeout=timeout)

    @classmethod
    def from_env(cls, env_file: str = ".env", timeout: float = 30.0) -> BookStackClient:
        return cls(BookStackConfig.from_env(env_file), timeout=timeout)

    def list(
        self,
        resource: str,
        *,
        count: int | None = None,
        offset: int | None = None,
        sort: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> Json:
        params: dict[str, str | int] = {}
        if count is not None:
            params["count"] = count
        if offset is not None:
            params["offset"] = offset
        if sort:
            params["sort"] = sort
        for key, value in (filters or {}).items():
            params[f"filter[{key}]"] = value
        return self.request("GET", _resource_path(resource), params=params)

    def get(self, resource: str, item_id: int | str) -> Json:
        return self.request("GET", _resource_path(resource, item_id))

    def create(self, resource: str, data: dict[str, Any]) -> Json:
        return self.request("POST", _resource_path(resource), json=data)

    def update(self, resource: str, item_id: int | str, data: dict[str, Any]) -> Json:
        return self.request("PUT", _resource_path(resource, item_id), json=data)

    def delete(self, resource: str, item_id: int | str) -> Json:
        return self.request("DELETE", _resource_path(resource, item_id))

    def get_many(self, resource: str, ids: builtins.list[int | str], workers: int = 4) -> builtins.list[Json]:
        if workers < 1:
            raise ValueError("workers must be at least 1")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return builtins.list(pool.map(lambda item_id: self.get(resource, item_id), ids))

    def list_all(
        self,
        resource: str,
        *,
        count: int | None = None,
        sort: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> builtins.list[Json]:
        items: builtins.list[Json] = []
        offset = 0
        while True:
            page = self.list(resource, count=count, offset=offset, sort=sort, filters=filters)
            data, total = _paginated_page(page)
            items.extend(data)
            offset += len(data)
            if not data or offset >= total:
                return items

    def search(self, query: str, *, page: int | None = None, count: int | None = None) -> Json:
        params: dict[str, str | int] = {"query": query}
        if page is not None:
            params["page"] = page
        if count is not None:
            params["count"] = count
        return self.request("GET", "/api/search", params=params)

    def tags(self, *, name: str | None = None, count: int | None = None) -> Json:
        params: dict[str, str | int] = {}
        if count is not None:
            params["count"] = count
        if name is None:
            return self.request("GET", "/api/tags/names", params=params)
        params["name"] = name
        return self.request("GET", "/api/tags/values-for-name", params=params)

    def recycle_bin_list(self, *, count: int | None = None, offset: int | None = None) -> Json:
        params: dict[str, str | int] = {}
        if count is not None:
            params["count"] = count
        if offset is not None:
            params["offset"] = offset
        return self.request("GET", _resource_path("recycle-bin"), params=params)

    def recycle_bin_restore(self, deletion_id: int | str) -> Json:
        return self.request("PUT", _resource_path("recycle-bin", deletion_id))

    def recycle_bin_destroy(self, deletion_id: int | str) -> Json:
        return self.request("DELETE", _resource_path("recycle-bin", deletion_id))

    def get_content_permissions(self, content_type: str, content_id: int | str) -> Json:
        return self.request("GET", _content_permissions_path(content_type, content_id))

    def set_content_permissions(self, content_type: str, content_id: int | str, data: dict[str, Any]) -> Json:
        return self.request("PUT", _content_permissions_path(content_type, content_id), json=data)

    def export(self, resource: str, item_id: int | str, export_format: str) -> RawResponse:
        path = f"{_resource_path(resource, item_id)}/export/{quote(export_format, safe='')}"
        return self.request_raw("GET", path)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        json: dict[str, Any] | None = None,
        fields: dict[str, str] | None = None,
        files: dict[str, Path] | None = None,
    ) -> Json:
        response = self.request_raw(method, path, params=params, json=json, fields=fields, files=files)
        return decode_response(response.body)

    def request_raw(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        json: dict[str, Any] | None = None,
        fields: dict[str, str] | None = None,
        files: dict[str, Path] | None = None,
    ) -> RawResponse:
        return self.transport.request_raw(method, path, params=params, json=json, fields=fields, files=files)


def _resource_path(resource: str, item_id: int | str | None = None) -> str:
    path = f"/api/{quote(resource, safe='')}"
    return path if item_id is None else f"{path}/{quote(str(item_id), safe='')}"


def _content_permissions_path(content_type: str, content_id: int | str) -> str:
    return f"/api/content-permissions/{quote(content_type, safe='')}/{quote(str(content_id), safe='')}"


def _paginated_page(page: Json) -> tuple[builtins.list[Any], int]:
    if not isinstance(page, dict):
        raise ValueError("list --all requires an endpoint that returns a JSON object")
    data, total = page.get("data"), page.get("total")
    if not isinstance(data, list) or not isinstance(total, int):
        raise ValueError("list --all requires an endpoint that returns {data: [...], total: N}")
    return data, total
