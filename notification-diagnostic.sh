#!/bin/bash
# Diagnóstico completo del sistema de notificaciones

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   DIAGNÓSTICO SISTEMA DE NOTIFICACIONES QUIC${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════════════${NC}"
echo ""

# Función para verificar servicio
check_service() {
    local name=$1
    local cmd=$2
    
    echo -ne "${CYAN}[*]${NC} Verificando ${name}... "
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FALLO${NC}"
        return 1
    fi
}

# 1. Verificar Docker
echo -e "${YELLOW}1️⃣  VERIFICACIÓN DE DOCKER${NC}"
echo "─────────────────────────────────────────"
check_service "Docker" "docker --version" || true

# Contenedor corriendo?
echo -ne "${CYAN}[*]${NC} Contenedor quic-file-transfer... "
CONTAINER=$(docker ps --filter "name=quic-file-transfer" -q 2>/dev/null | head -1)
if [ ! -z "$CONTAINER" ]; then
    echo -e "${GREEN}✅ CORRIENDO (ID: ${CONTAINER:0:12})${NC}"
else
    echo -e "${RED}❌ NO ENCONTRADO${NC}"
    echo -e "${YELLOW}    ⚠️ Ejecuta: ./run-docker.sh${NC}"
fi
echo ""

# 2. Verificar Tailscale
echo -e "${YELLOW}2️⃣  VERIFICACIÓN DE TAILSCALE${NC}"
echo "─────────────────────────────────────────"

STATUS_FILE="templates/quic-file-transfer/app/tailscale_status.json"
if [ -f "$STATUS_FILE" ]; then
    echo -e "${GREEN}✅ Status JSON encontrado${NC}"
    
    # Extraer información
    HOST_IP=$(jq -r '.Self.TailscaleIPs[0]' "$STATUS_FILE" 2>/dev/null)
    PEER_IP=$(jq -r '.Peer | to_entries[0].value.TailscaleIPs[0]' "$STATUS_FILE" 2>/dev/null)
    PEER_NAME=$(jq -r '.Peer | to_entries[0].value.HostName' "$STATUS_FILE" 2>/dev/null)
    
    echo -e "   ${CYAN}Host IP:${NC} ${HOST_IP}"
    echo -e "   ${CYAN}Peer:${NC} ${PEER_NAME} (${PEER_IP})"
else
    echo -e "${RED}❌ Status JSON no encontrado${NC}"
fi
echo ""

# 3. Verificar conectividad
echo -e "${YELLOW}3️⃣  VERIFICACIÓN DE CONECTIVIDAD${NC}"
echo "─────────────────────────────────────────"

if [ ! -z "$PEER_IP" ]; then
    echo -ne "${CYAN}[*]${NC} Ping a ${PEER_IP}... "
    if ping -c 1 -W 2 "$PEER_IP" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Alcanzable${NC}"
    else
        echo -e "${RED}❌ No responde${NC}"
    fi
    
    echo -ne "${CYAN}[*]${NC} HTTP a http://${PEER_IP}:5000... "
    if curl -s -m 2 "http://${PEER_IP}:5000/" > /dev/null; then
        echo -e "${GREEN}✅ Accesible${NC}"
    else
        echo -e "${RED}❌ No accesible${NC}"
    fi
fi
echo ""

# 4. Verificación interna del contenedor
echo -e "${YELLOW}4️⃣  VERIFICACIÓN INTERNA DEL CONTENEDOR${NC}"
echo "─────────────────────────────────────────"

if [ ! -z "$CONTAINER" ]; then
    # Puerto QUIC escuchando
    echo -ne "${CYAN}[*]${NC} Puerto QUIC 9999... "
    if docker exec "$CONTAINER" sh -c 'netstat -tlnup 2>/dev/null | grep 9999' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Escuchando${NC}"
    else
        echo -e "${YELLOW}⚠️  Verificando con ss...${NC}"
        docker exec "$CONTAINER" ss -tlnup 2>/dev/null | grep 9999 || echo "No escucha"
    fi
    
    # Puerto Flask escuchando
    echo -ne "${CYAN}[*]${NC} Puerto Flask 5000... "
    if docker exec "$CONTAINER" ss -tlnup 2>/dev/null | grep -q 5000; then
        echo -e "${GREEN}✅ Escuchando${NC}"
    else
        echo -e "${RED}❌ No escucha${NC}"
    fi
    
    # Archivo status.json
    echo -ne "${CYAN}[*]${NC} Status JSON en contenedor... "
    if docker exec "$CONTAINER" ls -l /app/tailscale_status.json > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Presente${NC}"
    else
        echo -e "${RED}❌ No encontrado${NC}"
    fi
fi
echo ""

# 5. Test de notificación
echo -e "${YELLOW}5️⃣  TEST DE ENVÍO DE NOTIFICACIÓN${NC}"
echo "─────────────────────────────────────────"

if [ ! -z "$PEER_IP" ]; then
    TEST_MESSAGE="🚨 TEST NOTIFICACIÓN - $(date '+%H:%M:%S')"
    echo -e "${CYAN}[*]${NC} Mensaje: ${TEST_MESSAGE}"
    echo ""
    
    echo -e "${CYAN}[*]${NC} Enviando POST a http://${PEER_IP}:5000/receive-notification..."
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "http://${PEER_IP}:5000/receive-notification" \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"$TEST_MESSAGE\"}")
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | head -n-1)
    
    echo "   HTTP Code: ${HTTP_CODE}"
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "   ${GREEN}✅ Enviado correctamente${NC}"
        echo "   Respuesta: $(echo "$BODY" | jq -c . 2>/dev/null || echo "$BODY")"
        
        # Esperar y verificar archivo
        echo ""
        echo -e "${CYAN}[*]${NC} Esperando 1s para creación de archivo..."
        sleep 1
        
        echo -ne "${CYAN}[*]${NC} Verificando /tmp/notification.txt... "
        if [ ! -z "$CONTAINER" ]; then
            CONTENT=$(docker exec "$CONTAINER" cat /tmp/notification.txt 2>/dev/null)
            if [ ! -z "$CONTENT" ]; then
                echo -e "${GREEN}✅ Archivo creado${NC}"
                echo "   Contenido: $CONTENT"
            else
                echo -e "${RED}❌ Archivo vacío o no existe${NC}"
                echo -e "   ${YELLOW}Intentando crear archivo manualmente...${NC}"
                docker exec "$CONTAINER" sh -c "echo 'TEST' > /tmp/notification.txt" 2>&1
                docker exec "$CONTAINER" cat /tmp/notification.txt 2>&1
            fi
        fi
    else
        echo -e "   ${RED}❌ Error HTTP ${HTTP_CODE}${NC}"
        echo "   Respuesta: $BODY"
    fi
else
    echo -e "${RED}❌ No se pudo obtener IP del peer${NC}"
fi
echo ""

# 6. Verificación de logs
echo -e "${YELLOW}6️⃣  LOGS DEL CONTENEDOR${NC}"
echo "─────────────────────────────────────────"

if [ ! -z "$CONTAINER" ]; then
    echo -e "${CYAN}[*]${NC} Últimas líneas de logs (búsqueda de 'notifi' o 'MSG'):"
    docker logs "$CONTAINER" 2>/dev/null | grep -i "notif\|msg\|alerta" | tail -10 || echo "   (sin coincidencias)"
fi
echo ""

# 7. Resumen
echo -e "${BLUE}════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}DIAGNÓSTICO COMPLETADO${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Próximos pasos:${NC}"
echo "  1️⃣  Si todo está verde, el sistema está OK"
echo "  2️⃣  Ejecuta: ./test-notification-direct.sh"
echo "  3️⃣  En el receptor ejecuta:"
echo "      docker exec -it <container> python3 /app/notification-monitor-advanced.py"
echo ""
