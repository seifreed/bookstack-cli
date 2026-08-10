import http.client
from urllib.error import HTTPError, URLError

import pytest

from bookstack_cli import BookStackAPIError, BookStackClient, BookStackConfig


@pytest.fixture
def client():
    return BookStackClient(BookStackConfig("https://bookstack.test", "id", "secret"))


def test_list_builds_bookstack_query(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.headers["Authorization"]
        return Response(b'{"data":[],"total":0}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    result = client.list("books", count=10, offset=20, sort="+name", filters={"name:like": "%api%"})

    assert result == {"data": [], "total": 0}
    assert seen["auth"] == "Token id:secret"
    assert (
        seen["url"]
        == "https://bookstack.test/api/books?count=10&offset=20&sort=%2Bname&filter%5Bname%3Alike%5D=%25api%25"
    )


def test_create_sends_json(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["data"] = request.data
        seen["content_type"] = request.headers["Content-type"]
        return Response(b'{"id":1}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    assert client.create("books", {"name": "Docs"}) == {"id": 1}
    assert seen["data"] == b'{"name": "Docs"}'
    assert seen["content_type"] == "application/json"


def test_request_raw_returns_non_json(monkeypatch, client):
    def fake_urlopen(request, timeout):
        return Response(b"plain text", content_type="text/plain")

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    response = client.request_raw("GET", "/api/pages/1/export/plaintext")

    assert response.body == b"plain text"
    assert response.content_type == "text/plain"


def test_multipart_sends_file(monkeypatch, tmp_path, client):
    seen = {}
    upload = tmp_path / "test.txt"
    upload.write_text("hello", encoding="utf-8")

    def fake_urlopen(request, timeout):
        seen["data"] = request.data
        seen["content_type"] = request.headers["Content-type"]
        return Response(b'{"id":1}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    assert client.request("POST", "/api/imports", fields={"name": "x"}, files={"file": upload}) == {"id": 1}
    assert seen["content_type"].startswith("multipart/form-data; boundary=")
    assert b'name="name"' in seen["data"]
    assert b'name="file"; filename="test.txt"' in seen["data"]
    assert b"hello" in seen["data"]


def test_multipart_escapes_quotes_in_field_name(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["data"] = request.data
        return Response(b'{"id":1}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    client.request("POST", "/api/imports", fields={'weird"name': "value"})

    assert b'name="weird\\"name"' in seen["data"]


def test_multipart_escapes_quotes_in_filename(monkeypatch, tmp_path, client):
    seen = {}
    upload = tmp_path / 'evil".png'
    upload.write_bytes(b"data")

    def fake_urlopen(request, timeout):
        seen["data"] = request.data
        return Response(b'{"id":1}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    client.request("POST", "/api/image-gallery", files={"image": upload})

    assert b'filename="evil\\".png"' in seen["data"]


def test_multipart_rejects_newline_in_field_name(client):
    with pytest.raises(ValueError, match="newline"):
        client.request("POST", "/api/imports", fields={"evil\r\nX-Injected: true": "value"})


def test_multipart_uses_fresh_boundary(monkeypatch, tmp_path, client):
    content_types = []
    upload = tmp_path / "test.txt"
    upload.write_text("hello", encoding="utf-8")

    def fake_urlopen(request, timeout):
        content_types.append(request.headers["Content-type"])
        return Response(b'{"id":1}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    client.request("POST", "/api/imports", files={"file": upload})
    client.request("POST", "/api/imports", files={"file": upload})

    assert len(set(content_types)) == 2


def test_resource_and_id_are_percent_encoded_in_the_path(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return Response(b'{"ok":true}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    client.get("books?count=999999", "1&admin=true")

    assert seen["url"] == "https://bookstack.test/api/books%3Fcount%3D999999/1%26admin%3Dtrue"


def test_shortcut_methods_and_relative_paths(monkeypatch, client):
    calls = []

    def fake_request(method, path, *, params=None, json=None, fields=None, files=None):
        calls.append((method, path, json))
        return {"ok": True}

    client.request = fake_request

    assert client.get("books", 1) == {"ok": True}
    assert client.update("books", 1, {"name": "Docs"}) == {"ok": True}
    assert client.delete("books", 1) == {"ok": True}
    assert client.transport._url("api/system", None) == "https://bookstack.test/api/system"
    assert calls == [
        ("GET", "/api/books/1", None),
        ("PUT", "/api/books/1", {"name": "Docs"}),
        ("DELETE", "/api/books/1", None),
    ]


def test_url_appends_params_to_existing_query(client):
    assert (
        client.transport._url("/api/search?query=docs", {"page": 2})
        == "https://bookstack.test/api/search?query=docs&page=2"
    )


def test_list_omits_empty_optional_params(monkeypatch, client):
    seen = {}

    def fake_request(method, path, *, params=None, json=None, fields=None, files=None):
        seen["params"] = params
        return {}

    client.request = fake_request

    client.list("books")

    assert seen["params"] == {}


def test_get_many_uses_workers(monkeypatch, client):
    monkeypatch.setattr(client, "get", lambda resource, item_id: {"resource": resource, "id": item_id})

    assert client.get_many("pages", ["1", "2"], workers=2) == [
        {"resource": "pages", "id": "1"},
        {"resource": "pages", "id": "2"},
    ]


def test_get_many_rejects_invalid_worker_count(client):
    with pytest.raises(ValueError, match="workers must be at least 1"):
        client.get_many("pages", ["1"], workers=0)


def test_list_all_accumulates_every_page(client):
    pages = [
        {"data": [{"id": 1}, {"id": 2}], "total": 3},
        {"data": [{"id": 3}], "total": 3},
    ]
    client.request = lambda method, path, **kwargs: pages.pop(0)

    assert client.list_all("books", count=2) == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_list_all_stops_on_empty_page_even_if_total_not_reached(client):
    client.request = lambda method, path, **kwargs: {"data": [], "total": 5}

    assert client.list_all("books") == []


def test_list_all_rejects_non_dict_response(client):
    client.request = lambda method, path, **kwargs: ["not", "a", "dict"]

    with pytest.raises(ValueError, match="requires an endpoint"):
        client.list_all("books")


def test_list_all_rejects_malformed_page_shape(client):
    client.request = lambda method, path, **kwargs: {"data": "not-a-list", "total": 0}

    with pytest.raises(ValueError, match="requires an endpoint"):
        client.list_all("books")


def test_search_sends_query_page_and_count(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return Response(b'{"data":[],"total":0}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    client.search("docs", page=2, count=5)

    assert seen["url"] == "https://bookstack.test/api/search?query=docs&page=2&count=5"


def test_search_omits_optional_params(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return Response(b'{"data":[],"total":0}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    client.search("docs")

    assert seen["url"] == "https://bookstack.test/api/search?query=docs"


def test_tags_lists_names_by_default(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return Response(b'["status", "priority"]')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    assert client.tags(count=10) == ["status", "priority"]
    assert seen["url"] == "https://bookstack.test/api/tags/names?count=10"


def test_tags_lists_values_for_name(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return Response(b'["draft", "final"]')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    client.tags(name="status")

    assert seen["url"] == "https://bookstack.test/api/tags/values-for-name?name=status"


def test_recycle_bin_list_builds_params(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return Response(b'{"data":[],"total":0}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    client.recycle_bin_list(count=5, offset=10)

    assert seen["url"] == "https://bookstack.test/api/recycle-bin?count=5&offset=10"


def test_recycle_bin_restore_and_destroy(monkeypatch, client):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.get_method(), request.full_url))
        return Response(b'{"restore_count":1}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    client.recycle_bin_restore(4)
    client.recycle_bin_destroy(4)

    assert calls == [
        ("PUT", "https://bookstack.test/api/recycle-bin/4"),
        ("DELETE", "https://bookstack.test/api/recycle-bin/4"),
    ]


def test_content_permissions_get_and_set(monkeypatch, client):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.get_method(), request.full_url, request.data))
        return Response(b'{"fallback_permissions":{}}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    client.get_content_permissions("book", 1)
    client.set_content_permissions("book", 1, {"fallback_permissions": {"inheriting": True}})

    assert calls[0] == ("GET", "https://bookstack.test/api/content-permissions/book/1", None)
    assert calls[1][0] == "PUT"
    assert calls[1][1] == "https://bookstack.test/api/content-permissions/book/1"
    assert calls[1][2] == b'{"fallback_permissions": {"inheriting": true}}'


def test_content_permissions_percent_encodes_type_and_id(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return Response(b"{}")

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    client.get_content_permissions("book?x=1", "1&y=2")

    assert seen["url"] == "https://bookstack.test/api/content-permissions/book%3Fx%3D1/1%26y%3D2"


def test_export_builds_path_and_returns_raw_response(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return Response(b"%PDF-1.4 fake", content_type="application/pdf")

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    response = client.export("pages", 1, "pdf")

    assert seen["url"] == "https://bookstack.test/api/pages/1/export/pdf"
    assert response.body == b"%PDF-1.4 fake"
    assert response.content_type == "application/pdf"


def test_request_without_body_has_no_content_type(monkeypatch, client):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["headers"] = request.headers
        return Response(b"")

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    assert client.request("GET", "/api/system") is None
    assert "Content-type" not in seen["headers"]


def test_http_error_with_api_message(monkeypatch, client):
    def fake_urlopen(request, timeout):
        raise HttpError(b'{"error":{"message":"Nope"}}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    with pytest.raises(BookStackAPIError) as error:
        client.request("GET", "/api/system")

    assert error.value.status == 422
    assert error.value.message == "Nope"
    assert error.value.payload == {"error": {"message": "Nope"}}


def test_http_error_without_api_message(monkeypatch, client):
    def fake_urlopen(request, timeout):
        raise HttpError(b'{"message":"Nope"}')

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    with pytest.raises(BookStackAPIError) as error:
        client.request("GET", "/api/system")

    assert str(error.value) == "BookStack API error 422: Unprocessable"
    assert error.value.payload == {"message": "Nope"}


def test_http_error_with_plain_text_body(monkeypatch, client):
    def fake_urlopen(request, timeout):
        raise HttpError(b"plain failure")

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    with pytest.raises(BookStackAPIError) as error:
        client.request("GET", "/api/system")

    assert str(error.value) == "BookStack API error 422: Unprocessable"
    assert error.value.payload == "plain failure"


def test_invalid_url_raises_api_error_instead_of_crashing(monkeypatch, client):
    def fake_urlopen(request, timeout):
        raise http.client.InvalidURL("URL can't contain control characters. '/api/books/1 2' (found at least ' ')")

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    with pytest.raises(BookStackAPIError) as error:
        client.get("books", "1 2")

    assert error.value.status == 0
    assert "control characters" in error.value.message


def test_json_body_rejected_when_combined_with_fields(client):
    with pytest.raises(ValueError, match="json cannot be combined with fields or files"):
        client.request("POST", "/api/pages", json={"name": "Docs"}, fields={"foo": "bar"})


def test_network_error_raises_api_error(monkeypatch, client):
    def fake_urlopen(request, timeout):
        raise URLError("network down")

    monkeypatch.setattr("bookstack_cli.transport.URL_OPENER.open", fake_urlopen)

    with pytest.raises(BookStackAPIError) as error:
        client.request("GET", "/api/system")

    assert str(error.value) == "BookStack API error 0: network down"
    assert error.value.payload is None


class Response:
    def __init__(self, body, content_type="application/json"):
        self.body = body
        self.headers = Headers(content_type)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class Headers:
    def __init__(self, content_type):
        self.content_type = content_type

    def get_content_type(self):
        return self.content_type


class HttpError(HTTPError):
    def __init__(self, body):
        super().__init__("https://bookstack.test/api/system", 422, "Unprocessable", {}, None)
        self.body = body

    def read(self):
        return self.body
