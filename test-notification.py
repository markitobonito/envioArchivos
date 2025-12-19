#!/usr/bin/env python3
"""Script de prueba para enviar notificación directamente al contenedor QUIC"""

import socket
import sys

def send_test_notification(ip: str = "127.0.0.1", port: int = 9999, message: str = "🚨 PRUEBA: Este es un mensaje de alerta de prueba"):
    """Envía una notificación de prueba directamente vía UDP QUIC"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        
        # Enviar header "MSG:\0" + mensaje
        header = b"MSG:\0"
        message_bytes = message.encode("utf-8", errors="ignore")
        data = header + message_bytes
        
        sock.sendto(data, (ip, port))
        sock.close()
        
        print(f"✓ Notificación de prueba enviada a {ip}:{port}")
        print(f"  Mensaje: {message}")
        return True
    except Exception as e:
        print(f"✗ Error enviando notificación: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    message = sys.argv[2] if len(sys.argv) > 2 else "🚨 PRUEBA: Este es un mensaje de alerta de prueba"
    
    print(f"Enviando notificación de prueba a {ip}...")
    send_test_notification(ip, 9999, message)
