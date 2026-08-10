<p align="center">
  <img src="https://img.shields.io/badge/bookstack--client-BookStack%20API-blue?style=for-the-badge" alt="bookstack-client">
</p>

<h1 align="center">bookstack-client</h1>

<p align="center">
  <strong>Python 3.14 CLI and library for the BookStack REST API</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/bookstack-client/"><img src="https://img.shields.io/pypi/v/bookstack-client?style=flat-square&logo=pypi&logoColor=white" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/bookstack-client/"><img src="https://img.shields.io/pypi/pyversions/bookstack-client?style=flat-square&logo=python&logoColor=white" alt="Python Versions"></a>
  <a href="https://github.com/seifreed/bookstack-cli/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"></a>
</p>

<p align="center">
  <a href="https://github.com/seifreed/bookstack-cli/stargazers"><img src="https://img.shields.io/github/stars/seifreed/bookstack-cli?style=flat-square" alt="GitHub Stars"></a>
  <a href="https://github.com/seifreed/bookstack-cli/issues"><img src="https://img.shields.io/github/issues/seifreed/bookstack-cli?style=flat-square" alt="GitHub Issues"></a>
  <a href="https://buymeacoffee.com/seifreed"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-yellow?style=flat-square&logo=buy-me-a-coffee&logoColor=white" alt="Buy Me a Coffee"></a>
</p>

---

## Overview

