import argparse
from importlib.metadata import PackageNotFoundError

import pytest

from bookstack_cli.cli import _filter, _json_object, _pair, main
from bookstack_cli.transport import RawResponse


class _StubClient:
    @classmethod
    def from_env(cls, env_file=".env", timeout=30.0):
        return cls()


def test_cli_list_uses_env_file(tmp_path, monkeypatch, capsys):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BOOKSTACK_URL=https://bookstack.test\nBOOKSTACK_TOKEN_ID=id\nBOOKSTACK_TOKEN_SECRET=secret\n",
        encoding="utf-8",
    )

    def fake_request(self, method, path, *, params=None, json=None, fields=None, files=None):
        assert method == "GET"
        assert path == "/api/books"
        assert params == {"count": 5}
        return {"data": [], "total": 0}

    monkeypatch.setattr("bookstack_cli.client.BookStackClient.request", fake_request)

    assert main(["--env-file", str(env_file), "list", "books", "--count", "5"]) == 0
    assert '"total": 0' in capsys.readouterr().out


def test_cli_commands_dispatch(monkeypatch, capsys):
    calls = []

    class Client:
        @classmethod
        def from_env(cls, env_file=".env", timeout=30.0):
            calls.append(("from_env", env_file, timeout))
            return cls()

        def get(self, resource, item_id):
            return {"method": "get", "resource": resource, "id": item_id}

        def get_many(self, resource, ids, workers):
            return [{"method": "batch", "resource": resource, "ids": ids, "workers": workers}]

        def create(self, resource, data):
            return {"method": "create", "resource": resource, "data": data}

        def update(self, resource, item_id, data):
            return {"method": "update", "resource": resource, "id": item_id, "data": data}

        def delete(self, resource, item_id):
            return {"method": "delete", "resource": resource, "id": item_id}

        def request(self, method, path, *, json=None, fields=None, files=None):
            return {
                "method": method,
                "path": path,
                "json": json,
                "fields": fields,
                "files": {key: str(value) for key, value in files.items()},
            }

    monkeypatch.setattr("bookstack_cli.cli.BookStackClient", Client)

    assert main(["--env-file", "local.env", "--timeout", "3", "--json", "get", "books", "1"]) == 0
    assert calls == [("from_env", "local.env", 3.0)]
    assert capsys.readouterr().out == '{"method": "get", "resource": "books", "id": "1"}\n'

    assert main(["--json", "batch-get", "pages", "1", "2", "--workers", "2"]) == 0
    assert '"workers": 2' in capsys.readouterr().out

    assert main(["--json", "create", "books", "--data", '{"name":"Docs"}']) == 0
    assert '"method": "create"' in capsys.readouterr().out

    assert main(["--json", "update", "books", "1", "--data", '{"name":"Docs"}']) == 0
    assert '"method": "update"' in capsys.readouterr().out

    assert main(["--json", "delete", "books", "1"]) == 0
    assert '"method": "delete"' in capsys.readouterr().out

    assert main(["--json", "request", "POST", "/api/books", "--field", "name=Docs", "--file", "file=README.md"]) == 0
    output = capsys.readouterr().out
    assert '"fields": {"name": "Docs"}' in output
    assert '"files": {"file": "README.md"}' in output


def test_cli_new_commands_dispatch(monkeypatch, capsys):
    class Client(_StubClient):
        def search(self, query, *, page=None, count=None):
            return {"method": "search", "query": query, "page": page, "count": count}

        def tags(self, *, name=None, count=None):
            return {"method": "tags", "name": name, "count": count}

        def recycle_bin_list(self, *, count=None, offset=None):
            return {"method": "recycle_bin_list", "count": count, "offset": offset}

        def recycle_bin_restore(self, deletion_id):
            return {"method": "recycle_bin_restore", "id": deletion_id}

        def recycle_bin_destroy(self, deletion_id):
            return {"method": "recycle_bin_destroy", "id": deletion_id}

        def get_content_permissions(self, content_type, content_id):
            return {"method": "get_content_permissions", "type": content_type, "id": content_id}

        def set_content_permissions(self, content_type, content_id, data):
            return {"method": "set_content_permissions", "type": content_type, "id": content_id, "data": data}

        def list_all(self, resource, *, count=None, sort=None, filters=None):
            return [{"method": "list_all", "resource": resource, "count": count, "sort": sort, "filters": filters}]

    monkeypatch.setattr("bookstack_cli.cli.BookStackClient", Client)

    assert main(["--json", "search", "docs", "--page", "2", "--count", "5"]) == 0
    assert capsys.readouterr().out == '{"method": "search", "query": "docs", "page": 2, "count": 5}\n'

    assert main(["--json", "tags"]) == 0
    assert '"name": null' in capsys.readouterr().out

    assert main(["--json", "tags", "--name", "status"]) == 0
    assert '"name": "status"' in capsys.readouterr().out

    assert main(["--json", "recycle-bin", "list", "--count", "5"]) == 0
    assert '"method": "recycle_bin_list"' in capsys.readouterr().out

    assert main(["--json", "recycle-bin", "restore", "4"]) == 0
    assert '"method": "recycle_bin_restore"' in capsys.readouterr().out

    assert main(["--json", "recycle-bin", "destroy", "4"]) == 0
    assert '"method": "recycle_bin_destroy"' in capsys.readouterr().out

    assert main(["--json", "permissions", "get", "bookshelf", "1"]) == 0
    assert '"method": "get_content_permissions"' in capsys.readouterr().out

    assert main(["--json", "permissions", "set", "book", "1", "--data", '{"fallback_permissions":{}}']) == 0
    assert '"method": "set_content_permissions"' in capsys.readouterr().out

    assert main(["--json", "list", "books", "--all"]) == 0
    assert '"method": "list_all"' in capsys.readouterr().out


