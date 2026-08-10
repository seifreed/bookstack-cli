import json
import os
import uuid
from pathlib import Path

import pytest

from bookstack_cli.cli import main

pytestmark = pytest.mark.integration


def test_cli_commands_against_bookstack(capsys):
    if not os.environ.get("BOOKSTACK_LIVE_TESTS"):
        pytest.skip("set BOOKSTACK_LIVE_TESTS=1 and run scripts/bookstack-local.sh up")

    suffix = uuid.uuid4().hex[:8]
    book_id = None
    second_book_id = None
    page_id = None

    try:
        env_file = Path(".env")
        assert env_file.exists()

        created_book = _run_json(
            capsys,
            "--env-file",
            str(env_file),
            "--timeout",
            "10",
            "create",
            "books",
            "--data",
            json.dumps({"name": f"CLI Test B {suffix}"}),
        )
        book_id = created_book["id"]

        second_book = _run_json(
            capsys,
            "request",
            "POST",
            "/api/books",
            "--data",
            json.dumps({"name": f"CLI Test A {suffix}"}),
        )
        second_book_id = second_book["id"]

        listed = _run_json(
            capsys,
            "list",
            "books",
            "--count",
            "1",
            "--offset",
            "0",
            "--sort",
            "+name",
            "--filter",
            f"name:like=CLI Test % {suffix}",
        )
        assert listed["total"] == 2
        assert listed["data"][0]["name"] == f"CLI Test A {suffix}"

        fetched_book = _run_json(capsys, "get", "books", str(book_id))
        assert fetched_book["id"] == book_id

        created_page = _run_json(
            capsys,
            "create",
            "pages",
            "--data",
            json.dumps({"book_id": book_id, "name": f"Page {suffix}", "markdown": "hello"}),
        )
        page_id = created_page["id"]

        updated_page = _run_json(
            capsys, "update", "pages", str(page_id), "--data", json.dumps({"name": f"Updated {suffix}"})
        )
        assert updated_page["name"] == f"Updated {suffix}"

        batch = _run_json(capsys, "batch-get", "pages", str(page_id), "--workers", "1")
        assert batch[0]["id"] == page_id

        system = _run_json(capsys, "request", "GET", "/api/system")
        assert "version" in system

        assert main(["--json", "delete", "pages", str(page_id)]) == 0
        page_id = None
        capsys.readouterr()
    finally:
        if page_id is not None:
            main(["--json", "delete", "pages", str(page_id)])
            capsys.readouterr()
        if book_id is not None:
            main(["--json", "delete", "books", str(book_id)])
            capsys.readouterr()
        if second_book_id is not None:
            main(["--json", "delete", "books", str(second_book_id)])
            capsys.readouterr()


def _run_json(capsys, *args):
    assert main(["--json", *args]) == 0
    return json.loads(capsys.readouterr().out)
