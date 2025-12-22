#!/bin/bash
# Script para probar envío de notificaciones directamente

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PRUEBA DIRECTA DE NOTIFICACIONES${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Leer Tailscale IPs del status.json
STATUS_FILE="templates/quic-file-transfer/app/tailscale_status.json"

if [ ! -f "$STATUS_FILE" ]; then
    echo -e "${RED}❌ Error: $STATUS_FILE no encontrado${NC}"
    echo -e "${YELLOW}   Ejecuta primero: ./run-docker.sh${NC}"
    exit 1
fi

echo -e "${YELLOW}[*] Leyendo peers desde $STATUS_FILE...${NC}"

# Extraer IP del peer (diferente al host)
PEER_IP=$(jq -r '.Peer | to_entries[0].value.TailscaleIPs[0]' "$STATUS_FILE" 2>/dev/null)

if [ -z "$PEER_IP" ] || [ "$PEER_IP" = "null" ]; then
    echo -e "${RED}❌ No se pudo obtener IP del peer${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Peer encontrado: $PEER_IP${NC}"
echo ""

# Mensaje de prueba
MESSAGE="🚨 PRUEBA DE NOTIFICACIÓN - $(date '+%H:%M:%S')"

echo -e "${BLUE}Enviando notificación...${NC}"
echo -e "${YELLOW}  IP destino: $PEER_IP${NC}"
echo -e "${YELLOW}  Mensaje: $MESSAGE${NC}"
echo ""

# Enviar notificación por HTTP
RESPONSE=$(curl -s -X POST "http://$PEER_IP:5000/receive-notification" \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"$MESSAGE\"}" \
    -w "\n%{http_code}")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

echo -e "${YELLOW}Respuesta HTTP: $HTTP_CODE${NC}"
echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
echo ""

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Notificación enviada exitosamente${NC}"
    echo ""
    echo -e "${BLUE}Verificando archivo /tmp/notification.txt en receptor...${NC}"
    
    # Intentar leer el archivo via ssh o docker
    if command -v docker &> /dev/null; then
        echo -e "${YELLOW}[*] Usando docker para verificar...${NC}"
        sleep 1
        CONTAINER=$(docker ps --filter "name=quic-file-transfer" -q | head -1)
        if [ ! -z "$CONTAINER" ]; then
            echo -e "${YELLOW}   Contenedor: $CONTAINER${NC}"
            docker exec "$CONTAINER" cat /tmp/notification.txt 2>/dev/null && \
                echo -e "${GREEN}✅ Archivo creado correctamente en contenedor${NC}" || \
                echo -e "${YELLOW}⚠️  Archivo aún no disponible${NC}"
        fi
    fi
else
    echo -e "${RED}❌ Error enviando notificación (HTTP $HTTP_CODE)${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Prueba completada${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
