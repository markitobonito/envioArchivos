#!/bin/bash
# Script para probar notificaciones de forma interactiva

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

clear

echo -e "${BLUE}════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}     PRUEBA INTERACTIVA DE NOTIFICACIONES QUIC FILE TRANSFER${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════════════${NC}"
echo ""

# Verificaciones previas
echo -e "${YELLOW}[*] Verificaciones previas...${NC}"
echo ""

# Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker no instalado${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker OK${NC}"

# Container
CONTAINER=$(docker ps --filter "name=quic-file-transfer" -q 2>/dev/null | head -1)
if [ -z "$CONTAINER" ]; then
    echo -e "${RED}❌ Contenedor no encontrado${NC}"
    echo -e "${YELLOW}    Ejecuta: ./run-docker.sh${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Contenedor OK${NC}"

# Status JSON
if [ ! -f "templates/quic-file-transfer/app/tailscale_status.json" ]; then
    echo -e "${RED}❌ Status JSON no encontrado${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Tailscale Status OK${NC}"

# Extraer IP del peer
PEER_IP=$(jq -r '.Peer | to_entries[0].value.TailscaleIPs[0]' "templates/quic-file-transfer/app/tailscale_status.json" 2>/dev/null)
PEER_NAME=$(jq -r '.Peer | to_entries[0].value.HostName' "templates/quic-file-transfer/app/tailscale_status.json" 2>/dev/null)

if [ -z "$PEER_IP" ]; then
    echo -e "${RED}❌ No se pudo obtener IP del peer${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Peer OK${NC}"
echo ""

# Mostrar información
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "  ${CYAN}Peer encontrado:${NC} ${PEER_NAME}"
echo -e "  ${CYAN}IP:${NC} ${PEER_IP}"
echo -e "  ${CYAN}URL:${NC} http://${PEER_IP}:5000"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""

# Menu
show_menu() {
    echo -e "${CYAN}Selecciona una opción:${NC}"
    echo ""
    echo "  ${YELLOW}1${NC}) Enviar notificación simple"
    echo "  ${YELLOW}2${NC}) Enviar notificación con emoji"
    echo "  ${YELLOW}3${NC}) Test de carga (10 notificaciones)"
    echo "  ${YELLOW}4${NC}) Abrir monitor en receptor"
    echo "  ${YELLOW}5${NC}) Ver logs del contenedor"
    echo "  ${YELLOW}6${NC}) Ejecutar diagnóstico completo"
    echo "  ${YELLOW}0${NC}) Salir"
    echo ""
    read -p "Opción: " option
}

send_notification() {
    local message=$1
    
    echo ""
    echo -e "${BLUE}► Enviando: \"${message}\"${NC}"
    
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "http://${PEER_IP}:5000/receive-notification" \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"$message\"}" \
        --connect-timeout 5)
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | head -n-1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Enviado (HTTP 200)${NC}"
        
        # Esperar un poco
        sleep 0.5
        
        # Verificar archivo
        CONTENT=$(docker exec "$CONTAINER" cat /tmp/notification.txt 2>/dev/null)
        if [ ! -z "$CONTENT" ]; then
            echo -e "${GREEN}✅ Archivo creado: /tmp/notification.txt${NC}"
            echo "   Contenido: $CONTENT"
        else
            echo -e "${YELLOW}⚠️  Archivo no accesible vía Docker${NC}"
        fi
    else
        echo -e "${RED}❌ Error HTTP ${HTTP_CODE}${NC}"
        echo "   Respuesta: $BODY"
    fi
    
    echo ""
}

# Loop principal
while true; do
    show_menu
    
    case $option in
        1)
            read -p "Escribe el mensaje: " message
            if [ ! -z "$message" ]; then
                send_notification "$message"
            else
                echo -e "${RED}Mensaje vacío${NC}"
            fi
            ;;
        2)
            messages=(
                "🚨 ALERTA CRÍTICA - Sistema comprometido"
                "⚠️ ADVERTENCIA - Recursos bajos"
                "🔔 NOTIFICACIÓN - Proceso completado"
                "✅ ÉXITO - Operación exitosa"
                "❌ ERROR - Falló la operación"
            )
            echo -e "${YELLOW}Selecciona emoji:${NC}"
            for i in "${!messages[@]}"; do
                echo "  $((i+1))) ${messages[$i]}"
            done
            read -p "Opción (1-${#messages[@]}): " emoji_option
            if [ "$emoji_option" -ge 1 ] && [ "$emoji_option" -le "${#messages[@]}" ]; then
                send_notification "${messages[$((emoji_option-1))]}"
            else
                echo -e "${RED}Opción inválida${NC}"
            fi
            ;;
        3)
            echo -e "${BLUE}► Enviando 10 notificaciones de prueba...${NC}"
            for i in {1..10}; do
                send_notification "🧪 Notificación de test #$i - $(date '+%H:%M:%S')"
                sleep 0.3
            done
            ;;
        4)
            echo -e "${BLUE}► Abriendo monitor en receptor...${NC}"
            echo -e "${CYAN}Presiona Ctrl+C para salir del monitor${NC}"
            echo ""
            docker exec -it "$CONTAINER" python3 /app/notification-monitor-advanced.py
            ;;
        5)
            echo -e "${BLUE}► Logs del contenedor (últimas 20 líneas):${NC}"
            echo ""
            docker logs "$CONTAINER" 2>/dev/null | tail -20
            echo ""
            ;;
        6)
            echo -e "${BLUE}► Ejecutando diagnóstico...${NC}"
            ./notification-diagnostic.sh
            ;;
        0)
            echo -e "${GREEN}✅ Adiós!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Opción inválida${NC}"
            ;;
    esac
done
