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
echo "🔐 CONFIGURACIÓN DE TAILSCALE (HOST)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Detectar SO del HOST
OS_TYPE=$(uname -s)
echo "Sistema detectado: $OS_TYPE"

# Si es Linux, instalar pico2wave (libttspico-utils) y espeak-ng
if [ "$OS_TYPE" = "Linux" ]; then
    echo ""
    echo "Instalando motores TTS para Linux..."
    
    # Detectar distro
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
    else
        DISTRO="unknown"
    fi
    
    # 1. INSTALAR PICO2WAVE PRIMERO (libttspico-utils) - PRIORITARIO
    if ! command -v pico2wave >/dev/null 2>&1; then
        echo "⚠️  pico2wave no instalado. Instalando libttspico-utils..."
        
        case "$DISTRO" in
            ubuntu|debian)
                sudo apt-get update -qq
                sudo apt-get install -y libttspico-utils
                ;;
            fedora)
                sudo dnf install -y libttspico-utils
                ;;
            rhel|centos)
                sudo yum install -y libttspico-utils
                ;;
            arch)
                sudo pacman -S --noconfirm libttspico
                ;;
            opensuse*)
                sudo zypper install -y libttspico-utils
                ;;
            *)
                echo "⚠️  Distro desconocida: $DISTRO, se saltará pico2wave"
                ;;
        esac
        
        if command -v pico2wave >/dev/null 2>&1; then
            echo "✅ pico2wave (libttspico-utils) instalado"
        else
            echo "⚠️  pico2wave no disponible, se usará espeak-ng como fallback"
        fi
    else
        echo "✅ pico2wave ya está instalado"
    fi
    
    # 2. INSTALAR LIBNOTIFY-BIN (para notify-send)
    if ! command -v notify-send >/dev/null 2>&1; then
        echo "⚠️  libnotify-bin no instalado. Instalando..."
        
        case "$DISTRO" in
            ubuntu|debian)
                sudo apt-get update -qq
                sudo apt-get install -y libnotify-bin
                ;;
            fedora)
                sudo dnf install -y libnotify
                ;;
            rhel|centos)
                sudo yum install -y libnotify
                ;;
            arch)
                sudo pacman -S --noconfirm libnotify
                ;;
            opensuse*)
                sudo zypper install -y libnotify
                ;;
            *)
                echo "⚠️  No se pudo instalar libnotify-bin"
                ;;
        esac
        
        if command -v notify-send >/dev/null 2>&1; then
            echo "✅ libnotify-bin instalado"
        else
            echo "⚠️  No se pudo instalar libnotify-bin, continuando..."
        fi
    else
        echo "✅ libnotify-bin ya está instalado"
    fi
    
    # 3. INSTALAR ESPEAK-NG (fallback para pico2wave)
    if ! command -v espeak-ng >/dev/null 2>&1; then
        echo "⚠️  espeak-ng no instalado. Instalando..."
        
        case "$DISTRO" in
            ubuntu|debian)
                sudo apt-get update -qq
                sudo apt-get install -y espeak-ng
                ;;
            fedora)
                sudo dnf install -y espeak-ng
                ;;
            rhel|centos)
                sudo yum install -y espeak-ng
                ;;
            arch)
                sudo pacman -S --noconfirm espeak-ng
                ;;
            opensuse*)
                sudo zypper install -y espeak-ng
                ;;
            *)
                echo "⚠️  No se pudo instalar espeak-ng"
                ;;
        esac
        
        if command -v espeak-ng >/dev/null 2>&1; then
            echo "✅ espeak-ng instalado"
        else
            echo "⚠️  No se pudo instalar espeak-ng, continuando..."
        fi
    else
        echo "✅ espeak-ng ya está instalado"
    fi
fi

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
  if sudo tailscale up --authkey="$TAILSCALE_AUTHKEY" --accept-routes --accept-dns 2>&1; then
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

# Esperar a que Tailscale sincronice todos los peers
echo ""
echo "Esperando a que Tailscale sincronice con todos los peers..."
TIMEOUT=45
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
  STATUS_JSON=$(tailscale status --json 2>/dev/null)
  
  # Verificar si hay peers en el JSON
  if echo "$STATUS_JSON" | grep -q '"Peer".*{'; then
    PEER_COUNT=$(echo "$STATUS_JSON" | grep -o '"HostName"' | wc -l)
    echo "✅ Peers detectados: $PEER_COUNT"
    break
  fi
  
  ATTEMPT=$((ELAPSED / 3 + 1))
  TOTAL_ATTEMPTS=$((TIMEOUT / 3 + 1))
  echo "  ⏳ Intento $ATTEMPT/$TOTAL_ATTEMPTS: Esperando sincronización de peers..."
  sleep 3
  ELAPSED=$((ELAPSED + 3))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
  echo "⚠️  Timeout esperando peers, pero continuamos..."
fi

# Generar status JSON desde el host (para que el contenedor lo lea)
echo ""
echo "Generando tailscale_status.json desde host..."
tailscale status --json > "$SCRIPT_DIR/templates/quic-file-transfer/app/tailscale_status.json" 2>/dev/null || true
echo "✅ Status generado"

# Iniciar el servicio de API de Tailscale en background
echo ""
echo "Iniciando servicio de API de Tailscale (puerto 5001)..."

# Matar proceso viejo si existe
pkill -f "tailscale-api.py" 2>/dev/null || true
sleep 1

# Iniciar nuevo proceso
python3 "$SCRIPT_DIR/tailscale-api.py" > /tmp/tailscale-api.log 2>&1 &
TAILSCALE_API_PID=$!
echo "✅ Servicio iniciado (PID: $TAILSCALE_API_PID)"
sleep 1  # Dar tiempo a que inicie

# Iniciar el monitor de alertas .msg
echo ""
echo "Iniciando monitor de alertas .msg..."

# Matar proceso viejo del monitor si existe
pkill -f "msg-monitor.py" 2>/dev/null || true
sleep 1

# Iniciar nuevo monitor
python3 "$SCRIPT_DIR/msg-monitor.py" > /tmp/msg-monitor.log 2>&1 &
MSG_MONITOR_PID=$!
echo "✅ Monitor .msg iniciado (PID: $MSG_MONITOR_PID)"
sleep 1  # Dar tiempo a que inicie

# Iniciar el monitor de videos
echo ""
echo "Iniciando monitor de videos..."

# Matar proceso viejo del monitor de videos si existe
pkill -f "video-monitor.py" 2>/dev/null || true
sleep 1

# Iniciar nuevo monitor de videos
python3 "$SCRIPT_DIR/video-monitor.py" > /tmp/video-monitor.log 2>&1 &
VIDEO_MONITOR_PID=$!
echo "✅ Monitor de videos iniciado (PID: $VIDEO_MONITOR_PID)"
sleep 1  # Dar tiempo a que inicie

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
