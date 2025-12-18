#!/usr/bin/env bash
# Test script to verify QUIC File Transfer setup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== QUIC File Transfer - Diagnosis Script ==="
echo ""

# 1. Check Docker
echo "[1] Checking Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo "✓ Docker: $DOCKER_VERSION"
else
    echo "✗ Docker not found. Install it from https://www.docker.com"
    exit 1
fi

# 2. Check Docker Compose
echo ""
echo "[2] Checking Docker Compose..."
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version 2>&1 | head -1)
    echo "✓ Docker Compose (new): $COMPOSE_VERSION"
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version)
    echo "✓ Docker Compose (legacy): $COMPOSE_VERSION"
    COMPOSE_CMD="docker-compose"
else
    echo "✗ Neither 'docker compose' nor 'docker-compose' found"
    exit 1
fi

# 3. Check container status
echo ""
echo "[3] Checking container status..."
CONTAINER_ID=$(docker ps -q -f name=quic-file-transfer)
if [ -z "$CONTAINER_ID" ]; then
    echo "✗ Container not running. Run './run-docker.sh' first"
    exit 1
else
    echo "✓ Container running: $CONTAINER_ID"
fi

# 4. Check Tailscale status
echo ""
echo "[4] Checking Tailscale..."
if command -v tailscale &> /dev/null; then
    TS_STATUS=$(tailscale status 2>&1 | head -3)
    echo "✓ Tailscale CLI found:"
    echo "$TS_STATUS"
else
    echo "⚠ Tailscale CLI not found on host. Container will try to use it."
fi

# 5. Check if container can see tailscale_status.json
echo ""
echo "[5] Checking tailscale_status.json in container..."
if docker exec "$CONTAINER_ID" test -f /app/tailscale_status.json; then
    PEER_COUNT=$(docker exec "$CONTAINER_ID" jq '.Peer | length' /app/tailscale_status.json 2>/dev/null || echo "?")
    SELF_IPS=$(docker exec "$CONTAINER_ID" jq '.Self.TailscaleIPs[0]' /app/tailscale_status.json 2>/dev/null || echo "?")
    echo "✓ Status file found. Peers detected: $PEER_COUNT, Self IP: $SELF_IPS"
else
    echo "✗ tailscale_status.json not found in container"
fi

# 6. Check Flask endpoint
echo ""
echo "[6] Checking Flask Web UI (port 5000)..."
if curl -s http://localhost:5000 > /dev/null 2>&1; then
    echo "✓ Flask web server responding on http://localhost:5000"
else
    echo "⚠ Flask not responding on port 5000. Check logs: docker logs $CONTAINER_ID"
fi

# 7. Check QUIC port (UDP 9999)
echo ""
echo "[7] Checking QUIC port (UDP 9999)..."
if docker exec "$CONTAINER_ID" netstat -tuln 2>/dev/null | grep -q 9999 || \
   docker exec "$CONTAINER_ID" ss -tuln 2>/dev/null | grep -q 9999; then
    echo "✓ QUIC server listening on port 9999 (UDP)"
else
    echo "⚠ QUIC port 9999 not showing in netstat. Might still be listening."
fi

# 8. Show recent logs
echo ""
echo "[8] Recent container logs (last 10 lines):"
docker logs --tail 10 "$CONTAINER_ID" | sed 's/^/  /'

echo ""
echo "=== Diagnosis Complete ==="
echo ""
echo "If all checks pass, you can:"
echo "  1. Open http://localhost:5000 in your browser"
echo "  2. Upload a file to send it to all online Tailscale peers"
echo "  3. Received files will appear in ~/Downloads on remote machines"
echo ""
echo "For more info, see: README-DEPLOYMENT.md"
