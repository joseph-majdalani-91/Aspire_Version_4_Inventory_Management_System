#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8765}"
HOST="${HOST:-127.0.0.1}"

if [[ -z "${AUTH_PASSWORD_PEPPER:-}" ]]; then
  if [[ -f ".env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi
fi

if [[ -z "${AUTH_PASSWORD_PEPPER:-}" ]]; then
  echo "AUTH_PASSWORD_PEPPER is required."
  echo "Example: cp .env.example .env && export AUTH_PASSWORD_PEPPER='local-dev-pepper'"
  exit 1
fi

echo "Starting app on http://${HOST}:${PORT} ..."
uvicorn app.main:app --host "${HOST}" --port "${PORT}" >/tmp/ims_public_uvicorn.log 2>&1 &
UVICORN_PID=$!

cleanup() {
  kill "${UVICORN_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

sleep 2

echo "Creating public tunnel (free, temporary URL)..."
npx localtunnel --port "${PORT}"
