#!/usr/bin/env python3
"""
Monitor de Tailscale: Reconecta automáticamente si se desconecta.
Corre como proceso de fondo y mantiene Tailscale activo 24/7.
"""
import subprocess
import time
import os
import sys
import json
from pathlib import Path
from datetime import datetime
import requests

def log_msg(msg):
    """Log con timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def get_auth_key():
    """Lee el TAILSCALE_AUTHKEY del .env"""
    home = os.path.expanduser("~")
    env_file = Path(home) / "Documents/prr/envioArchivos/templates/quic-file-transfer/.env"
    
    if not env_file.exists():
        log_msg("[!] .env no encontrado")
        return None
    
    try:
        with open(env_file) as f:
            for line in f:
                if line.startswith("TAILSCALE_AUTHKEY="):
                    return line.split("=", 1)[1].strip()
    except Exception as e:
        log_msg(f"[!] Error leyendo .env: {e}")
    return None

def get_api_key():
    """Lee el TAILSCALE_API_KEY del .env"""
    home = os.path.expanduser("~")
    env_file = Path(home) / "Documents/prr/envioArchivos/templates/quic-file-transfer/.env"
    
    try:
        with open(env_file) as f:
            for line in f:
                if line.startswith("TAILSCALE_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except:
        pass
    return None

def get_tailnet():
    """Lee el TAILNET del .env"""
    home = os.path.expanduser("~")
    env_file = Path(home) / "Documents/prr/envioArchivos/templates/quic-file-transfer/.env"
    
    try:
        with open(env_file) as f:
            for line in f:
                if line.startswith("TAILNET="):
                    return line.split("=", 1)[1].strip()
    except:
        pass
    return None

def update_json_from_api():
    """Obtiene peers desde API REST de Tailscale (FUENTE DE VERDAD EN NUBE)"""
    api_key = get_api_key()
    tailnet = get_tailnet()
    
    if not api_key or not tailnet:
        return False
    
    try:
        home = os.path.expanduser("~")
        url = f"https://api.tailscale.com/api/v2/tailnet/{tailnet}/devices"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            log_msg(f"[!] API error {response.status_code}")
            return False
        
        devices = response.json().get("devices", [])
        
        # Construir JSON en formato compatible con client.py
        json_data = {
            "Peer": {},
            "Self": {"TailscaleIPs": []},
            "Version": "tailscale-api-v2"
        }
        
        peer_count = 0
        for device in devices:
            device_name = device.get("name", "?")
            ips = device.get("addresses", [])
            if not ips:
                continue
            
            ip = ips[0].split("/")[0] if "/" in ips[0] else ips[0]
            
            # Determinar si es el Self (macbook)
            if "macbook" in device_name.lower():
                json_data["Self"]["HostName"] = device_name
                json_data["Self"]["TailscaleIPs"] = [ip]
            else:
                # Es un peer - INCLUIR CON InNetworkMap=true
                # (La API REST siempre retorna dispositivos en la red, aunque no estén online)
                json_data["Peer"][device.get("id", ip)] = {
                    "HostName": device_name,
                    "TailscaleIPs": [ip],
                    "Online": device.get("online", False),
                    "InMagicSock": device.get("online", False),
                    "InNetworkMap": True,  # IMPORTANTE: todos están en la red por que la API los retorna
                }
                peer_count += 1
                status = "🟢" if device.get("online") else "⚫"
                log_msg(f"    {status} {device_name} ({ip})")
        
        # Escribir JSON
        json_path = Path(home) / "Documents/prr/envioArchivos/templates/quic-file-transfer/app/tailscale_status.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=2)
        
        log_msg(f"[✓] API REST: {peer_count} peers (incluidos offline)")
        return True
    except Exception as e:
        log_msg(f"[!] Error API REST: {e}")
        return False

def check_tailscale_status():
    """Verifica si Tailscale está conectado y lógueado"""
    try:
        # Primero, intentar obtener la IP - si la hay, está conectado
        result_ip = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if result_ip.returncode == 0 and result_ip.stdout.strip():
            # Hay IP, está conectado
            return "connected"
        
        # Si no hay IP, verificar qué pasó
        result = subprocess.run(
            ["tailscale", "status"],
            capture_output=True,
            text=True,
            timeout=3
        )
        
        output = result.stdout + result.stderr
        
        # Verificar si está lógueado
        if "logged out" in output.lower() or "invalid key" in output.lower():
            return "logged_out"
        
        # Verificar si está stopped
        if "stopped" in output.lower():
            return "stopped"
        
        # Verificar si está offline
        if "offline" in output.lower():
            return "offline"
        
        # Verificar si hay error de coordinación
        if "unable to connect" in output.lower():
            return "coord_error"
        
        return "unknown"
    except subprocess.TimeoutExpired:
        log_msg(f"[!] Timeout verificando status (tailscale lento)")
        return "timeout"
    except Exception as e:
        log_msg(f"[!] Error verificando status: {e}")
        return "error"

def get_tailscale_ip():
    """Obtiene la IP de Tailscale del host"""
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    return None

def reconnect_tailscale(auth_key):
    """Reconecta a Tailscale con el auth key"""
    if not auth_key:
        log_msg("[!] No hay TAILSCALE_AUTHKEY disponible")
        return False
    
    import platform
    os_type = platform.system()
    
    log_msg("[*] Intentando reconectar a Tailscale...")
    
    try:
        # Logout previo (opcional, por si estaba deslogueado)
        try:
            if os_type == "Windows":
                # Windows: no necesita sudo
                subprocess.run(
                    ["tailscale", "logout", "--accept-risk=lose-ssh-access"],
                    capture_output=True,
                    timeout=2
                )
            else:
                # macOS/Linux: necesita sudo
                subprocess.run(
                    ["sudo", "tailscale", "logout", "--accept-risk=lose-ssh-access"],
                    capture_output=True,
                    timeout=2
                )
            log_msg("[*] Logout completado")
            time.sleep(1)
        except subprocess.TimeoutExpired:
            log_msg("[!] Logout timeout (ignorando, pasando a reconnect)")
        except Exception as e:
            log_msg(f"[!] Logout error: {e} (ignorando)")
        
        # Conectar con el auth key
        if os_type == "Windows":
            # Windows: no necesita sudo
            result = subprocess.run(
                ["tailscale", "up", f"--authkey={auth_key}", "--accept-routes", "--accept-dns"],
                capture_output=True,
                text=True,
                timeout=15
            )
        else:
            # macOS/Linux: necesita sudo
            result = subprocess.run(
                ["sudo", "tailscale", "up", f"--authkey={auth_key}", "--accept-routes", "--accept-dns"],
                capture_output=True,
                text=True,
                timeout=15
            )
        
        if result.returncode == 0:
            log_msg("[✓] Reconexión exitosa")
            time.sleep(2)
            return True
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            log_msg(f"[!] Error: {error_msg[:100]}")
            return False
    except subprocess.TimeoutExpired:
        log_msg("[!] Timeout en conexión (auth key inválido o servidor lento)")
        return False
    except Exception as e:
        log_msg(f"[!] Excepción: {e}")
        return False
    except Exception as e:
        log_msg(f"[!] Excepción: {e}")
        return False

def ensure_tailscale_daemon():
    """Asegura que el daemon tailscaled esté corriendo"""
    try:
        import platform
        os_type = platform.system()
        
        # Verificar si el daemon está corriendo
        daemon_running = False
        
        if os_type == "Windows":
            # Windows: usar tasklist
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq tailscaled.exe"],
                capture_output=True,
                text=True
            )
            daemon_running = "tailscaled.exe" in result.stdout
        else:
            # macOS/Linux: usar pgrep
            result = subprocess.run(
                ["pgrep", "-x", "tailscaled"],
                capture_output=True
            )
            daemon_running = result.returncode == 0
        
        if not daemon_running:
            log_msg("[!] tailscaled no está corriendo, iniciando...")
            
            if os_type == "Darwin":
                # macOS: usar brew services
                subprocess.run(
                    ["sudo", "brew", "services", "start", "tailscale"],
                    capture_output=True,
                    timeout=30
                )
            elif os_type == "Windows":
                # Windows: usar net start o GUI
                subprocess.run(
                    ["net", "start", "Tailscale"],
                    capture_output=True,
                    timeout=10
                )
            else:
                # Linux: usar systemctl
                subprocess.run(
                    ["sudo", "systemctl", "start", "tailscaled"],
                    capture_output=True,
                    timeout=10
                )
            
            time.sleep(3)
    except Exception as e:
        log_msg(f"[!] Error iniciando tailscaled: {e}")

def update_json_status():
    """Actualiza el JSON de status para que lo lea el contenedor
    PRIMERO intenta API REST (fuente de verdad en nube)
    LUEGO fallback a tailscale status --json (local)
    """
    # Primero: intentar API REST (más confiable)
    if update_json_from_api():
        log_msg("[✓] JSON actualizado desde API REST (fuente en nube)")
        return True
    
    # Fallback: tailscale status local
    try:
        home = os.path.expanduser("~")
        json_path = Path(home) / "Documents/prr/envioArchivos/templates/quic-file-transfer/app/tailscale_status.json"
        
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, "w") as f:
                f.write(result.stdout)
            log_msg("[✓] JSON actualizado desde 'tailscale status' (local)")
            return True
    except Exception as e:
        log_msg(f"[!] Error actualizando JSON local: {e}")
    
    return False

def main():
    """Loop principal"""
    log_msg("🔐 Iniciando Monitor de Tailscale")
    
    auth_key = get_auth_key()
    if not auth_key:
        log_msg("[!] CRÍTICO: No se pudo obtener TAILSCALE_AUTHKEY")
        sys.exit(1)
    
    log_msg("[✓] TAILSCALE_AUTHKEY cargado")
    
    # Verificaciones iniciales
    ensure_tailscale_daemon()
    time.sleep(2)
    
    # Loop de monitoreo
    consecutive_errors = 0
    check_interval = 20  # 20 segundos
    
    while True:
        try:
            status = check_tailscale_status()
            ip = get_tailscale_ip()
            
            if status == "connected":
                # ✅ Está bien, actualizar JSON CADA 20 segundos
                if consecutive_errors > 0:
                    log_msg(f"[✓] Reconexión exitosa. IP: {ip}")
                    consecutive_errors = 0
                
                # Actualizar JSON SIEMPRE (cada 20 segundos)
                # Usa API REST (fuente de verdad en nube)
                update_json_status()
            
            elif status == "logged_out":
                log_msg(f"[⚠️] Tailscale está deslogueado")
                consecutive_errors += 1
                
                if consecutive_errors >= 1:  # Reconectar inmediatamente
                    if reconnect_tailscale(auth_key):
                        consecutive_errors = 0
                        time.sleep(3)
                        update_json_status()
            
            elif status == "offline" or status == "stopped":
                log_msg(f"[⚠️] Tailscale está {status}")
                consecutive_errors += 1
                
                if consecutive_errors >= 2:  # Esperar 2 intentos antes de reconectar
                    if reconnect_tailscale(auth_key):
                        consecutive_errors = 0
                        time.sleep(3)
                        update_json_status()
            
            elif status == "coord_error":
                log_msg(f"[⚠️] Error de coordinación, pero hay IP: {ip}")
                # Intentar actualizar status para reactivar peers
                update_json_status()
                consecutive_errors = 0
            
            elif status == "timeout":
                log_msg(f"[!] Tailscale lento (timeout), reintentando...")
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    if reconnect_tailscale(auth_key):
                        consecutive_errors = 0
            
            else:
                log_msg(f"[!] Estado desconocido: {status}")
                consecutive_errors += 1
            
            time.sleep(check_interval)
        
        except KeyboardInterrupt:
            log_msg("[*] Monitor detenido por usuario")
            sys.exit(0)
        except Exception as e:
            log_msg(f"[!] Error en loop: {e}")
            consecutive_errors += 1
            time.sleep(check_interval)

if __name__ == "__main__":
    main()
