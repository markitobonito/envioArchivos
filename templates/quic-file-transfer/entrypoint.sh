#!/bin/sh
set -e

# Entrypoint: El contenedor usa Tailscale del HOST (no instala su propia).
# El host genera tailscale_status.json y lo monta en ./app

STATUS_PATH=${TAILSCALE_STATUS_PATH:-/app/tailscale_status.json}

echo "════════════════════════════════════════════════════════"
echo "  CONTENEDOR QUIC: Usando Tailscale del HOST"
echo "════════════════════════════════════════════════════════"
echo ""

# Esperar a que el status.json esté disponible (generado por el host)
echo "Esperando a que Tailscale del host genere status.json..."
TIMEOUT=30
ELAPSED=0

while [ ! -f "$STATUS_PATH" ] && [ $ELAPSED -lt $TIMEOUT ]; do
  echo "  Intento $((ELAPSED/2 + 1))/$((TIMEOUT/2)): Esperando..."
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done

if [ ! -f "$STATUS_PATH" ]; then
  echo "⚠️  Timeout: status.json no disponible después de ${TIMEOUT}s"
  echo "   El host Tailscale puede no estar listo aún"
  echo "   La app intentará leerlo cuando esté disponible"
else
  echo "✅ Tailscale status.json disponible"
  echo ""
  echo "Peers detectados:"
  grep -o '"HostName":"[^"]*"' "$STATUS_PATH" | cut -d'"' -f4 | sed 's/^/   - /'
fi

# final: show status file content for debug
if [ -f "$STATUS_PATH" ]; then
  echo "--- tailscale_status.json (start) ---"
  cat "$STATUS_PATH" || true
  echo "--- tailscale_status.json (end) ---"
else
  echo "No tailscale status available inside container"
fi

# Iniciar Xvfb (virtual display) para Firefox
echo "Iniciando Xvfb (virtual display para notificaciones)..."
Xvfb :99 -screen 0 1920x1080x24 >/dev/null 2>&1 &
XVFB_PID=$!
echo "Xvfb iniciado en display :99 (PID: $XVFB_PID)"

# Exec the original command (run.py)
exec python3 /run.py
