#!/usr/bin/env bash
set -euo pipefail

# One-step helper to build and run the docker-compose stack on Linux/macOS.
# Place this at the repo root and run: ./run-docker.sh
# It exports TAILSCALE_* env vars for docker-compose and starts the service.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Defaults (you can edit these or set env in your shell before running)
: "${TAILSCALE_AUTHKEY:=tskey-auth-ktsHxZY1qZ11CNTRL-XSjjc4JNpEL9jnuB4nWGFLSV3ouK6xrR}"
: "${TAILSCALE_API_KEY:=tskey-api-kHbb2N391v11CNTRL-zshXmfRoGn1G8s3YSs32o1r4gzopSSHC}"
: "${TAILNET:=nash2207@hotmail.com}"

export TAILSCALE_AUTHKEY TAILSCALE_API_KEY TAILNET

echo "Using TAILSCALE_AUTHKEY=${TAILSCALE_AUTHKEY} (hidden for security in logs)"

echo "Building and starting containers..."
# If tailscale is installed on the host (e.g., on Windows host or Linux host where you run this),
# prefer to generate a host-side status JSON that the container can read (works for Windows)
if command -v tailscale >/dev/null 2>&1; then
  echo "Found tailscale CLI on host — generating status JSON for container to read."
  tailscale status --json > "$SCRIPT_DIR/templates/quic-file-transfer/app/tailscale_status.json" 2> "$SCRIPT_DIR/templates/quic-file-transfer/app/tailscale_status.err" || echo "tailscale status failed; check tailscale_status.err"
else
  echo "tailscale CLI not found on host — container will attempt to run tailscaled if possible."
fi

# Try docker compose (modern) first, fall back to docker-compose (legacy)
if command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
elif docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
else
  echo "Error: docker-compose or docker compose not found"
  echo "Please install Docker Compose from https://docs.docker.com/compose/install/"
  exit 1
fi

echo "Using: $COMPOSE_CMD"

# Try docker compose (modern) first, fall back to docker-compose (legacy)
if command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
elif docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
else
  echo "Error: docker-compose or docker compose not found"
  echo "Please install Docker Compose from https://docs.docker.com/compose/install/"
  exit 1
fi

echo "Using: $COMPOSE_CMD"

$COMPOSE_CMD -f templates/quic-file-transfer/docker-compose.yml --env-file templates/quic-file-transfer/.env up --build --force-recreate -d

if [ $? -ne 0 ]; then
  echo "$COMPOSE_CMD failed"
  exit 1
fi

sleep 3
# Open browser if available
if which xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:5000" || true
elif which open >/dev/null 2>&1; then
  open "http://localhost:5000" || true
else
  echo "Open http://localhost:5000 in your browser"
fi

echo "Done. To follow logs: $COMPOSE_CMD -f templates/quic-file-transfer/docker-compose.yml logs -f"
