#!/usr/bin/env bash
set -euo pipefail

# One-step helper to build and run the docker-compose stack on macOS.
# Installs Tailscale on the host (not in Docker) and connects via authkey.
# The host's Tailscale daemon is then mounted into Docker for the app to use.

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

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 CONFIGURACIÓN DE TAILSCALE (HOST macOS)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1) Verificar si Tailscale está instalado en el host
if ! command -v tailscale >/dev/null 2>&1; then
  echo "❌ Tailscale no está instalado en macOS"
  echo ""
  echo "Instalando Tailscale..."
  if command -v brew >/dev/null 2>&1; then
    echo "   (usando Homebrew)"
    brew install tailscale
  else
    echo "   (descargando instalador oficial)"
    curl -fsSL https://tailscale.com/install.sh | sh
  fi
  
  if ! command -v tailscale >/dev/null 2>&1; then
    echo "❌ Error: No se pudo instalar Tailscale"
    exit 1
  fi
  echo "✅ Tailscale instalado"
else
  echo "✅ Tailscale ya está instalado"
fi

# 2) Verificar si ya estamos conectados a Tailscale
echo ""
echo "Verificando conexión a Tailscale..."
TAILSCALE_STATUS=$(tailscale status 2>&1 || echo "")

if echo "$TAILSCALE_STATUS" | grep -q "Online"; then
  echo "✅ Tailscale ya está conectado"
  HOST_TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1)
  echo "   IP Tailscale del host: $HOST_TAILSCALE_IP"
else
  echo "⚠️  Tailscale no conectado. Conectando con authkey..."
  
  # Intentar conectar
  if sudo tailscale up --authkey="$TAILSCALE_AUTHKEY" --accept-routes --accept-dns 2>&1; then
    echo "✅ Tailscale conectado exitosamente"
    sleep 2
    HOST_TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1)
    echo "   IP Tailscale del host: $HOST_TAILSCALE_IP"
  else
    echo "❌ Error: No se pudo conectar a Tailscale"
    echo "   Verifica tu TAILSCALE_AUTHKEY"
    exit 1
  fi
fi

# Guardar la IP para pasar al contenedor
export HOST_TAILSCALE_IP

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐳 INICIANDO DOCKER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Generar status JSON desde el host (para que el contenedor lo lea)
echo ""
echo "Generando tailscale_status.json desde host..."
tailscale status --json > "$SCRIPT_DIR/templates/quic-file-transfer/app/tailscale_status.json" 2>/dev/null || true
echo "✅ Status generado"

# Try docker compose (modern/bundled) first, fall back to docker-compose (legacy)
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  echo "⚠️  Usando docker-compose antiguo"
  COMPOSE_CMD="docker-compose"
else
  echo "❌ Error: ni 'docker compose' ni 'docker-compose' encontrados"
  echo "Instala Docker Compose desde https://docs.docker.com/compose/install/"
  exit 1
fi

echo "Usando: $COMPOSE_CMD"

export DOWNLOADS_PATH HOST_TAILSCALE_IP

echo ""
echo "Iniciando contenedores Docker..."
$COMPOSE_CMD -f templates/quic-file-transfer/docker-compose.yml up --build -d

if [ $? -ne 0 ]; then
  echo "❌ Error: docker compose falló"
  exit 1
fi

echo ""
echo "✅ Contenedores iniciados exitosamente"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 SISTEMA LISTO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 Host Tailscale IP: $HOST_TAILSCALE_IP"
echo "🌐 Acceso local:      http://localhost:8080"
echo "📊 Logs:              docker compose -f templates/quic-file-transfer/docker-compose.yml logs -f"
echo ""

# Abrir navegador
if command -v open >/dev/null 2>&1; then
  echo "Abriendo navegador..."
  open "http://localhost:8080" || true
fi

echo "✅ Listo para enviar archivos a través de Tailscale"