**bookstack-client** is a Python package for working with the [BookStack REST API](https://demo.bookstackapp.com/api/docs) from scripts or the command line. It provides a small typed client, environment-based configuration, JSON output, and parallel batch reads.

BookStack authentication uses:

```text
Authorization: Token <token_id>:<token_secret>
```

### Key Features

| Feature | Description |
|---------|-------------|
| **CLI + Library** | Use as a command-line tool or Python package |
| **Python 3.14** | Built and tested for Python 3.14+ |
| **Environment Config** | Reads `BOOKSTACK_URL`, `BOOKSTACK_TOKEN_ID`, and `BOOKSTACK_TOKEN_SECRET` |
| **.env Support** | Loads credentials from a local `.env` file when environment variables are not set |
| **CRUD Helpers** | Convenience methods for list, get, create, update, and delete |
| **Raw Requests** | Access any BookStack API endpoint with `request()` |
| **Parallel Reads** | Fetch multiple resources concurrently with `get_many()` or `batch-get` |

### Supported Operations

```text
List resources   books, shelves, pages, chapters, users, roles, attachments, images
List all pages   Auto-paginate any resource with list --all
Read item        GET /api/<resource>/<id>
Create item      POST /api/<resource>
Update item      PUT /api/<resource>/<id>
Delete item      DELETE /api/<resource>/<id>
Export item      GET /api/<resource>/<id>/export/<format>
Search           GET /api/search
Tags             GET /api/tags/names, /api/tags/values-for-name
Recycle bin      List, restore, or permanently delete deleted content
Permissions      Read or set content-level permissions
Raw request      Any BookStack API path
Batch reads      Parallel get by IDs
```

---

## Installation

### From PyPI

```bash
pip install bookstack-client
```

### From Source

```bash
git clone https://github.com/seifreed/bookstack-cli.git
cd bookstack-cli
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .
```

---

## Configuration

### Environment Variables

```bash
export BOOKSTACK_URL="https://bookstack.example.com"
export BOOKSTACK_TOKEN_ID="token-id"
export BOOKSTACK_TOKEN_SECRET="token-secret"
```

### .env File

```dotenv
BOOKSTACK_URL=https://bookstack.example.com
BOOKSTACK_TOKEN_ID=token-id
BOOKSTACK_TOKEN_SECRET=token-secret
```

Environment variables override values loaded from `.env`.

---

## Quick Start

```bash
# List books
bookstack list books --count 20 --sort +name

# Read a page
bookstack get pages 1

# Fetch pages in parallel
bookstack batch-get pages 1 2 3 --workers 3
```

---

## Local BookStack Testing

This repository includes a Docker Compose setup for a disposable local BookStack instance:

```bash
scripts/bookstack-local.sh up
```

The script starts BookStack and MariaDB, creates an admin user, creates an API token, and writes a local `.env` file for the CLI.

Run the live CLI regression test with:

```bash
BOOKSTACK_LIVE_TESTS=1 uv run pytest -q tests/integration
```

Stop the stack with:

```bash
scripts/bookstack-local.sh down
```

---

## Usage

### Command Line Interface

```bash
# Create a page
bookstack create pages --data '{"book_id":1,"name":"API page","markdown":"Hello"}'

# Update a page
bookstack update pages 1 --data '{"name":"Renamed"}'

# Delete a page
bookstack delete pages 1

# Call a raw endpoint
bookstack request GET /api/system

# Multipart upload
bookstack request POST /api/image-gallery \
  --field type=gallery \
  --field uploaded_to=1 \
  --file image=photo.png

# Search content
bookstack search "deprecated runbook"

# List every tag name, or values for one tag
bookstack tags
bookstack tags --name status

# Manage the recycle bin
bookstack recycle-bin list --count 20 --offset 0
bookstack recycle-bin restore 4
bookstack recycle-bin destroy 4

# Read or set content-level permissions
bookstack permissions get bookshelf 1
bookstack permissions set book 1 --data '{"fallback_permissions":{"inheriting":false}}'

# Download an export directly
bookstack export pages 1 pdf -o page.pdf

# Fetch every page of a resource automatically
bookstack list books --all
```

### Global Options

These apply to every command and must come before the subcommand name:

| Option | Description |
|--------|-------------|
| `--env-file <path>` | dotenv file to read; environment variables still override it (default `.env`) |
| `--timeout <seconds>` | HTTP timeout in seconds (default `30`) |
| `--json` | Print compact JSON instead of indented |
| `--version` | Print the installed version and exit |

```bash
bookstack --env-file prod.env --timeout 60 --json list books
```

### Available Commands

| Command | Description |
|---------|-------------|
| `bookstack list <resource>` | List BookStack resources |
| `bookstack get <resource> <id>` | Fetch one resource by ID |
| `bookstack batch-get <resource> <ids...>` | Fetch several resources concurrently |
| `bookstack create <resource> --data <json>` | Create a resource |
| `bookstack update <resource> <id> --data <json>` | Update a resource |
| `bookstack delete <resource> <id>` | Delete a resource |
| `bookstack request <method> <path>` | Send a raw API request |
| `bookstack search <query>` | Search content |
| `bookstack tags` | List tag names, or values for `--name` |
| `bookstack recycle-bin list\|restore\|destroy` | Manage deleted content |
| `bookstack permissions get\|set <type> <id>` | Read or set content-level permissions |
| `bookstack export <resource> <id> <format> -o <path>` | Download a resource export |

### Listing Options

| Option | Description |
|--------|-------------|
| `--count <n>` | Limit result count, or page size when `--all` is used |
| `--offset <n>` | Offset list results (not usable with `--all`) |
| `--sort <field>` | Sort with BookStack syntax, such as `+name` |
| `--filter FIELD=VALUE` | Add BookStack `filter[...]` query parameters |
| `--all` | Fetch every page automatically |

### Raw Request Options

| Option | Description |
|--------|-------------|
| `--data <json>` | Send a JSON request body |
| `--field NAME=VALUE` | Add a multipart form field |
| `--file NAME=PATH` | Add a multipart file field |
| `-o, --output <path>` | Write raw response bytes to a file |

---

## Task Recipes

These recipes use the current CLI commands and work against any configured BookStack instance.

### Export All Books

Export every visible book as a ZIP archive:

```bash
mkdir -p exports/books

bookstack --json list books --all \
  | python3 -c 'import json,sys; [print(book["id"]) for book in json.load(sys.stdin)]' \
  | while read -r id; do
      bookstack export books "$id" zip -o "exports/books/${id}.zip"
    done
```

Use another export format by changing the last argument:

```bash
bookstack export books 1 pdf -o book-1.pdf
bookstack export books 1 markdown -o book-1.md
bookstack export books 1 html -o book-1.html
bookstack export books 1 plaintext -o book-1.txt
```

### Create Pages From Markdown

Create a page from a local Markdown file:

```bash
python3 - <<'PY' > /tmp/page.json
import json
from pathlib import Path

print(json.dumps({
    "book_id": 1,
    "name": "Runbook",
    "markdown": Path("runbook.md").read_text(encoding="utf-8"),
}))
PY

bookstack create pages --data "$(cat /tmp/page.json)"
```

Create the page inside a chapter instead:

```bash
python3 - <<'PY' > /tmp/page.json
import json
from pathlib import Path

print(json.dumps({
    "chapter_id": 10,
    "name": "Incident Response",
    "markdown": Path("incident-response.md").read_text(encoding="utf-8"),
}))
PY

bookstack create pages --data "$(cat /tmp/page.json)"
```

### Upload Images

Upload an image to a page and get reusable HTML/Markdown snippets in the response:

```bash
bookstack request POST /api/image-gallery \
  --field type=gallery \
  --field uploaded_to=1 \
  --field name=diagram.png \
  --file image=diagram.png
```

Download an uploaded image by ID:

```bash
bookstack request GET /api/image-gallery/42/data -o image.png
```

### Migrate Content

Move content between BookStack instances using BookStack ZIP exports/imports.

On the source instance:

```bash
bookstack export books 1 zip -o book-1.zip
```

On the target instance, after switching `.env` or environment variables:

```bash
import_id="$(
  bookstack --json request POST /api/imports --file file=book-1.zip \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'
)"

bookstack request POST "/api/imports/${import_id}"
```

For chapter or page imports, provide the target parent:

```bash
bookstack request POST "/api/imports/${import_id}" \
  --data '{"parent_type":"book","parent_id":1}'
```

### Partial Backup

Back up structure and selected binary exports without dumping the whole database:

```bash
mkdir -p backup/json backup/exports

for resource in books chapters pages shelves attachments users roles; do
  bookstack --json list "$resource" > "backup/json/${resource}.json"
done

bookstack --json request GET /api/system > backup/json/system.json
bookstack --json tags > backup/json/tag-names.json

bookstack --json list books --all \
  | python3 -c 'import json,sys; [print(book["id"]) for book in json.load(sys.stdin)]' \
  | while read -r id; do
      bookstack export books "$id" zip -o "backup/exports/book-${id}.zip"
    done
```

### Find Old Content

Find old or stale pages using BookStack list filters:

```bash
bookstack list pages \
  --filter updated_at:lt=2025-01-01 \
  --sort -updated_at \
  --count 50
```

Search content by text:

```bash
bookstack search "deprecated" --count 20
```

Search by BookStack query syntax:

```bash
bookstack search "{updated_by:me} runbook" --page 1 --count 20
```

### Automate Permissions

Read current content permissions for a book:

```bash
bookstack permissions get book 1
```

Set explicit fallback permissions while leaving role overrides unchanged:

```bash
bookstack permissions set book 1 --data '{
    "fallback_permissions": {
      "inheriting": false,
      "view": true,
      "create": false,
      "update": false,
      "delete": false
    }
  }'
```

Apply a role override:

```bash
bookstack permissions set book 1 --data '{
    "role_permissions": [
      {
        "role_id": 2,
        "view": true,
        "create": true,
        "update": true,
        "delete": false
      }
    ]
  }'
```

Use `page`, `book`, `chapter`, or `bookshelf` as the content type — not `shelf`, which BookStack rejects.

---

## Python Library

### Basic Usage

```python
from bookstack_cli import BookStackClient

client = BookStackClient.from_env()

books = client.list("books", count=20)
page = client.get("pages", 1)
pages = client.get_many("pages", [1, 2, 3], workers=3)
```

### Create and Update

```python
from bookstack_cli import BookStackClient

client = BookStackClient.from_env()

created = client.create("pages", {
    "book_id": 1,
    "name": "API page",
    "markdown": "Hello from Python",
})

updated = client.update("pages", created["id"], {"name": "Renamed page"})
```

### Raw API Requests

```python
from bookstack_cli import BookStackClient

client = BookStackClient.from_env()
system = client.request("GET", "/api/system")
```

### Search, Tags, Recycle Bin, Permissions & Export

```python
from bookstack_cli import BookStackClient

client = BookStackClient.from_env()

all_books = client.list_all("books")  # auto-paginates
results = client.search("runbook", count=20)
tag_names = client.tags()
tag_values = client.tags(name="status")

deleted = client.recycle_bin_list()
client.recycle_bin_restore(deleted["data"][0]["id"])
client.recycle_bin_destroy(4)

perms = client.get_content_permissions("bookshelf", 1)
client.set_content_permissions("book", 1, {"fallback_permissions": {"inheriting": False}})

pdf = client.export("pages", 1, "pdf")
open("page.pdf", "wb").write(pdf.body)
```

---

## Architecture

Five small modules, each with one job and a strict, one-directional dependency chain:

```text
cli.py        argparse wiring + dispatch only. Talks to BookStack only
              through BookStackClient's public methods.
    |
    v
client.py     One method per BookStack resource operation. Owns BookStack's
              URL and resource-shape conventions.
    |
    v
transport.py  HTTP encoding (JSON/multipart), headers, the raw urllib call,
              and mapping failures to BookStackAPIError.
    |
    v
config.py     Reads BOOKSTACK_* settings from the environment/.env file.
errors.py     The one error type API failures surface as.
```

`config.py` and `errors.py` have no internal dependencies. Nothing outside
`transport.py` imports `urllib` directly, and nothing outside `cli.py` builds
an `argparse` parser. `cli.py` never imports `transport.py` — it only ever
sees `BookStackClient`.

---

## Requirements

- Python 3.14+
- No runtime dependencies
- See [pyproject.toml](pyproject.toml) for package metadata

---

## Quality Gate

Run all local non-live checks with:

```bash
scripts/quality.sh
```

The gate runs black, ruff, mypy, bandit, pip-audit, and the non-integration pytest suite.

---

## Contributing

Contributions are welcome.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## Support the Project

If this project is useful in your workflows, you can support development:

<a href="https://buymeacoffee.com/seifreed" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50">
</a>

---

## License

This project is licensed under the MIT license. See [pyproject.toml](pyproject.toml).

**Attribution**
- Author: **seifreed** | [@seifreed](https://github.com/seifreed)
- Repository: [github.com/seifreed/bookstack-cli](https://github.com/seifreed/bookstack-cli)

---

<p align="center">
  <sub>Built for practical BookStack automation</sub>
</p>
