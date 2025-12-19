#!/usr/bin/env bash
set -euo pipefail

# One-step helper to build and run the docker-compose stack on Linux/macOS.
# Place this at the repo root and run: ./run-docker.sh
# It exports TAILSCALE_* env vars for docker-compose and starts the service.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detectar la carpeta de descargas correcta (Descargas o Downloads según idioma)
# Primero intentar Descargas (español)
if [ -d "$HOME/Descargas" ]; then
    export DOWNLOADS_PATH="$HOME/Descargas"
    echo "✓ Carpeta de descargas detectada: $DOWNLOADS_PATH"
# Luego intentar Downloads (inglés)
elif [ -d "$HOME/Downloads" ]; then
    export DOWNLOADS_PATH="$HOME/Downloads"
    echo "✓ Usando carpeta de descargas: $DOWNLOADS_PATH"
# Si no existe ninguna, crear Downloads por defecto
else
    export DOWNLOADS_PATH="$HOME/Downloads"
    mkdir -p "$DOWNLOADS_PATH"
    echo "✓ Carpeta de descargas creada: $DOWNLOADS_PATH"
fi

# Validar que la ruta sea válida
if [ -z "$DOWNLOADS_PATH" ] || [ ! -d "$DOWNLOADS_PATH" ]; then
    echo "❌ Error: No se pudo establecer DOWNLOADS_PATH"
    echo "HOME=$HOME"
    exit 1
fi

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

# Try docker compose (modern/bundled) first, fall back to docker-compose (legacy)
# Modern docker compose has fewer bugs with new Docker versions
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  echo "⚠️  Using legacy docker-compose. Consider upgrading to modern 'docker compose' (bundled with Docker)"
  COMPOSE_CMD="docker-compose"
else
  echo "Error: neither 'docker compose' nor 'docker-compose' found"
  echo "Please install Docker Compose from https://docs.docker.com/compose/install/"
  exit 1
fi

echo "Using: $COMPOSE_CMD"

export DOWNLOADS_PATH  # Asegurar que la variable se exporte para docker-compose

$COMPOSE_CMD -f templates/quic-file-transfer/docker-compose.yml --env-file templates/quic-file-transfer/.env up --build --force-recreate -d

if [ $? -ne 0 ]; then
  echo "$COMPOSE_CMD failed"
  exit 1
fi

echo "✓ Containers started successfully"
echo "Opening http://localhost:5000 in browser..."
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open http://localhost:5000 &
elif command -v open >/dev/null 2>&1; then
  open http://localhost:5000 &
fi

# Iniciar el monitor de videos automático en background
echo ""
echo "🎬 Iniciando monitor de videos automático..."
chmod +x "$SCRIPT_DIR/video-monitor.py"
python3 "$SCRIPT_DIR/video-monitor.py" > /tmp/video-monitor.log 2>&1 &
MONITOR_PID=$!
echo "✓ Monitor de videos activo (PID: $MONITOR_PID)"
echo "  - Reproducir Ahora: abre inmediatamente"
echo "  - Programar: abre solo a la hora exacta"
echo "  - Solo Descargar: sin reproducción automática"
echo ""

# Iniciar el monitor de notificaciones automático en background
echo "📢 Iniciando monitor de notificaciones..."
chmod +x "$SCRIPT_DIR/templates/quic-file-transfer/app/notification-monitor.py"
python3 "$SCRIPT_DIR/templates/quic-file-transfer/app/notification-monitor.py" > /tmp/notification-monitor.log 2>&1 &
NOTIFICATION_MONITOR_PID=$!
echo "✓ Monitor de notificaciones activo (PID: $NOTIFICATION_MONITOR_PID)"
echo ""

echo "✅ Sistema listo. Abre http://localhost:5000 para enviar videos y alertas"

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
