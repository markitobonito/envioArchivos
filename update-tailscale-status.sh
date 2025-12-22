#!/bin/bash
# Script para mantener tailscale_status.json actualizado cada 5 segundos

STATUS_FILE="/Users/markito/Documents/prr/envioArchivos/templates/quic-file-transfer/app/tailscale_status.json"

echo "🔄 Actualizando Tailscale status cada 5 segundos..."
echo "   (Ejecuta esto en una terminal mientras usas la app)"
echo ""

while true; do
    tailscale status --json > "$STATUS_FILE" 2>/dev/null
    sleep 5
done
