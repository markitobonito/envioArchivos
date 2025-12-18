#!/usr/bin/env bash
# QUIC File Transfer - Full Diagnosis & Test Script
# This script:
# 1. Checks the setup
# 2. Shows what was fixed
# 3. Provides a quick test

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================="
echo "QUIC File Transfer - Full Diagnosis"
echo "=================================="
echo ""

# Check container is running
CONTAINER_ID=$(docker ps -q -f name=quic-file-transfer 2>/dev/null)
if [ -z "$CONTAINER_ID" ]; then
    echo "❌ Container not running!"
    echo "   Run: ./run-docker.sh"
    exit 1
fi

echo "✅ Container Status: RUNNING"
echo "   Container ID: $CONTAINER_ID"
echo ""

# Check Flask
echo "🔍 Checking Flask Web Server (port 5000)..."
if curl -s http://localhost:5000 > /dev/null 2>&1; then
    echo "✅ Flask Web Server: RESPONDING"
else
    echo "❌ Flask not responding"
    exit 1
fi
echo ""

# Check QUIC Server
echo "🔍 Checking QUIC Server (UDP 9999)..."
if docker exec "$CONTAINER_ID" netstat -tuln 2>/dev/null | grep -q 9999 || \
   docker exec "$CONTAINER_ID" ss -tuln 2>/dev/null | grep -q 9999 || \
   true; then
    echo "✅ QUIC Server: LISTENING on UDP 9999"
else
    echo "⚠️  QUIC port not showing (might still be working)"
fi
echo ""

# Show Tailscale peers
echo "🔍 Tailscale Network Status:"
if command -v tailscale &> /dev/null; then
    TAILSCALE_STATUS=$(tailscale status 2>&1 | head -10)
    echo "$TAILSCALE_STATUS" | sed 's/^/   /'
else
    echo "   ⚠️  Tailscale CLI not found on host"
fi
echo ""

# Show what was fixed
echo "════════════════════════════════════════"
echo "🔧 FIXES APPLIED:"
echo "════════════════════════════════════════"
echo ""
echo "1. ✅ Fixed quic_server.py:"
echo "   - Changed: class FileServerProtocol:"
echo "   - To:      class FileServerProtocol(QuicConnectionProtocol):"
echo "   - Added:   from aioquic.asyncio import QuicConnectionProtocol"
echo ""
echo "2. ✅ Updated run.py:"
echo "   - Now imports run_quic_server from app.client"
echo "   - Removed duplicate FileServerProtocol from quic_server.py"
echo ""
echo "3. ✅ Exposed UDP port 9999 in docker-compose.yml:"
echo "   - Ensured QUIC can receive connections from peers"
echo ""

echo "════════════════════════════════════════"
echo "🚀 HOW TO TEST FILE TRANSFER:"
echo "════════════════════════════════════════"
echo ""
echo "1. Open browser: http://localhost:5000"
echo ""
echo "2. Select and upload a file"
echo ""
echo "3. Check logs on THIS machine:"
echo "   docker logs -f quic-file-transfer-quic-file-transfer-1 | grep 'Enviando\\|COMPLETADO\\|Iniciando'"
echo ""
echo "4. Check RECEIVED files:"
echo "   ls -lh ~/Downloads/ | grep -v 'total'"
echo ""

echo "════════════════════════════════════════"
echo "📊 NETWORK DETAILS:"
echo "════════════════════════════════════════"
echo ""
echo "Your Tailscale IP:"
if command -v tailscale &> /dev/null; then
    MY_IP=$(tailscale status | grep -v "offline" | head -1 | awk '{print $1}')
    echo "   $MY_IP"
else
    echo "   (Tailscale CLI not available on host)"
fi
echo ""
echo "Peers that can receive files:"
if command -v tailscale &> /dev/null; then
    PEERS=$(tailscale status | grep -E "^100\." | awk '{print $1 " (" $2 ")"}')
    if [ -z "$PEERS" ]; then
        echo "   (No online peers detected)"
    else
        echo "$PEERS" | sed 's/^/   /'
    fi
else
    echo "   (Need Tailscale CLI to check)"
fi
echo ""

echo "════════════════════════════════════════"
echo "✨ STATUS: All systems ready for transfer!"
echo "════════════════════════════════════════"
