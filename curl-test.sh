#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
TIMEOUT_SEC="${TIMEOUT_SEC:-20}"
CHECK_TDA_TOOLS="${CHECK_TDA_TOOLS:-false}"

pass() { echo "[PASS] $1"; }
fail() { echo "[FAIL] $1"; exit 1; }

check_get_200() {
  local path="$1"
  local label="$2"

  local tmp_body
  tmp_body="$(mktemp)"
  local code
  code="$(curl -sS --max-time "$TIMEOUT_SEC" -o "$tmp_body" -w "%{http_code}" "$BASE_URL$path" || true)"

  if [[ "$code" == "200" ]]; then
    pass "$label ($path)"
  else
    echo "Response body:"
    cat "$tmp_body" || true
    rm -f "$tmp_body"
    fail "$label expected HTTP 200, got $code"
  fi

  rm -f "$tmp_body"
}

echo "Running curl smoke tests against: $BASE_URL"

check_get_200 "/v1/health" "Health endpoint"
check_get_200 "/openapi.json" "OpenAPI endpoint"

if [[ "${CHECK_TDA_TOOLS,,}" == "true" ]]; then
  check_get_200 "/v1/tda/mcp/tools" "TDA MCP tools endpoint"
else
  echo "[SKIP] TDA tools check (set CHECK_TDA_TOOLS=true to enable)"
fi

echo "All smoke tests passed."
