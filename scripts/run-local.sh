#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_PID=""
FRONTEND_PID=""
INSTALL_DEPENDENCIES=false
CHECK_ONLY=false

usage() {
  cat <<'EOF'
Usage: ./scripts/run-local.sh [--install] [--check]

  --install  Install/synchronize backend and frontend dependencies first.
  --check    Validate the local setup without starting either server.
  -h, --help Show this help message.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) INSTALL_DEPENDENCIES=true ;;
    --check) CHECK_ONLY=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

env_value() {
  local key="$1"
  awk -F= -v key="${key}" '$1 == key { sub(/^[^=]*=/, ""); value=$0 } END { print value }' "${REPOSITORY_ROOT}/.env"
}

port_owner() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | awk 'NR == 2 { print $1 " (PID " $2 ")" }'
  fi
}

cleanup() {
  local pid
  for pid in "${FRONTEND_PID}" "${BACKEND_PID}"; do
    if [[ "${pid}" =~ ^[0-9]+$ ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      wait "${pid}" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

require_command npm
require_command uv

cd "${REPOSITORY_ROOT}"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add integration credentials when required."
fi

if [[ "${INSTALL_DEPENDENCIES}" == true ]]; then
  make install
fi

if [[ ! -x backend/.venv/bin/python ]] || [[ ! -x frontend/node_modules/.bin/vite ]]; then
  echo "Dependencies are missing. Run ./scripts/run-local.sh --install once." >&2
  exit 1
fi

AI_PROVIDER_VALUE="$(env_value AI_PROVIDER)"
AI_PROVIDER_VALUE="${AI_PROVIDER_VALUE:-lmstudio}"
case "${AI_PROVIDER_VALUE}" in
  lmstudio)
    if [[ -z "$(env_value LMSTUDIO_ORCHESTRATOR_MODEL)" ]] || [[ -z "$(env_value LMSTUDIO_KNOWLEDGE_MODEL)" ]]; then
      echo "Warning: LM Studio model IDs are incomplete; model-backed runs will fail until they are configured."
    fi
    ;;
  openai_compatible)
    for required_key in OPENAI_COMPATIBLE_BASE_URL OPENAI_COMPATIBLE_API_KEY OPENAI_COMPATIBLE_ORCHESTRATOR_MODEL OPENAI_COMPATIBLE_KNOWLEDGE_MODEL; do
      if [[ -z "$(env_value "${required_key}")" ]]; then
        echo "Missing ${required_key} for AI_PROVIDER=openai_compatible." >&2
        exit 1
      fi
    done
    ;;
  *)
    echo "AI_PROVIDER must be lmstudio or openai_compatible, not '${AI_PROVIDER_VALUE}'." >&2
    exit 1
    ;;
esac

BACKEND_OWNER="$(port_owner 8000)"
FRONTEND_OWNER="$(port_owner 5173)"

if [[ "${CHECK_ONLY}" == true ]]; then
  echo "Local setup is valid. AI provider: ${AI_PROVIDER_VALUE}."
  [[ -n "${BACKEND_OWNER}" ]] && echo "Port 8000 is currently used by ${BACKEND_OWNER}."
  [[ -n "${FRONTEND_OWNER}" ]] && echo "Port 5173 is currently used by ${FRONTEND_OWNER}."
  exit 0
fi

if [[ -n "${BACKEND_OWNER}" ]]; then
  echo "Port 8000 is already used by ${BACKEND_OWNER}. Stop it before launching." >&2
  exit 1
fi
if [[ -n "${FRONTEND_OWNER}" ]]; then
  echo "Port 5173 is already used by ${FRONTEND_OWNER}. Stop it before launching." >&2
  exit 1
fi

(
  cd "${REPOSITORY_ROOT}/backend"
  exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

(
  cd "${REPOSITORY_ROOT}/frontend"
  exec ./node_modules/.bin/vite --host 127.0.0.1
) &
FRONTEND_PID=$!

echo "Knowledge Graph Builder is starting:"
echo "  Application: http://127.0.0.1:5173"
echo "  API docs:    http://127.0.0.1:8000/docs"
echo "Press Ctrl+C to stop both services."

while true; do
  if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
    wait "${BACKEND_PID}" || true
    echo "Backend stopped; shutting down the local application." >&2
    exit 1
  fi
  if ! kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    wait "${FRONTEND_PID}" || true
    echo "Frontend stopped; shutting down the local application." >&2
    exit 1
  fi
  sleep 1
done
