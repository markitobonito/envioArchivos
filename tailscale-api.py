#!/usr/bin/env python3
"""
Servicio simple: retorna peers activos leyendo JSON del host
Si tailscale status falla, usa API REST
"""
from flask import Flask, jsonify
import json
import os
import subprocess
from pathlib import Path
import requests

app = Flask(__name__)

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

def get_peers_from_api():
    """Obtiene peers desde API REST de Tailscale"""
    api_key = get_api_key()
    tailnet = get_tailnet()
    
    if not api_key or not tailnet:
        print(f"[!] Credenciales incompletas: api_key={bool(api_key)}, tailnet={bool(tailnet)}")
        return None
    
    try:
        print(f"[*] Usando API REST para obtener dispositivos...")
        print(f"    Tailnet: {tailnet}")
        url = f"https://api.tailscale.com/api/v2/tailnet/{tailnet}/devices"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        response = requests.get(url, headers=headers, timeout=10)
        print(f"[*] API response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"[!] API error {response.status_code}: {response.text[:200]}")
            return None
        
        data = response.json()
        devices = data.get("devices", [])
        print(f"[✓] API retornó {len(devices)} dispositivos")
        
        # Debug: imprimir todos los dispositivos
        for i, device in enumerate(devices):
            print(f"    Device {i}: {device.get('name')} - online={device.get('online')} - addresses={device.get('addresses', [])}")
        
        # Convertir a formato JSON local
        mock_json = {
            "Peer": {},
            "Self": {"TailscaleIPs": []},
            "Version": "1.0-api"
        }
        
        for device in devices:
            ips = device.get("addresses", [])
            if not ips:
                print(f"    [skip] {device.get('name')}: sin addresses")
                continue
            
            ip = ips[0].split("/")[0] if "/" in ips[0] else ips[0]
            mock_json["Peer"][device.get("id", "unknown")] = {
                "HostName": device.get("name", "?"),
                "TailscaleIPs": [ip],
                "Online": device.get("online", False),
                "InMagicSock": device.get("online", False),
            }
            
            status = "🟢 ONLINE" if device.get("online") else "⚫"
            print(f"  {status} {device.get('name')} ({ip})")
        
        return mock_json
    except Exception as e:
        print(f"[!] Error API REST: {e}")
        import traceback
        traceback.print_exc()
        return None

@app.route('/peers', methods=['GET'])
def get_peers():
    """Retorna lista de peers activos"""
    home = os.path.expanduser("~")
    json_path = Path(home) / "Documents/prr/envioArchivos/templates/quic-file-transfer/app/tailscale_status.json"
    
    if not json_path.exists():
        alt_paths = [
            Path(home) / ".tailscale_status.json",
            Path("/tmp/tailscale_status.json"),
            Path("/app/tailscale_status.json"),
        ]
        for alt_path in alt_paths:
            if alt_path.exists():
                json_path = alt_path
                break
    
    if not json_path.exists():
        print(f"[!] tailscale_status.json no existe")
        return jsonify({"peers": []}), 200
    
    try:
        with open(json_path) as f:
            data = json.load(f)
        
        active_peers = []
        self_ips = set(data.get("Self", {}).get("TailscaleIPs", []))
        
        for device in data.get("Peer", {}).values():
            is_reachable = device.get("Online", False) or device.get("InMagicSock", False)
            if is_reachable:
                ips = device.get("TailscaleIPs", [])
                if ips and ips[0] not in self_ips:
                    ip = ips[0]
                    active_peers.append(ip)
                    hostname = device.get("HostName", "?")
                    print(f"[✓] Peer: {hostname} -> {ip}")
        
        print(f"[✓] Total peers: {len(active_peers)}")
        return jsonify({"peers": active_peers}), 200
    
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"peers": []}), 200

@app.route('/regenerate', methods=['POST'])
def regenerate():
    """Regenera JSON desde tailscale status, fallback a API REST"""
    home = os.path.expanduser("~")
    json_path = home + "/Documents/prr/envioArchivos/templates/quic-file-transfer/app/tailscale_status.json"
    
    # Intentar tailscale status primero
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout:
            Path(json_path).parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, "w") as f:
                f.write(result.stdout)
            print(f"[✓] JSON regenerado desde tailscale status")
            return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"[!] tailscale status falló: {e}")
    
    # Fallback: API REST
    print("[*] Intentando fallback a API REST...")
    mock_json = get_peers_from_api()
    
    if mock_json:
        try:
            Path(json_path).parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, "w") as f:
                json.dump(mock_json, f, indent=2)
            print(f"[✓] JSON regenerado desde API REST")
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"[!] Error escribiendo JSON: {e}")
    
    print("[!] No se pudo regenerar JSON")
    return jsonify({"status": "error"}), 500

if __name__ == "__main__":
    print("[*] API Tailscale iniciada (puerto 5001)")
    app.run(host="0.0.0.0", port=5001, debug=False)



