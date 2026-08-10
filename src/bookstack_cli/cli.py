from __future__ import annotations

import argparse
import json
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .client import BookStackClient
from .config import BookStackConfigError
from .errors import BookStackAPIError

if TYPE_CHECKING:
    # argparse._SubParsersAction is only generic in typeshed's stubs, not at
    # runtime, so this alias must stay inside a TYPE_CHECKING guard.
    SubParsers = argparse._SubParsersAction[argparse.ArgumentParser]

CONTENT_TYPES = ("book", "chapter", "page", "bookshelf")
EXPORT_RESOURCES = ("books", "chapters", "pages")
EXPORT_FORMATS = ("html", "pdf", "plaintext", "markdown", "zip")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        client = BookStackClient.from_env(env_file=args.env_file, timeout=args.timeout)
        result = args.func(client, args)
        _print(result, compact=args.json)
    except (BookStackAPIError, BookStackConfigError, OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bookstack",
        description="CLI for the BookStack REST API. Configure with BOOKSTACK_* env vars or a .env file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""commands:
  list RESOURCE [--count N] [--offset N] [--sort FIELD] [--filter FIELD=VALUE]
      List resources. Example: bookstack list books --count 20 --sort +name

  get RESOURCE ID
      Read one resource. Example: bookstack get pages 1

  batch-get RESOURCE ID [ID ...] [--workers N]
      Read several resources in parallel. Example: bookstack batch-get pages 1 2 3 --workers 3

  create RESOURCE --data JSON
      Create a resource. Example: bookstack create books --data '{"name":"Docs"}'

  update RESOURCE ID --data JSON
      Update a resource. Example: bookstack update books 1 --data '{"name":"Docs v2"}'

  delete RESOURCE ID
      Delete a resource. Example: bookstack delete pages 1

  request METHOD PATH [--data JSON] [--field NAME=VALUE] [--file NAME=PATH] [-o PATH]
      Call any BookStack API endpoint, including multipart uploads and exports.
      Examples:
        bookstack request GET /api/system
        bookstack request POST /api/image-gallery --field type=gallery --field uploaded_to=1 --file image=photo.png

  search QUERY [--page N] [--count N]
      Search across content. Example: bookstack search "docs"

  tags [--name NAME] [--count N]
      List tag names, or values for a tag name. Example: bookstack tags --name status

  recycle-bin list [--count N] [--offset N]
  recycle-bin restore ID
  recycle-bin destroy ID
      Manage deleted content. Example: bookstack recycle-bin restore 4

  permissions get {book,chapter,page,bookshelf} ID
  permissions set {book,chapter,page,bookshelf} ID --data JSON
      Manage content-level permissions. Example: bookstack permissions get bookshelf 1

  export {books,chapters,pages} ID {html,pdf,plaintext,markdown,zip} -o PATH
      Download a resource export. Example: bookstack export pages 1 pdf -o page.pdf

resources:
  books, chapters, pages, shelves, attachments, comments, roles, users, image-gallery, imports, ...
""",
    )
    parser.add_argument("--env-file", default=".env", help="dotenv file to read; env vars override it")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    parser.add_argument("--json", action="store_true", help="print compact JSON")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    subparsers = parser.add_subparsers(required=True)

    _add_list_command(subparsers)
    _add_get_command(subparsers)
    _add_batch_get_command(subparsers)
    _add_create_command(subparsers)
    _add_update_command(subparsers)
    _add_delete_command(subparsers)
    _add_request_command(subparsers)
    _add_search_command(subparsers)
    _add_tags_command(subparsers)
    _add_recycle_bin_command(subparsers)
    _add_permissions_command(subparsers)
    _add_export_command(subparsers)
    return parser


def _add_list_command(subparsers: SubParsers) -> None:
    list_parser = subparsers.add_parser("list", help="list resources")
    _add_resource_argument(list_parser)
    list_parser.add_argument("--count", type=int, help="limit result count, or page size when --all is used")
    list_parser.add_argument("--offset", type=int, help="skip result count (not usable with --all)")
    list_parser.add_argument("--sort", help="BookStack sort expression, for example +name or -created_at")
    list_parser.add_argument("--filter", action="append", default=[], metavar="FIELD=VALUE", help="BookStack filter")
    list_parser.add_argument("--all", action="store_true", help="fetch every page automatically")
    list_parser.set_defaults(func=_list)


def _add_get_command(subparsers: SubParsers) -> None:
    get_parser = subparsers.add_parser("get", help="read one resource")
    _add_resource_argument(get_parser)
    _add_id_argument(get_parser)
    get_parser.set_defaults(func=lambda client, args: client.get(args.resource, args.id))


def _add_batch_get_command(subparsers: SubParsers) -> None:
    batch_parser = subparsers.add_parser("batch-get", help="read resources in parallel")
    _add_resource_argument(batch_parser)
    batch_parser.add_argument("ids", nargs="+", help="resource IDs")
    batch_parser.add_argument("--workers", type=int, default=4, help="parallel worker count")
    batch_parser.set_defaults(func=lambda client, args: client.get_many(args.resource, args.ids, args.workers))


def _add_create_command(subparsers: SubParsers) -> None:
    create_parser = subparsers.add_parser("create", help="create a resource")
    _add_resource_argument(create_parser)
    _add_data_argument(create_parser)
    create_parser.set_defaults(func=lambda client, args: client.create(args.resource, args.data))


def _add_update_command(subparsers: SubParsers) -> None:
    update_parser = subparsers.add_parser("update", help="update a resource")
    _add_resource_argument(update_parser)
    _add_id_argument(update_parser)
    _add_data_argument(update_parser)
    update_parser.set_defaults(func=lambda client, args: client.update(args.resource, args.id, args.data))


def _add_delete_command(subparsers: SubParsers) -> None:
    delete_parser = subparsers.add_parser("delete", help="delete a resource")
    _add_resource_argument(delete_parser)
    _add_id_argument(delete_parser)
    delete_parser.set_defaults(func=lambda client, args: client.delete(args.resource, args.id))


def _add_request_command(subparsers: SubParsers) -> None:
    request_parser = subparsers.add_parser("request", help="call any API endpoint")
    request_parser.add_argument("method", help="HTTP method, for example GET, POST, PUT, DELETE")
    request_parser.add_argument("path", help="API path, for example /api/system")
    request_parser.add_argument("--data", type=_json_object, help="JSON object request body")
    request_parser.add_argument("--field", action="append", default=[], metavar="NAME=VALUE", help="multipart field")
    request_parser.add_argument("--file", action="append", default=[], metavar="NAME=PATH", help="multipart file")
    request_parser.add_argument("-o", "--output", help="write raw response bytes to a file")
    request_parser.set_defaults(func=_request)


def _add_search_command(subparsers: SubParsers) -> None:
    search_parser = subparsers.add_parser("search", help="search content")
    search_parser.add_argument("query", help="BookStack search query")
    search_parser.add_argument("--page", type=int, help="page number")
    search_parser.add_argument("--count", type=int, help="limit result count")
    search_parser.set_defaults(func=lambda client, args: client.search(args.query, page=args.page, count=args.count))


def _add_tags_command(subparsers: SubParsers) -> None:
    tags_parser = subparsers.add_parser("tags", help="list tag names or values")
    tags_parser.add_argument("--name", help="list values for this tag name instead of every tag name")
    tags_parser.add_argument("--count", type=int, help="limit result count")
    tags_parser.set_defaults(func=lambda client, args: client.tags(name=args.name, count=args.count))


def _add_recycle_bin_command(subparsers: SubParsers) -> None:
    recycle_bin_parser = subparsers.add_parser("recycle-bin", help="manage deleted content")
    recycle_bin_subparsers = recycle_bin_parser.add_subparsers(required=True)

    rb_list_parser = recycle_bin_subparsers.add_parser("list", help="list deleted items")
    rb_list_parser.add_argument("--count", type=int, help="limit result count")
    rb_list_parser.add_argument("--offset", type=int, help="skip result count")
    rb_list_parser.set_defaults(func=lambda client, args: client.recycle_bin_list(count=args.count, offset=args.offset))

    rb_restore_parser = recycle_bin_subparsers.add_parser("restore", help="restore a deleted item")
    _add_id_argument(rb_restore_parser)
    rb_restore_parser.set_defaults(func=lambda client, args: client.recycle_bin_restore(args.id))

    rb_destroy_parser = recycle_bin_subparsers.add_parser("destroy", help="permanently delete a deleted item")
    _add_id_argument(rb_destroy_parser)
    rb_destroy_parser.set_defaults(func=lambda client, args: client.recycle_bin_destroy(args.id))


def _add_permissions_command(subparsers: SubParsers) -> None:
    permissions_parser = subparsers.add_parser("permissions", help="manage content-level permissions")
    permissions_subparsers = permissions_parser.add_subparsers(required=True)

    perm_get_parser = permissions_subparsers.add_parser("get", help="read content permissions")
    _add_content_type_argument(perm_get_parser)
    _add_id_argument(perm_get_parser)
    perm_get_parser.set_defaults(func=lambda client, args: client.get_content_permissions(args.content_type, args.id))

    perm_set_parser = permissions_subparsers.add_parser("set", help="update content permissions")
    _add_content_type_argument(perm_set_parser)
    _add_id_argument(perm_set_parser)
    _add_data_argument(perm_set_parser)
    perm_set_parser.set_defaults(
        func=lambda client, args: client.set_content_permissions(args.content_type, args.id, args.data)
    )


def _add_export_command(subparsers: SubParsers) -> None:
    export_parser = subparsers.add_parser("export", help="download a resource export")
    export_parser.add_argument("resource", choices=EXPORT_RESOURCES, help="exportable resource")
    _add_id_argument(export_parser)
    export_parser.add_argument("format", choices=EXPORT_FORMATS, help="export format")
    export_parser.add_argument("-o", "--output", required=True, help="file path to write the export to")
    export_parser.set_defaults(func=_export)


def _add_resource_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("resource", help="API resource, for example books or pages")


def _add_id_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("id", help="resource ID")


def _add_data_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data", required=True, type=_json_object, help="JSON object request body")


def _add_content_type_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("content_type", choices=CONTENT_TYPES, help="content type")


def _version() -> str:
    try:
        return _package_version("bookstack-cli")
    except PackageNotFoundError:
        return "unknown"


def _list(client: BookStackClient, args: argparse.Namespace) -> Any:
    filters = dict(_filter(item) for item in args.filter)
    if args.all:
        if args.offset is not None:
            raise ValueError("--all cannot be combined with --offset")
        return client.list_all(args.resource, count=args.count, sort=args.sort, filters=filters)
    return client.list(args.resource, count=args.count, offset=args.offset, sort=args.sort, filters=filters)


def _export(client: BookStackClient, args: argparse.Namespace) -> None:
    response = client.export(args.resource, args.id, args.format)
    Path(args.output).write_bytes(response.body)
    return None


def _request(client: BookStackClient, args: argparse.Namespace) -> Any:
    fields = dict(_pair(item, "--field") for item in args.field)
    files = {name: Path(path) for name, path in (_pair(item, "--file") for item in args.file)}
    if args.data is not None and (fields or files):
        raise ValueError("--data cannot be combined with --field or --file")

    if args.output is not None:
        response = client.request_raw(args.method, args.path, json=args.data, fields=fields, files=files)
        Path(args.output).write_bytes(response.body)
        return None
    return client.request(args.method, args.path, json=args.data, fields=fields, files=files)


def _json_object(value: str) -> dict[str, Any]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    if not isinstance(data, dict):
        raise argparse.ArgumentTypeError("--data must be a JSON object")
    return data


def _filter(value: str) -> tuple[str, str]:
    return _pair(value, "--filter")


def _pair(value: str, option: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"{option} must use NAME=VALUE")
    key, pair_value = value.split("=", 1)
    if not key:
        raise ValueError(f"{option} name cannot be empty")
    return key, pair_value


def _print(data: Any, *, compact: bool) -> None:
    if data is None:
        return
    indent = None if compact else 2
    print(json.dumps(data, indent=indent, ensure_ascii=False))
