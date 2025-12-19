#!/usr/bin/env python3
"""
Monitor de notificaciones - Detecta archivos de notificación y abre alertas automáticamente.
Similar al video-monitor.py pero para notificaciones.
"""

import os
import time
import subprocess
import platform
from pathlib import Path

NOTIFICATION_FILE = "/tmp/notification.txt"
PROCESSED_FILE = "/tmp/notification-processed.txt"
LOCK_FILE = "/tmp/notification-monitor.lock"

def acquire_lock():
    """Adquiere un lock para asegurar que solo una instancia corre."""
    try:
        # Verificar si ya existe un lock
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, "r") as f:
                pid = f.read().strip()
            # Verificar si el proceso sigue corriendo
            if pid and int(pid) > 0:
                try:
                    os.kill(int(pid), 0)  # Verifica si el proceso existe
                    print(f"❌ Monitor ya ejecutándose (PID: {pid})")
                    return False
                except:
                    pass
        
        # Crear nuevo lock
        current_pid = os.getpid()
        with open(LOCK_FILE, "w") as f:
            f.write(str(current_pid))
        print(f"✅ Monitor de Notificaciones iniciado (PID: {current_pid})")
        return True
    except Exception as e:
        print(f"Error adquiriendo lock: {e}")
        return False

def release_lock():
    """Libera el lock."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except:
        pass

def open_notification():
    """Abre la ventana de notificación usando el navegador."""
    try:
        system = platform.system()
        
        # URLs posibles según el puerto
        url = "http://localhost:5000/show-notification"
        
        if system == "Windows":
            # Windows
            subprocess.Popen(["start", url], shell=True)
        elif system == "Darwin":
            # macOS
            subprocess.Popen(["open", url])
        else:
            # Linux - intentar con diferentes navegadores
            browsers = ["firefox", "chromium-browser", "chromium", "google-chrome", "google-chrome-stable"]
            opened = False
            for browser in browsers:
                try:
                    subprocess.Popen([browser, url])
                    opened = True
                    break
                except:
                    continue
            
            if not opened:
                # Fallback: xdg-open
                try:
                    subprocess.Popen(["xdg-open", url])
                    opened = True
                except:
                    pass
            
            if not opened:
                print(f"⚠️ No se pudo abrir el navegador. Visita: {url}")
        
        print(f"[+] Abriendo notificación en navegador...")
    except Exception as e:
        print(f"Error abriendo notificación: {e}")

def is_notification_processed(filename):
    """Verifica si una notificación ya fue procesada."""
    try:
        if os.path.exists(PROCESSED_FILE):
            with open(PROCESSED_FILE, "r") as f:
                processed = f.read().strip().split("\n")
            return filename in processed
    except:
        pass
    return False

def mark_as_processed(filename):
    """Marca una notificación como procesada."""
    try:
        with open(PROCESSED_FILE, "a") as f:
            f.write(filename + "\n")
    except:
        pass

def monitor_notifications():
    """Monitorea las notificaciones y abre alertas."""
    print("[*] Monitoreando notificaciones...")
    
    while True:
        try:
            # Verificar si existe archivo de notificación
            if os.path.exists(NOTIFICATION_FILE):
                # Verificar si ya fue procesada
                if not is_notification_processed("current"):
                    print("[+] Notificación detectada!")
                    open_notification()
                    mark_as_processed("current")
                    
                    # Esperar a que se procese
                    time.sleep(2)
            
            # Limpiar archivo procesado ocasionalmente para permitir múltiples notificaciones
            if os.path.exists(NOTIFICATION_FILE):
                try:
                    os.remove(NOTIFICATION_FILE)
                except:
                    pass
            
            time.sleep(0.5)
        
        except KeyboardInterrupt:
            print("\n[!] Monitor detenido por usuario")
            break
        except Exception as e:
            print(f"[!] Error en monitor: {e}")
            time.sleep(1)

if __name__ == "__main__":
    if not acquire_lock():
        exit(1)
    
    try:
        monitor_notifications()
    finally:
        release_lock()
