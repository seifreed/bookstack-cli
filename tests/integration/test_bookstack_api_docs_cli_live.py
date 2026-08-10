from __future__ import annotations

import base64
import json
import os
import subprocess
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest

pytestmark = pytest.mark.integration


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def test_cli_against_bookstack_api_docs_endpoints(tmp_path: Path) -> None:
    if not os.environ.get("BOOKSTACK_LIVE_TESTS"):
        pytest.skip("set BOOKSTACK_LIVE_TESTS=1 and run scripts/bookstack-local.sh up")

    suffix = uuid.uuid4().hex[:8]
    made: dict[str, list[int]] = {
        "attachments": [],
        "books": [],
        "chapters": [],
        "comments": [],
        "images": [],
        "imports": [],
        "pages": [],
        "roles": [],
        "shelves": [],
        "users": [],
    }

    def cli_json(*args: str) -> object:
        result = subprocess.run(
            ["uv", "run", "bookstack", "--json", *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout) if result.stdout.strip() else None

    def request_json(method: str, path: str, *args: str) -> object:
        return cli_json("request", method, path, *args)

    def request_output(method: str, path: str, output: Path) -> None:
        subprocess.run(
            ["uv", "run", "bookstack", "--json", "request", method, path, "-o", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert output.exists()
        assert output.stat().st_size > 0

    def export_output(resource: str, item_id: int, fmt: str, output: Path) -> None:
        subprocess.run(
            ["uv", "run", "bookstack", "--json", "export", resource, str(item_id), fmt, "-o", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert output.exists()
        assert output.stat().st_size > 0

    def remember(resource: str, payload: object) -> int:
        assert isinstance(payload, dict)
        item_id = payload["id"]
        assert isinstance(item_id, int)
        made[resource].append(item_id)
        return item_id

    try:
        docs_html = tmp_path / "docs.html"
        docs_json = tmp_path / "docs.json"
        request_output("GET", "/api/docs", docs_html)
        request_output("GET", "/api/docs.json", docs_json)

        system = request_json("GET", "/api/system")
        assert isinstance(system, dict) and "version" in system

        book_id = remember(
            "books",
            cli_json(
                "create",
                "books",
                "--data",
                json.dumps(
                    {
                        "name": f"CLI Docs Book {suffix}",
                        "description": "live docs coverage",
                        "tags": [{"name": f"cli-tag-{suffix}", "value": "docs"}],
                    }
                ),
            ),
        )
        chapter_id = remember(
            "chapters",
            request_json(
                "POST",
                "/api/chapters",
                "--data",
                json.dumps({"book_id": book_id, "name": f"CLI Docs Chapter {suffix}", "description": "chapter"}),
            ),
        )
        page_id = remember(
            "pages",
            request_json(
                "POST",
                "/api/pages",
                "--data",
                json.dumps({"chapter_id": chapter_id, "name": f"CLI Docs Page {suffix}", "markdown": "hello docs"}),
            ),
        )

        _assert_list(cli_json("list", "pages", "--count", "1", "--offset", "0", "--sort", "+name"))
        assert _dict(cli_json("get", "pages", str(page_id)))["id"] == page_id
        assert (
            _dict(cli_json("update", "pages", str(page_id), "--data", json.dumps({"markdown": "updated"})))["id"]
            == page_id
        )
        for fmt in ("html", "pdf", "plaintext", "markdown", "zip"):
            export_output("pages", page_id, fmt, tmp_path / f"page.{fmt}")

        _assert_list(request_json("GET", "/api/chapters?count=1"))
        assert _dict(request_json("GET", f"/api/chapters/{chapter_id}"))["id"] == chapter_id
        assert (
            _dict(request_json("PUT", f"/api/chapters/{chapter_id}", "--data", json.dumps({"description": "updated"})))[
                "id"
            ]
            == chapter_id
        )
        for fmt in ("html", "pdf", "plaintext", "markdown", "zip"):
            export_output("chapters", chapter_id, fmt, tmp_path / f"chapter.{fmt}")

        _assert_list(request_json("GET", "/api/books?count=1"))
        assert _dict(request_json("GET", f"/api/books/{book_id}"))["id"] == book_id
        assert (
            _dict(request_json("PUT", f"/api/books/{book_id}", "--data", json.dumps({"description": "updated"})))["id"]
            == book_id
        )
        book_zip = tmp_path / "book.zip"
        for fmt in ("html", "pdf", "plaintext", "markdown", "zip"):
            export_output("books", book_id, fmt, tmp_path / f"book.{fmt}")

        shelf_id = remember(
            "shelves",
            request_json(
                "POST",
                "/api/shelves",
                "--data",
                json.dumps({"name": f"CLI Docs Shelf {suffix}", "books": [book_id]}),
            ),
        )
        _assert_list(request_json("GET", "/api/shelves?count=1"))
        assert _dict(request_json("GET", f"/api/shelves/{shelf_id}"))["id"] == shelf_id
        assert (
            _dict(request_json("PUT", f"/api/shelves/{shelf_id}", "--data", json.dumps({"description": "updated"})))[
                "id"
            ]
            == shelf_id
        )

        attachment_id = remember(
            "attachments",
            request_json(
                "POST",
                "/api/attachments",
                "--data",
                json.dumps({"name": f"CLI Docs Link {suffix}", "uploaded_to": page_id, "link": "https://example.com"}),
            ),
        )
        attachment_file = tmp_path / "attachment.txt"
        attachment_file.write_text("attachment", encoding="utf-8")
        remember(
            "attachments",
            request_json(
                "POST",
                "/api/attachments",
                "--field",
                f"name=CLI Docs File {suffix}",
                "--field",
                f"uploaded_to={page_id}",
                "--file",
                f"file={attachment_file}",
            ),
        )
        _assert_list(request_json("GET", "/api/attachments?count=1"))
        assert _dict(request_json("GET", f"/api/attachments/{attachment_id}"))["id"] == attachment_id
        assert (
            _dict(
                request_json(
                    "PUT",
                    f"/api/attachments/{attachment_id}",
                    "--data",
                    json.dumps({"name": f"CLI Docs Link Updated {suffix}"}),
                )
            )["id"]
            == attachment_id
        )

        _assert_list(request_json("GET", "/api/audit-log?count=1"))

        comment_id = remember(
            "comments",
            request_json(
                "POST",
                "/api/comments",
                "--data",
                json.dumps({"page_id": page_id, "html": "<p>comment</p>"}),
            ),
        )
        _assert_list(request_json("GET", "/api/comments?count=1"))
        assert _dict(request_json("GET", f"/api/comments/{comment_id}"))["id"] == comment_id
        assert (
            _dict(request_json("PUT", f"/api/comments/{comment_id}", "--data", json.dumps({"archived": True})))["id"]
            == comment_id
        )

        perms = cli_json("permissions", "get", "book", str(book_id))
        assert isinstance(perms, dict) and "fallback_permissions" in perms
        updated_perms = cli_json(
            "permissions",
            "set",
            "book",
            str(book_id),
            "--data",
            json.dumps({"fallback_permissions": {"inheriting": True}}),
        )
        assert isinstance(updated_perms, dict) and "fallback_permissions" in updated_perms

        shelf_perms = cli_json("permissions", "get", "bookshelf", str(shelf_id))
        assert isinstance(shelf_perms, dict) and "fallback_permissions" in shelf_perms

        image_path = tmp_path / "tiny.png"
        image_path.write_bytes(PNG_1X1)
        image_id = remember(
            "images",
            request_json(
                "POST",
                "/api/image-gallery",
                "--field",
                "type=gallery",
                "--field",
                f"uploaded_to={page_id}",
                "--field",
                f"name=CLI Docs Image {suffix}.png",
                "--file",
                f"image={image_path}",
            ),
        )
        image = _dict(request_json("GET", f"/api/image-gallery/{image_id}"))
        request_output("GET", f"/api/image-gallery/{image_id}/data", tmp_path / "image-by-id.png")
        request_output(
            "GET", f"/api/image-gallery/url/data?url={quote(str(image['url']), safe='')}", tmp_path / "image-by-url.png"
        )
        _assert_list(request_json("GET", "/api/image-gallery?count=1"))
        assert (
            _dict(
                request_json(
                    "PUT",
                    f"/api/image-gallery/{image_id}",
                    "--data",
                    json.dumps({"name": f"CLI Docs Image Updated {suffix}.png"}),
                )
            )["id"]
            == image_id
        )

        _assert_list(request_json("GET", "/api/imports?count=1"))
        import_id = remember(
            "imports",
            request_json("POST", "/api/imports", "--file", f"file={book_zip}"),
        )
        assert _dict(request_json("GET", f"/api/imports/{import_id}"))["id"] == import_id
        imported_book = request_json("POST", f"/api/imports/{import_id}")
        if isinstance(imported_book, dict) and isinstance(imported_book.get("id"), int):
            made["books"].append(imported_book["id"])
            made["imports"].remove(import_id)

        deleted_page_id = remember(
            "pages",
            request_json(
                "POST",
                "/api/pages",
                "--data",
                json.dumps({"book_id": book_id, "name": f"CLI Restore Page {suffix}", "markdown": "restore"}),
            ),
        )
        cli_json("delete", "pages", str(deleted_page_id))
        made["pages"].remove(deleted_page_id)
        deletion_id = _find_deletion_id(cli_json("recycle-bin", "list"), f"CLI Restore Page {suffix}")
        restored = cli_json("recycle-bin", "restore", str(deletion_id))
        assert isinstance(restored, dict) and restored["restore_count"] >= 1
        made["pages"].append(deleted_page_id)

        destroyed_page_id = remember(
            "pages",
            request_json(
                "POST",
                "/api/pages",
                "--data",
                json.dumps({"book_id": book_id, "name": f"CLI Destroy Page {suffix}", "markdown": "destroy"}),
            ),
        )
        cli_json("delete", "pages", str(destroyed_page_id))
        made["pages"].remove(destroyed_page_id)
        destroy_deletion_id = _find_deletion_id(cli_json("recycle-bin", "list"), f"CLI Destroy Page {suffix}")
        destroyed = cli_json("recycle-bin", "destroy", str(destroy_deletion_id))
        assert isinstance(destroyed, dict) and destroyed["delete_count"] >= 1

        role_id = remember(
            "roles",
            request_json(
                "POST",
                "/api/roles",
                "--data",
                json.dumps({"display_name": f"CLI Docs Role {suffix}", "description": "role", "permissions": []}),
            ),
        )
        _assert_list(request_json("GET", "/api/roles?count=1"))
        assert _dict(request_json("GET", f"/api/roles/{role_id}"))["id"] == role_id
        assert (
            _dict(request_json("PUT", f"/api/roles/{role_id}", "--data", json.dumps({"description": "updated"})))["id"]
            == role_id
        )

        user_id = remember(
            "users",
            request_json(
                "POST",
                "/api/users",
                "--data",
                json.dumps(
                    {
                        "name": f"CLI Docs User {suffix}",
                        "email": f"cli-{suffix}@example.com",
                        "password": "bookstack-test-pass",
                        "roles": [role_id],
                    }
                ),
            ),
        )
        _assert_list(request_json("GET", "/api/users?count=1"))
        assert _dict(request_json("GET", f"/api/users/{user_id}"))["id"] == user_id
        assert (
            _dict(request_json("PUT", f"/api/users/{user_id}", "--data", json.dumps({"language": "en"})))["id"]
            == user_id
        )

        _assert_list(cli_json("search", suffix, "--page", "1", "--count", "2"))
        _assert_list(cli_json("tags", "--count", "5"))
        _assert_list(cli_json("tags", "--name", f"cli-tag-{suffix}"))

        all_books = cli_json("list", "books", "--all")
        assert isinstance(all_books, list) and any(book["id"] == book_id for book in all_books)
    finally:
        for resource, ids in (
            ("comments", made["comments"]),
            ("attachments", made["attachments"]),
            ("images", made["images"]),
            ("imports", made["imports"]),
            ("shelves", made["shelves"]),
            ("pages", made["pages"]),
            ("chapters", made["chapters"]),
            ("books", made["books"]),
            ("users", made["users"]),
            ("roles", made["roles"]),
        ):
            for item_id in reversed(ids):
                subprocess.run(
                    ["uv", "run", "bookstack", "--json", "request", "DELETE", f"/api/{resource}/{item_id}"],
                    check=False,
                    capture_output=True,
                    text=True,
                )


def _dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _assert_list(value: object) -> None:
    assert isinstance(value, dict)
    assert isinstance(value.get("data"), list)
    assert isinstance(value.get("total"), int)


def _find_deletion_id(value: object, name: str) -> int:
    assert isinstance(value, dict)
    for item in value["data"]:
        if item["deletable"]["name"] == name:
            deletion_id = item["id"]
            assert isinstance(deletion_id, int)
            return deletion_id
    raise AssertionError(f"Deletion not found for {name}")
