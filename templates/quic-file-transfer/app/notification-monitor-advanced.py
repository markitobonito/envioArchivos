#!/usr/bin/env python3
"""
Monitor avanzado de notificaciones - Detector de cambios en /tmp/notification.txt
Ejecutar en el receptor para ver notificaciones en tiempo real.

Uso:
    python3 notification-monitor-advanced.py
    
En Docker:
    docker exec -it quic-file-transfer-quic-file-transfer-1 python3 /app/notification-monitor-advanced.py
"""

import os
import sys
import time
import platform
import subprocess
from pathlib import Path
from datetime import datetime

NOTIFICATION_FILE = "/tmp/notification.txt"
LAST_CONTENT = None
NOTIFICATION_COUNT = 0

def show_native_notification(title: str, message: str, duration: int = 10):
    """Muestra una notificación nativa del SO."""
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            
        elif system == "Windows":
            # Windows Toast (requiere PowerShell)
            ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$APP_ID = 'QuicFileTransfer'
$template = @"
<toast>
    <visual>
        <binding template="ToastText02">
            <text id="1">{title}</text>
            <text id="2">{message}</text>
        </binding>
    </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($APP_ID).Show($toast)
"""
            subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
            
        elif system == "Linux":
            # Linux notify-send
            subprocess.run(
                ["notify-send", "-u", "critical", "-t", str(duration * 1000), title, message],
                check=True,
                capture_output=True
            )
    except Exception as e:
        print(f"  ⚠️ Error mostrando notificación nativa: {e}")


def display_notification(message: str):
    """Muestra la notificación recibida."""
    global NOTIFICATION_COUNT
    NOTIFICATION_COUNT += 1
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    print("")
    print("╔" + "═" * 78 + "╗")
    print(f"║ 🚨 NOTIFICACIÓN #{NOTIFICATION_COUNT} - {timestamp}" + " " * (78 - 38 - len(str(NOTIFICATION_COUNT))) + "║")
    print("╠" + "═" * 78 + "╣")
    print(f"║ {message:<76} ║")
    print("╚" + "═" * 78 + "╝")
    print("")
    
    # Mostrar notificación nativa
    try:
        show_native_notification("🚨 ALERTA RECIBIDA", message, duration=10)
        print(f"  ✅ Notificación nativa mostrada")
    except Exception as e:
        print(f"  ⚠️ No se pudo mostrar notificación nativa: {e}")


def monitor_notifications():
    """Monitorea el archivo de notificación."""
    global LAST_CONTENT
    
    print("")
    print("╔" + "═" * 78 + "╗")
    print(f"║ 📢 Monitor de Notificaciones QUIC File Transfer" + " " * (31) + "║")
    print("╠" + "═" * 78 + "╣")
    print(f"║ Observando: {NOTIFICATION_FILE:<64} ║")
    print(f"║ Sistema: {platform.system():<69} ║")
    print(f"║ Presiona Ctrl+C para salir" + " " * (49) + "║")
    print("╚" + "═" * 78 + "╝")
    print("")
    
    # Crear archivo si no existe
    Path(NOTIFICATION_FILE).parent.mkdir(parents=True, exist_ok=True)
    
    try:
        while True:
            try:
                if os.path.exists(NOTIFICATION_FILE):
                    # Leer contenido
                    with open(NOTIFICATION_FILE, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                    
                    # Si cambió el contenido
                    if content and content != LAST_CONTENT:
                        LAST_CONTENT = content
                        display_notification(content)
                
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n" + "═" * 80)
        print(f"👋 Monitor detenido. Total notificaciones recibidas: {NOTIFICATION_COUNT}")
        print("═" * 80)
        sys.exit(0)


if __name__ == "__main__":
    monitor_notifications()
