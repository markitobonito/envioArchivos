#!/usr/bin/env python3
"""
Servicio simple: retorna peers activos leyendo JSON del host
"""
from flask import Flask, jsonify
import json
import os
from pathlib import Path

app = Flask(__name__)

@app.route('/peers', methods=['GET'])
def get_peers():
    """Retorna lista de peers ACTIVOS desde el JSON generado por el host"""
    json_path = Path(os.path.expanduser("~/Documents/prr/envioArchivos/templates/quic-file-transfer/app/tailscale_status.json"))
    
    if not json_path.exists():
        print("[!] tailscale_status.json no existe")
        return jsonify({"peers": []}), 200
    
    try:
        with open(json_path) as f:
            data = json.load(f)
        
        active_peers = []
        self_ips = set(data.get("Self", {}).get("TailscaleIPs", []))
        
        # Filtrar peers activos (Online: true)
        for device in data.get("Peer", {}).values():
            if device.get("Online", False):
                ips = device.get("TailscaleIPs", [])
                if ips and ips[0] not in self_ips:
                    ip = ips[0]
                    active_peers.append(ip)
                    hostname = device.get("HostName", "?")
                    print(f"[+] Peer activo: {hostname} -> {ip}")
        
        print(f"[✓] Total peers activos: {len(active_peers)}")
        return jsonify({"peers": active_peers}), 200
    
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"peers": []}), 200

@app.route('/regenerate', methods=['POST'])
def regenerate():
    """Regenera el JSON ejecutando tailscale status --json"""
    import subprocess
    
    try:
        json_path = os.path.expanduser("~/Documents/prr/envioArchivos/templates/quic-file-transfer/app/tailscale_status.json")
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            with open(json_path, "w") as f:
                f.write(result.stdout)
            print(f"[✓] JSON regenerado")
            return jsonify({"status": "ok"}), 200
        else:
            print(f"[!] tailscale status falló")
            return jsonify({"error": "tailscale status failed"}), 500
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/speak', methods=['POST'])
def speak():
    """Ejecuta TTS en el HOST según el SO"""
    import subprocess
    import platform
    from flask import request
    
    try:
        data = request.get_json()
        message = data.get("message", "")
        repetitions = int(data.get("repetitions", 1))
        
        if not message:
            return jsonify({"error": "no message"}), 400
        
        system = platform.system()
        
        # Ejecutar TTS según el SO
        if system == "Darwin":  # macOS
            for i in range(repetitions):
                subprocess.run(["say", "-v", "es", message], timeout=30)
                print(f"[🔊] macOS: {message} ({i+1}/{repetitions})")
        
        elif system == "Linux":
            for i in range(repetitions):
                try:
                    subprocess.run(["espeak-ng", "-v", "es", message], timeout=30, check=True)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    subprocess.run(["espeak", "-v", "es", message], timeout=30)
                print(f"[🔊] Linux: {message} ({i+1}/{repetitions})")
        
        elif system == "Windows":
            ps_script = f"""Add-Type –AssemblyName System.Speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speak.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSpecified, [System.Speech.Synthesis.VoiceAge]::NotSpecified, 0, [System.Globalization.CultureInfo]'es-ES')
for ($i = 0; $i -lt {repetitions}; $i++) {{
    $speak.Speak(\"{message}\")
}}
"""
            subprocess.run(["powershell", "-Command", ps_script], timeout=30)
            print(f"[🔊] Windows: {message} ({repetitions}x)")
        
        return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("[*] Iniciando servicio en puerto 5001...")
    app.run(host="127.0.0.1", port=5001, threaded=True, debug=False)



