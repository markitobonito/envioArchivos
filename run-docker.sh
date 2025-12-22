#!/usr/bin/env bash
set -euo pipefail

# One-step helper to build and run the docker-compose stack on macOS.
# Installs Tailscale on the host (not in Docker) and connects via authkey.
# The host's Tailscale daemon is then mounted into Docker for the app to use.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Cargar variables desde .env si existen
if [ -f "$SCRIPT_DIR/templates/quic-file-transfer/.env" ]; then
  set -a
  source "$SCRIPT_DIR/templates/quic-file-transfer/.env"
  set +a
fi

# Fallback a defaults si no están definidas en .env
: "${TAILSCALE_AUTHKEY:=}"
: "${TAILSCALE_API_KEY:=}"
: "${TAILNET:=}"

# Validar que tenemos las credenciales
if [ -z "$TAILSCALE_AUTHKEY" ]; then
  echo "❌ Error: TAILSCALE_AUTHKEY no está definida"
  echo "   Edita $SCRIPT_DIR/templates/quic-file-transfer/.env"
  exit 1
fi

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

# 2) Verificar si el daemon tailscaled está corriendo
echo ""
echo "Verificando si el daemon Tailscale está corriendo..."

if ! pgrep -x "tailscaled" >/dev/null 2>&1; then
  echo "⚠️  El daemon tailscaled no está corriendo"
  echo "   Iniciando Tailscale como servicio..."
  
  # Usar brew services para iniciar como servicio de fondo
  if command -v brew >/dev/null 2>&1; then
    # Primero, asegúrate de que Homebrew pueda instalar sin pedir contraseña
    sudo brew services start tailscale 2>/dev/null || {
      echo "⚠️  brew services requiere contraseña..."
      sudo -n true 2>/dev/null || {
        echo "Por favor, ingresa tu contraseña para iniciar Tailscale:"
        sudo brew services start tailscale
      }
    }
  else
    echo "❌ Homebrew no encontrado para iniciar el servicio"
    exit 1
  fi
  
  # Esperar a que el daemon esté listo
  echo "   Esperando a que tailscaled inicie..."
  TIMEOUT=15
  ELAPSED=0
  while ! pgrep -x "tailscaled" >/dev/null 2>&1 && [ $ELAPSED -lt $TIMEOUT ]; do
    sleep 1
    ELAPSED=$((ELAPSED + 1))
  done
  
  if ! pgrep -x "tailscaled" >/dev/null 2>&1; then
    echo "❌ Error: tailscaled no inició después de ${TIMEOUT}s"
    exit 1
  fi
  echo "✅ tailscaled iniciado correctamente"
else
  echo "✅ tailscaled ya está corriendo"
fi

# 3) Verificar si ya estamos conectados a Tailscale
echo ""
echo "Verificando conexión a Tailscale..."
TAILSCALE_STATUS=$(tailscale status 2>&1 || echo "")

if echo "$TAILSCALE_STATUS" | grep -q "Online"; then
  echo "✅ Tailscale ya está conectado"
  HOST_TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1)
  echo "   IP Tailscale del host: $HOST_TAILSCALE_IP"
else
  echo "⚠️  Tailscale no conectado. Conectando con authkey..."
  
  # Intentar conectar (sin usar sudo porque el daemon ya corre)
  if tailscale up --authkey="$TAILSCALE_AUTHKEY" --accept-routes --accept-dns 2>&1; then
    echo "✅ Tailscale conectado exitosamente"
    sleep 2
    HOST_TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1)
    echo "   IP Tailscale del host: $HOST_TAILSCALE_IP"
  else
    echo "❌ Error: No se pudo conectar a Tailscale"
    echo "   Verifica que tu TAILSCALE_AUTHKEY sea válido"
    echo ""
    echo "   Para debugging:"
    echo "   - tailscale status"
    echo "   - tailscale logs"
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
