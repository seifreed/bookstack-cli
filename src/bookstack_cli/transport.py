from __future__ import annotations

import builtins
import http.client
import json
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPHandler, HTTPSHandler, Request, build_opener

from .config import BookStackConfig
from .errors import BookStackAPIError

Json = dict[str, Any] | builtins.list[Any] | str | int | float | bool | None
URL_OPENER = build_opener(HTTPHandler, HTTPSHandler)


@dataclass(frozen=True)
class RawResponse:
    body: bytes
    content_type: str


class BookStackTransport:
    def __init__(self, config: BookStackConfig, timeout: float = 30.0) -> None:
        self.config = config
        self.timeout = timeout

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
        body, content_type = _encode_body(json, fields, files)
        request = Request(
            self._url(path, params),
            data=body,
            method=method.upper(),
            headers=self._headers(content_type),
        )
        try:
            with URL_OPENER.open(request, timeout=self.timeout) as response:
                return RawResponse(response.read(), response.headers.get_content_type())
        except HTTPError as error:
            raise _api_error(error) from error
        except URLError as error:
            raise BookStackAPIError(0, str(error.reason)) from error
        except http.client.HTTPException as error:
            raise BookStackAPIError(0, str(error)) from error

    def _url(self, path: str, params: dict[str, str | int] | None) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        separator = "&" if "?" in clean_path else "?"
        query = f"{separator}{urlencode(params)}" if params else ""
        return f"{self.config.url}{clean_path}{query}"

    def _headers(self, content_type: str | None) -> dict[str, str]:
        headers = {
            "Accept": "*/*",
            "Authorization": self.config.authorization,
            "User-Agent": "bookstack-cli/0.1.0",
        }
        if content_type is not None:
            headers["Content-Type"] = content_type
        return headers


def _encode_body(
    data: dict[str, Any] | None,
    fields: dict[str, str] | None,
    files: dict[str, Path] | None,
) -> tuple[bytes | None, str | None]:
    if fields or files:
        if data is not None:
            raise ValueError("json cannot be combined with fields or files")
        return _encode_multipart(fields or {}, files or {})
    return _encode_json(data), "application/json" if data is not None else None


def _encode_json(data: dict[str, Any] | None) -> bytes | None:
    if data is None:
        return None
    return json.dumps(data).encode("utf-8")


def _encode_multipart(fields: dict[str, str], files: dict[str, Path]) -> tuple[bytes, str]:
    boundary = f"bookstack-cli-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        disposition = f'Content-Disposition: form-data; name="{_quote_multipart_param(name)}"'
        chunks.append(_multipart_part(boundary, [disposition], value.encode()))
    for name, path in files.items():
        disposition = (
            f'Content-Disposition: form-data; name="{_quote_multipart_param(name)}"; '
            f'filename="{_quote_multipart_param(path.name)}"'
        )
        content_type = f"Content-Type: {mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}"
        chunks.append(_multipart_part(boundary, [disposition, content_type], path.read_bytes()))
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _multipart_part(boundary: str, header_lines: list[str], body: bytes) -> bytes:
    headers = "".join(f"{line}\r\n" for line in header_lines)
    return f"--{boundary}\r\n".encode() + headers.encode() + b"\r\n" + body + b"\r\n"


def _quote_multipart_param(value: str) -> str:
    if "\r" in value or "\n" in value:
        raise ValueError(f"multipart field/file name cannot contain a newline: {value!r}")
    return value.replace("\\", "\\\\").replace('"', '\\"')


def decode_response(body: bytes) -> Json:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    try:
        return cast(Json, json.loads(text))
    except json.JSONDecodeError:
        return text


def _api_error(error: HTTPError) -> BookStackAPIError:
    payload = decode_response(error.read())
    error.close()
    if isinstance(payload, dict):
        api_error = payload.get("error")
        if isinstance(api_error, dict) and isinstance(api_error.get("message"), str):
            return BookStackAPIError(error.code, api_error["message"], payload)
    return BookStackAPIError(error.code, error.reason, payload)
