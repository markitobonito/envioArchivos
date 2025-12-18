#!/usr/bin/env python3
"""
Script para diagnosticar la conexión QUIC/TCP a un peer Tailscale
"""
import subprocess
import json
import asyncio
import socket
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration

# Obtener peers Tailscale
print("=" * 60)
print("DIAGNOSTICO DE CONEXION QUIC/TCP")
print("=" * 60)

try:
    result = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    self_ips = set(data.get("Self", {}).get("TailscaleIPs", []))
    print(f"\n[*] IP local: {self_ips}")
    
    peers = []
    for name, info in data.get("Peer", {}).items():
        if info.get("Online", False):
            dns_name = info.get("DNSName", "").rstrip(".")
            ips = info.get("TailscaleIPs", [])
            if ips and ips[0] not in self_ips:
                peer_addr = dns_name if dns_name else ips[0]
                peers.append({
                    "name": name,
                    "addr": peer_addr,
                    "ip": ips[0],
                    "dns": dns_name
                })
    
    print(f"\n[*] Peers encontrados: {len(peers)}")
    for i, p in enumerate(peers, 1):
        print(f"   {i}. {p['addr']} (IP: {p['ip']}, DNS: {p['dns']})")
    
    if not peers:
        print("[!] No hay peers online")
        exit(1)
    
    # Test first peer
    target = peers[0]
    print(f"\n[*] Testeando conexión a: {target['addr']}")
    
    # Test TCP primero (más rápido)
    print(f"\n[1] Test TCP a {target['addr']}:9999")
    try:
        s = socket.create_connection((target['addr'], 9999), timeout=5)
        s.close()
        print(f"    [✓] TCP conectado exitosamente")
    except Exception as e:
        print(f"    [!] TCP falló: {type(e).__name__}: {e}")
    
    # Test QUIC
    print(f"\n[2] Test QUIC a {target['addr']}:9999")
    
    config = QuicConfiguration(is_client=True, alpn_protocols=["quic-file"])
    config.verify_mode = False
    
    async def test_quic():
        try:
            print(f"    [*] Conectando...")
            async with connect(target['addr'], 9999, configuration=config) as client:
                print(f"    [✓] QUIC conectado exitosamente")
                print(f"        Local: {client._local_addr}")
                print(f"        Remote: {client._remote_addr}")
        except Exception as e:
            print(f"    [!] QUIC falló: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test_quic())
    
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