def test_cli_export_writes_output(monkeypatch, tmp_path):
    class Client(_StubClient):
        def export(self, resource, item_id, export_format):
            assert (resource, item_id, export_format) == ("pages", "1", "pdf")
            return RawResponse(b"%PDF-1.4", "application/pdf")

    monkeypatch.setattr("bookstack_cli.cli.BookStackClient", Client)
    output = tmp_path / "page.pdf"

    assert main(["export", "pages", "1", "pdf", "-o", str(output)]) == 0
    assert output.read_bytes() == b"%PDF-1.4"


def test_cli_export_requires_output_and_valid_choices():
    with pytest.raises(SystemExit) as missing_output:
        main(["export", "pages", "1", "pdf"])
    assert missing_output.value.code == 2

    with pytest.raises(SystemExit) as bad_resource:
        main(["export", "notaresource", "1", "pdf", "-o", "x"])
    assert bad_resource.value.code == 2


def test_cli_permissions_rejects_shelf_typo():
    with pytest.raises(SystemExit) as error:
        main(["permissions", "get", "shelf", "1"])
    assert error.value.code == 2


def test_cli_list_all_rejects_offset(monkeypatch, capsys):
    monkeypatch.setattr("bookstack_cli.cli.BookStackClient", _StubClient)

    assert main(["list", "books", "--all", "--offset", "5"]) == 1
    assert "--all cannot be combined with --offset" in capsys.readouterr().err


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert "bookstack" in capsys.readouterr().out


def test_cli_version_falls_back_when_metadata_missing(monkeypatch, capsys):
    def fail_version(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr("bookstack_cli.cli._package_version", fail_version)

    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert "unknown" in capsys.readouterr().out


def test_cli_request_writes_output(monkeypatch, tmp_path):
    class Client(_StubClient):
        def request_raw(self, method, path, *, json=None, fields=None, files=None):
            return RawResponse(b"downloaded", "application/octet-stream")

    monkeypatch.setattr("bookstack_cli.cli.BookStackClient", Client)
    output = tmp_path / "out.bin"

    assert main(["request", "GET", "/api/pages/1/export/pdf", "-o", str(output)]) == 0
    assert output.read_bytes() == b"downloaded"


def test_cli_file_error_returns_failure(monkeypatch, tmp_path, capsys):
    class Client(_StubClient):
        def request_raw(self, method, path, *, json=None, fields=None, files=None):
            return RawResponse(b"downloaded", "application/octet-stream")

    monkeypatch.setattr("bookstack_cli.cli.BookStackClient", Client)

    assert main(["request", "GET", "/api/pages/1/export/pdf", "-o", str(tmp_path / "missing" / "out.bin")]) == 1
    assert "No such file or directory" in capsys.readouterr().err


def test_cli_empty_output_path_fails_instead_of_silently_printing(monkeypatch, capsys):
    class Client(_StubClient):
        def request_raw(self, method, path, *, json=None, fields=None, files=None):
            return RawResponse(b"downloaded", "application/octet-stream")

    monkeypatch.setattr("bookstack_cli.cli.BookStackClient", Client)

    assert main(["request", "GET", "/api/pages/1/export/pdf", "-o", ""]) == 1
    assert capsys.readouterr().err.strip() != ""


def test_cli_print_failure_is_reported_cleanly(monkeypatch, capsys):
    class Client(_StubClient):
        def request(self, method, path, *, json=None, fields=None, files=None):
            return {"ok": True}

    def failing_print(data, *, compact):
        raise BrokenPipeError("[Errno 32] Broken pipe")

    monkeypatch.setattr("bookstack_cli.cli.BookStackClient", Client)
    monkeypatch.setattr("bookstack_cli.cli._print", failing_print)

    assert main(["request", "GET", "/api/system"]) == 1
    assert "Broken pipe" in capsys.readouterr().err


def test_cli_errors(monkeypatch, capsys):
    monkeypatch.setattr("bookstack_cli.cli.BookStackClient", _StubClient)

    assert main(["request", "POST", "/api/books", "--data", '{"name":"Docs"}', "--field", "x=y"]) == 1
    assert "--data cannot be combined" in capsys.readouterr().err


def test_print_none(monkeypatch, capsys):
    class Client(_StubClient):
        def request(self, method, path, *, json=None, fields=None, files=None):
            return None

    monkeypatch.setattr("bookstack_cli.cli.BookStackClient", Client)

    assert main(["request", "DELETE", "/api/pages/1"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_config_error(monkeypatch, capsys):
    def fail_from_env(env_file=".env", timeout=30.0):
        raise ValueError("bad config")

    monkeypatch.setattr("bookstack_cli.cli.BookStackClient.from_env", fail_from_env)

    assert main(["list", "books"]) == 1
    assert "bad config" in capsys.readouterr().err


def test_helpers_validate_input():
    assert _json_object('{"a":1}') == {"a": 1}
    with pytest.raises(argparse.ArgumentTypeError):
        _json_object("[1]")
    with pytest.raises(argparse.ArgumentTypeError):
        _json_object("{")
    with pytest.raises(ValueError):
        _pair("missing", "--field")
    with pytest.raises(ValueError, match="name cannot be empty"):
        _pair("=value", "--field")
    assert _filter("name:like=%docs%") == ("name:like", "%docs%")
