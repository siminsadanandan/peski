#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-peski:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-peski-app}"
HOST_PORT="${HOST_PORT:-8080}"
CONTAINER_PORT="${CONTAINER_PORT:-8080}"
HOST_RESULTS_DIR="${HOST_RESULTS_DIR:-./results}"
CONTAINER_RESULTS_DIR="${CONTAINER_RESULTS_DIR:-/var/log/threaddumps}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p "$HOST_RESULTS_DIR"

ENV_ARGS=()
if [[ -f ".env" ]]; then
  ENV_ARGS=(--env-file .env)
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

echo "Building image: $IMAGE_NAME"
docker build -t "$IMAGE_NAME" .

echo "Running container: $CONTAINER_NAME"
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "$HOST_PORT:$CONTAINER_PORT" \
  -v "$SCRIPT_DIR/$HOST_RESULTS_DIR:$CONTAINER_RESULTS_DIR" \
  "${ENV_ARGS[@]}" \
  "$IMAGE_NAME"

echo "Container started."
echo "- URL: http://localhost:$HOST_PORT/v1/health"
echo "- Host results dir: $SCRIPT_DIR/$HOST_RESULTS_DIR"
echo "- Container results dir: $CONTAINER_RESULTS_DIR"
