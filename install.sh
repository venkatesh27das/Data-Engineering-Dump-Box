#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_CHECKS=false
CREATE_FIXTURES=false

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Install the Workbook Agent development dependencies.

Options:
  --check          Run linting, tests, and the production frontend build.
  --with-fixtures  Recreate the generated backend workbook fixtures.
  -h, --help       Show this help message.
EOF
}

for argument in "$@"; do
  case "$argument" in
    --check)
      RUN_CHECKS=true
      ;;
    --with-fixtures)
      CREATE_FIXTURES=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $argument" >&2
      usage >&2
      exit 1
      ;;
  esac
done

require_command() {
  local command_name="$1"
  local install_hint="$2"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    echo "$install_hint" >&2
    exit 1
  fi
}

require_command uv "Install uv from https://docs.astral.sh/uv/getting-started/installation/"
require_command node "Install Node.js 20 or newer from https://nodejs.org/"
require_command npm "npm is normally included with Node.js."

NODE_MAJOR="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
if [[ ! "$NODE_MAJOR" =~ ^[0-9]+$ ]] || (( NODE_MAJOR < 20 )); then
  echo "Node.js 20 or newer is required; found $(node --version)." >&2
  exit 1
fi

cd "$PROJECT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example."
else
  echo "Keeping existing .env."
fi

mkdir -p data/storage

echo "Installing backend dependencies..."
uv sync --project backend --extra dev --frozen

echo "Installing frontend dependencies..."
npm ci --prefix frontend

if [[ "$CREATE_FIXTURES" == true ]]; then
  echo "Creating backend workbook fixtures..."
  uv run --project backend python scripts/create_test_workbooks.py
fi

if [[ "$RUN_CHECKS" == true ]]; then
  echo "Running repository checks..."
  make check
fi

cat <<'EOF'

Installation complete.

Start the application in two terminals:
  make backend
  make frontend

Then open http://localhost:5173
EOF
