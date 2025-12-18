# QUIC File Transfer - Multicast Sender/Receiver

Sistema de transferencia de archivos multicast usando QUIC y Tailscale. Funciona tanto como **emisor** como **receptor** simultáneamente.

## Características

- ✅ **Soporte QUIC**: Protocolo UDP moderno con encriptación integrada
- ✅ **Fallback TCP**: Si QUIC falla, intenta envío por TCP
- ✅ **Tailscale Integration**: Conecta automáticamente peers en tu Tailnet
- ✅ **Receptor Integrado**: Recibe archivos en `~/Downloads` mientras envías
- ✅ **Contenedorizado**: Docker con soporta Linux, Windows y macOS
- ✅ **Web UI**: Interfaz bonita con Tailwind CSS

## Requisitos

### Linux / macOS
- **Docker** y **docker-compose** (o **Docker Desktop** con `docker compose`)
- **Tailscale** instalado en el host (opcional pero recomendado)

### Windows
- **Docker Desktop** (incluye `docker compose`)
- **Tailscale** (opcional pero recomendado)

## Configuración

### 1. Crear archivo `.env`

En `templates/quic-file-transfer/` crea un archivo `.env` con tus credenciales:

```bash
# Production environment variables for docker-compose (keep this file private)
TAILSCALE_AUTHKEY=tskey-auth-...
TAILSCALE_API_KEY=tskey-api-...
TAILNET=your-email@tailscale.com
FLASK_ENV=production
```

**⚠️ IMPORTANTE**: Nunca subir este archivo a Git. Ya está en `.gitignore`.

### 2. Obtener Tailscale Auth Key

1. Ve a https://login.tailscale.com/admin/settings/keys
2. Genera una **Auth Key** (máquina de larga duración)
3. Copia el valor en `TAILSCALE_AUTHKEY`
4. Haz lo mismo para la **API Key**

## Despliegue

### Linux / macOS

```bash
# Hacer ejecutable el script
chmod +x run-docker.sh

# Ejecutar (se levantará el contenedor y abrirá http://localhost:5000)
./run-docker.sh
```

### Windows

```batch
REM Hacer doble-click en run-docker.bat
REM O ejecutar desde PowerShell/CMD:
run-docker.bat
```

## Cómo usar

1. **Abre el navegador** → `http://localhost:5000`
2. **Selecciona un archivo** para enviar
3. El sistema automáticamente:
   - Detecta todos los **peers Tailscale online** de tu Tailnet
   - **Envía el archivo** a cada peer (intenta QUIC → fallback TCP)
   - Los archivos se **reciben en `~/Downloads`** en cada máquina remota

## Verificar status

### Ver logs en vivo

```bash
# Linux/macOS
docker-compose -f templates/quic-file-transfer/docker-compose.yml logs -f

# Windows
docker compose -f templates\quic-file-transfer\docker-compose.yml logs -f
```

### Ver status de Tailscale en el contenedor

```bash
docker exec -it quic-file-transfer-quic-file-transfer-1 cat /app/tailscale_status.json
```

### Listar IPs Tailscale detectadas

```bash
docker exec -it quic-file-transfer-quic-file-transfer-1 tailscale status
```

## Detener / Restart

### Detener

```bash
# Linux/macOS
docker-compose -f templates/quic-file-transfer/docker-compose.yml down

# Windows
docker compose -f templates\quic-file-transfer\docker-compose.yml down
```

### Reiniciar

```bash
# Linux/macOS
./run-docker.sh

# Windows
run-docker.bat
```

## Troubleshooting

### "No hay peers Tailscale online"

1. Verifica que Tailscale esté corriendo: `tailscale status`
2. Comprueba que otros dispositivos estén online
3. Revisa los logs del contenedor: `docker logs quic-file-transfer-quic-file-transfer-1`

### Los archivos no se reciben

1. **Verifica el puerto UDP 9999** está abierto:
   - Linux: `sudo ufw allow 9999/udp`
   - Windows: comprueba el firewall

2. **Revisa los logs de emisión**:
   ```bash
   docker logs -f quic-file-transfer-quic-file-transfer-1 | grep "Enviando\|COMPLETADO\|Error"
   ```

3. **Prueba TCP fallback** manualmente:
   ```bash
   # En el receptor
   nc -l -p 9999
   
   # En el emisor
   echo "test.txt" | nc <receiver-ip> 9999
   ```

### Problemas con Tailscale en el contenedor (Docker Desktop en Windows/macOS)

Si el contenedor no puede acceder a Tailscale:

1. **Asegúrate de que el host tiene Tailscale corriendo**: `tailscale status`
2. El contenedor monta `/var/run/tailscale` del host; Docker Desktop podría no exponerlo correctamente
3. **Alternativa**: genera el `tailscale_status.json` en el host y deja que el contenedor lo lea:
   ```bash
   tailscale status --json > templates/quic-file-transfer/app/tailscale_status.json
   ```

## Seguridad

- ✅ Archivos encriptados en tránsito (QUIC con TLS + TCP con fallback)
- ✅ Certificados autofirmados en `certs/`
- ✅ **NO** subir `.env` con credenciales
- ✅ **NO** exponer puertos 5000/9999 a Internet (solo Tailscale)

## Archivos importantes

```
envioArchivos/
├── run-docker.sh          # Script para Linux/macOS
├── run-docker.bat         # Script para Windows
├── .gitignore             # Excluye .env y credenciales
├── .env                   # Tus credenciales (privado)
├── templates/quic-file-transfer/
│   ├── .env               # Ambiente del contenedor (privado)
│   ├── docker-compose.yml # Configuración del contenedor
│   ├── Dockerfile         # Imagen Docker
│   ├── entrypoint.sh      # Script de inicio del contenedor
│   ├── requirements.txt    # Dependencias Python
│   ├── run.py             # Punto de entrada Python
│   ├── certs/
│   │   ├── cert.pem       # Certificado autofirmado
│   │   └── key.pem        # Clave privada
│   ├── app/
│   │   ├── client.py      # Lógica de emisor/receptor
│   │   ├── quic_server.py # Servidor QUIC
│   │   ├── utils.py       # Utilidades
│   │   └── uploads/       # Archivos subidos temporalmente
│   └── tests/
│       ├── test_client.py
│       └── test_quic_server.py
```

## Notas técnicas

### QUIC vs TCP

- **QUIC**: UDP basado, más rápido, encriptado por defecto
  - Puerto: 9999 (UDP)
  - Protocolo: RFC 9000
  
- **TCP Fallback**: Si QUIC falla o está bloqueado
  - Puerto: 9999 (TCP)
  - Formato: `filename\0` + bytes del archivo

### Detección de peers

El sistema lee `tailscale_status.json` (generado por `tailscale status --json`) para descubrir:
- Tu IP Tailscale
- IPs de peers online
- DNSNames de cada peer

### Montajes Docker

```yaml
volumes:
  - ./app:/app                          # Código
  - ./certs:/certs                      # Certificados
  - /var/run/tailscale:/var/run/tailscale:ro  # Socket de Tailscale
  - /var/lib/tailscale:/var/lib/tailscale:ro  # Estado de Tailscale
```

## Contacto / Issues

Si tienes problemas:
1. Revisa los logs: `docker logs quic-file-transfer-quic-file-transfer-1`
2. Verifica la conectividad Tailscale: `tailscale status`
3. Abre un issue con el error y los primeros 50 caracteres del archivo de error

---

**Hecho con ❤️ usando QUIC + Tailscale + Docker**
