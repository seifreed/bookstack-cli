#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
unset VIRTUAL_ENV

uv run black --check src tests
uv run ruff check src tests
uv run mypy
uv run bandit -q -r src
uv run pip-audit
uv run pytest --cov=bookstack_cli --cov-report=term-missing --cov-fail-under=100 -q -m "not integration"
