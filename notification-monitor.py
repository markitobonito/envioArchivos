#!/usr/bin/env python3
"""
Monitor de notificaciones para QUIC File Transfer
Monitorea archivos de notificación y muestra notificaciones nativas del SO.

Uso:
    python3 notification-monitor.py
    
    En Windows: python notification-monitor.py
    En Linux: python3 notification-monitor.py
    En macOS: python3 notification-monitor.py
"""

import os
import sys
import time
import platform
import subprocess
from pathlib import Path


def show_notification(title: str, message: str, duration: int = 10):
    """Muestra una notificación nativa del SO."""
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            print(f"✓ Notificación macOS: {title}")
            
        elif system == "Windows":
            ps_script = f"""
$Notification = @{{
    ToastTitle   = "{title}"
    ToastMessage = "{message}"
    ToastDuration = "Long"
}}
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
            print(f"✓ Notificación Windows: {title}")
            
        elif system == "Linux":
            subprocess.run(
                ["notify-send", "-u", "critical", "-t", str(duration * 1000), title, message],
                check=True,
                capture_output=True
            )
            print(f"✓ Notificación Linux: {title}")
            
    except Exception as e:
        print(f"✗ Error mostrando notificación: {e}")


def monitor_notifications(watch_file: str = "/tmp/notification.txt", check_interval: int = 1):
    """Monitorea cambios en un archivo de notificación."""
    print(f"🔍 Monitor de notificaciones iniciado")
    print(f"   Observando: {watch_file}")
    print(f"   Intervalo: {check_interval}s")
    print(f"   Sistema: {platform.system()}")
    print(f"   Presiona Ctrl+C para salir\n")
    
    last_mtime = None
    last_content = None
    
    try:
        while True:
            try:
                if os.path.exists(watch_file):
                    current_mtime = os.path.getmtime(watch_file)
                    
                    # Si el archivo cambió recientemente
                    if last_mtime is None or current_mtime > last_mtime:
                        time.sleep(0.1)  # Pequeño delay para asegurar escritura completa
                        
                        with open(watch_file, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                        
                        if content and content != last_content:
                            print(f"\n📬 NOTIFICACIÓN NUEVA:")
                            print(f"   {content}\n")
                            
                            # Mostrar notificación nativa
                            show_notification("🚨 ALERTA URGENTE", content, duration=10)
                            
                            last_content = content
                            last_mtime = current_mtime
                            
                            # Limpiar archivo
                            try:
                                os.remove(watch_file)
                                print(f"✓ Archivo limpiado\n")
                            except:
                                pass
                
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"✗ Error: {e}")
                time.sleep(check_interval)
                
    except KeyboardInterrupt:
        print("\n\n👋 Monitor detenido")
        sys.exit(0)


if __name__ == "__main__":
    monitor_notifications()
