#!/usr/bin/env python3
"""
Test specific peer
"""
import subprocess
import json
import asyncio
import socket
import sys
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration

target_name = sys.argv[1] if len(sys.argv) > 1 else "marco-hp-laptop"

result = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, check=True)
data = json.loads(result.stdout)
self_ips = set(data.get("Self", {}).get("TailscaleIPs", []))

for name, info in data.get("Peer", {}).items():
    if info.get("Online", False):
        dns_name = info.get("DNSName", "").rstrip(".")
        if target_name in dns_name or target_name in name:
            ips = info.get("TailscaleIPs", [])
            if ips and ips[0] not in self_ips:
                addr = dns_name if dns_name else ips[0]
                print(f"Testing {dns_name} ({ips[0]})...")
                
                # TCP
                print(f"  [TCP] ", end="", flush=True)
                try:
                    s = socket.create_connection((addr, 9999), timeout=5)
                    s.close()
                    print("OK")
                except Exception as e:
                    print(f"FAIL: {type(e).__name__}")
                
                # QUIC
                print(f"  [QUIC] ", end="", flush=True)
                config = QuicConfiguration(is_client=True, alpn_protocols=["quic-file"])
                config.verify_mode = False
                
                async def test():
                    try:
                        async with connect(addr, 9999, configuration=config) as client:
                            print(f"OK")
                    except Exception as e:
                        print(f"FAIL: {type(e).__name__}")
                
                asyncio.run(test())
                break
