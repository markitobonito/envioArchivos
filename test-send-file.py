#!/usr/bin/env python3
"""
Test real de envío de archivo pequeño al laptop
"""
import os
import asyncio
import json
import subprocess
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration

# Obtener el DNS del laptop
result = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, check=True)
data = json.loads(result.stdout)
self_ips = set(data.get("Self", {}).get("TailscaleIPs", []))

laptop_addr = None
for name, info in data.get("Peer", {}).items():
    if "marco-hp-laptop" in info.get("DNSName", "").lower():
        if info.get("Online", False):
            dns_name = info.get("DNSName", "").rstrip(".")
            ips = info.get("TailscaleIPs", [])
            if ips and ips[0] not in self_ips:
                laptop_addr = dns_name if dns_name else ips[0]
                print(f"[*] Laptop encontrado: {laptop_addr}")
                break

if not laptop_addr:
    print("[!] No se encontró el laptop online")
    exit(1)

# Crear archivo de prueba pequeño
test_file = "/tmp/test_quic_transfer.txt"
test_content = b"X" * (1024 * 1024)  # 1 MB
with open(test_file, "wb") as f:
    f.write(test_content)

print(f"[*] Archivo de prueba creado: {test_file} ({len(test_content)} bytes)")

config = QuicConfiguration(is_client=True, alpn_protocols=["quic-file"])
config.verify_mode = False

async def send_test_file():
    filename = "test_quic_transfer.txt"
    print(f"\n[>] Enviando '{filename}' a {laptop_addr}:9999...")
    
    try:
        print(f"[*] Conectando QUIC...")
        async with connect(laptop_addr, 9999, configuration=config) as client:
            print(f"[✓] Conectado!")
            
            stream_id = client._quic.get_next_available_stream_id()
            header = filename.encode() + b"\0"
            
            print(f"[*] Enviando header: {filename}")
            client._quic.send_stream_data(stream_id, header, end_stream=False)
            
            print(f"[*] Enviando {len(test_content)} bytes...")
            client._quic.send_stream_data(stream_id, test_content, end_stream=False)
            
            print(f"[*] Finalizando stream...")
            client._quic.send_stream_data(stream_id, b"", end_stream=True)
            
            print(f"[*] Esperando ACK...")
            for i in range(100):
                await asyncio.sleep(0.1)
                if client._quic._streams.get(stream_id) is None:
                    print(f"[✓] Stream cerrado por servidor")
                    break
            
            print(f"[+] ¡ÉXITO! Archivo enviado.")
            return True
            
    except Exception as e:
        print(f"[!] Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

result = asyncio.run(send_test_file())

if result:
    print("\n[+] Test EXITOSO - Verifica si el archivo apareció en ~/Downloads del laptop")
else:
    print("\n[!] Test FALLÓ")

# Limpiar
os.remove(test_file)
