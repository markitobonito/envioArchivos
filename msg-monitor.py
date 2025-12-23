#!/usr/bin/env python3
"""
Monitor de archivos .msg en Descargas.
Detecta archivos nuevos y los lee en voz alta automáticamente.
"""
import os
import time
import subprocess
import platform
from pathlib import Path
from datetime import datetime

def get_downloads_folder():
    """Obtiene la carpeta de descargas del usuario"""
    home = os.path.expanduser("~")
    
    # Opción 1: Descargas (español)
    if os.path.exists(os.path.join(home, "Descargas")):
        return os.path.join(home, "Descargas")
    
    # Opción 2: Downloads (inglés)
    if os.path.exists(os.path.join(home, "Downloads")):
        return os.path.join(home, "Downloads")
    
    # Fallback
    return os.path.join(home, "Downloads")

def log_message(msg):
    """Escribe en log con timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {msg}"
    print(log_entry, flush=True)
    
    # También escribir en archivo de log
    with open("/tmp/msg-monitor.log", "a") as f:
        f.write(log_entry + "\n")

def speak_message(message, repetitions=1):
    """Lee el mensaje en voz alta según el SO"""
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            for i in range(repetitions):
                subprocess.run(["say", "-v", "es", message], timeout=30)
                log_message(f"[🔊] macOS TTS: '{message}' ({i+1}/{repetitions})")
        
        elif system == "Linux":
            for i in range(repetitions):
                try:
                    subprocess.run(["espeak-ng", "-v", "es", message], timeout=30, check=True)
                    log_message(f"[🔊] Linux espeak-ng: '{message}' ({i+1}/{repetitions})")
                except (FileNotFoundError, subprocess.CalledProcessError):
                    subprocess.run(["espeak", "-v", "es", message], timeout=30)
                    log_message(f"[🔊] Linux espeak: '{message}' ({i+1}/{repetitions})")
        
        elif system == "Windows":
            ps_script = f"""Add-Type –AssemblyName System.Speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
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
    """Procesa un archivo .msg"""
    try:
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
        
        log_message(f"[📬] Archivo .msg: {os.path.basename(filepath)}")
        log_message(f"[📝] Contenido: {repetitions}x '{message}'")
        
        # Reproducir en voz alta
        speak_message(message, repetitions)
        
        # Renombrar a .done para no procesarlo otra vez
        processed_file = filepath.replace(".msg", ".msg.done")
        os.rename(filepath, processed_file)
        log_message(f"[✅] Procesado: {os.path.basename(processed_file)}")
    
    except Exception as e:
        log_message(f"[❌] Error: {e}")

def monitor_downloads():
    """Monitorea la carpeta Descargas por archivos .msg"""
    downloads_path = get_downloads_folder()
    processed_files = set()
    
    log_message(f"[*] Monitor iniciado en: {downloads_path}")
    log_message(f"[*] Vigilando archivos .msg...")
    
    while True:
        try:
            # Buscar archivos .msg sin procesar
            for filename in os.listdir(downloads_path):
                if filename.endswith(".msg") and not filename.endswith(".msg.done"):
                    filepath = os.path.join(downloads_path, filename)
                    
                    # Evitar procesar el mismo archivo 2 veces
                    if filepath not in processed_files:
                        # Esperar a que se complete la escritura (2 segundos)
                        time.sleep(2)
                        
                        if os.path.exists(filepath):
                            processed_files.add(filepath)
                            process_msg_file(filepath)
            
            # Limpiar archivos procesados muy antiguos (más de 1 hora)
            cutoff_time = time.time() - 3600
            for filename in os.listdir(downloads_path):
                if filename.endswith(".msg.done"):
                    filepath = os.path.join(downloads_path, filename)
                    try:
                        if os.path.getmtime(filepath) < cutoff_time:
                            os.remove(filepath)
                    except:
                        pass
            
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
