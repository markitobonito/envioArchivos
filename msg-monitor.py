#!/usr/bin/env python3
"""
Monitor de archivos .msg en Descargas.
Solo procesa ARCHIVOS NUEVOS que llegan.
Ejecuta TTS, notificación y elimina el archivo.
"""
import os
import time
import subprocess
import platform
from datetime import datetime

def get_downloads_folder():
    """Obtiene la carpeta de descargas del usuario"""
    home = os.path.expanduser("~")
    
    if os.path.exists(os.path.join(home, "Descargas")):
        return os.path.join(home, "Descargas")
    elif os.path.exists(os.path.join(home, "Downloads")):
        return os.path.join(home, "Downloads")
    
    return os.path.join(home, "Downloads")

def log_message(msg):
    """Escribe en log con timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {msg}"
    print(log_entry, flush=True)
    
    with open("/tmp/msg-monitor.log", "a") as f:
        f.write(log_entry + "\n")

def show_notification(title, message):
    """Muestra notificación del SO"""
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], timeout=5)
            log_message(f"[📢] Notificación macOS mostrada")
        
        elif system == "Linux":
            subprocess.run(
                ["notify-send", "-u", "critical", "-t", "5000", title, message],
                timeout=5
            )
            log_message(f"[📢] Notificación Linux mostrada")
        
        elif system == "Windows":
            ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$APP_ID = 'AlertasTTS'
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
            subprocess.run(["powershell", "-Command", ps_script], timeout=5)
            log_message(f"[📢] Notificación Windows mostrada")
    
    except Exception as e:
        log_message(f"[!] Error notificación: {e}")

def speak_message(message, repetitions=1):
    """Lee el mensaje en voz alta con máxima calidad"""
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            for i in range(repetitions):
                subprocess.run(
                    ["say", "-v", "es", message],
                    timeout=30
                )
                log_message(f"[🔊] macOS: '{message}' ({i+1}/{repetitions})")
        
        elif system == "Linux":
            for i in range(repetitions):
                try:
                    # Usar espeak-ng con mbrola para mejor calidad
                    subprocess.run(
                        ["espeak-ng", "-v", "es+mbrola-es1", "-a", "200", message],
                        timeout=30,
                        check=True
                    )
                    log_message(f"[🔊] Linux espeak-ng+mbrola: '{message}' ({i+1}/{repetitions})")
                except (FileNotFoundError, subprocess.CalledProcessError):
                    # Fallback sin mbrola
                    try:
                        subprocess.run(
                            ["espeak-ng", "-v", "es", "-a", "200", message],
                            timeout=30
                        )
                        log_message(f"[🔊] Linux espeak-ng: '{message}' ({i+1}/{repetitions})")
                    except FileNotFoundError:
                        # Último recurso: espeak antiguo
                        subprocess.run(
                            ["espeak", "-v", "es", message],
                            timeout=30
                        )
                        log_message(f"[🔊] Linux espeak: '{message}' ({i+1}/{repetitions})")
        
        elif system == "Windows":
            ps_script = f"""Add-Type –AssemblyName System.Speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speak.Volume = 100
$speak.Rate = 0
$speak.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSpecified, [System.Speech.Synthesis.VoiceAge]::NotSpecified, 0, [System.Globalization.CultureInfo]'es-ES')
for ($i = 0; $i -lt {repetitions}; $i++) {{
    $speak.Speak(\"{message}\")
}}
"""
            subprocess.run(["powershell", "-Command", ps_script], timeout=30)
            log_message(f"[🔊] Windows TTS: '{message}' ({repetitions}x)")
    
    except Exception as e:
        log_message(f"[❌] Error TTS: {e}")

def process_msg_file(filepath):
    """Procesa un archivo .msg y lo elimina"""
    try:
        log_message(f"[📬] Archivo .msg detectado: {os.path.basename(filepath)}")
        
        # Leer contenido
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        
        # Parsear formato: repeticiones|mensaje
        parts = content.split("|", 1)
        if len(parts) == 2:
            try:
                repetitions = int(parts[0].strip())
                message = parts[1].strip()
            except ValueError:
                repetitions = 1
                message = content
        else:
            repetitions = 1
            message = content
        
        log_message(f"[📝] Contenido: {repetitions}x '{message}'")
        
        # Mostrar notificación
        show_notification("🚨 ALERTA URGENTE", message)
        
        # Reproducir en voz alta
        speak_message(message, repetitions)
        
        # Eliminar archivo
        try:
            os.remove(filepath)
            log_message(f"[🗑️] Archivo eliminado")
        except Exception as e:
            log_message(f"[!] Error eliminando archivo: {e}")
    
    except Exception as e:
        log_message(f"[❌] Error procesando: {e}")

def monitor_downloads():
    """Monitorea la carpeta Descargas por NUEVOS archivos .msg"""
    downloads_path = get_downloads_folder()
    previous_files = set()
    
    log_message(f"[*] Monitor iniciado en: {downloads_path}")
    log_message(f"[*] Escuchando archivos .msg nuevos...")
    
    # Obtener archivos existentes al iniciar (no procesarlos)
    try:
        for filename in os.listdir(downloads_path):
            if filename.endswith(".msg"):
                previous_files.add(filename)
        log_message(f"[*] Ignorando {len(previous_files)} archivos .msg existentes")
    except:
        pass
    
    while True:
        try:
            # Buscar SOLO archivos nuevos
            current_files = set()
            for filename in os.listdir(downloads_path):
                if filename.endswith(".msg"):
                    current_files.add(filename)
            
            # Detectar archivos NUEVOS (que no estaban antes)
            new_files = current_files - previous_files
            
            for filename in new_files:
                filepath = os.path.join(downloads_path, filename)
                
                # Esperar a que se complete la escritura
                time.sleep(1)
                
                if os.path.exists(filepath):
                    process_msg_file(filepath)
            
            previous_files = current_files
            time.sleep(1)  # Revisar cada segundo
        
        except Exception as e:
            log_message(f"[⚠️] Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Limpiar log anterior
    try:
        os.remove("/tmp/msg-monitor.log")
    except:
        pass
    
    log_message("=" * 60)
    log_message("MONITOR DE ARCHIVOS .MSG INICIADO")
    log_message("=" * 60)
    
    monitor_downloads()

