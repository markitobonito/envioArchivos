#!/usr/bin/env python3
"""
Monitor de videos que respeta los flags en el nombre del archivo:
- video.mp4              → Reproducir Ahora (inmediato)
- video.mp4.SILENT       → Solo Descargar (no abre)
- video.mp4.SCHED_14:30_mon,wed → Programar para 14:30 en esos días
"""
import os
import time
import subprocess
import platform
from datetime import datetime

# Detectar carpeta de descargas
HOME = os.path.expanduser("~")
DOWNLOADS_DIR = os.path.join(HOME, "Descargas") if os.path.isdir(os.path.join(HOME, "Descargas")) else os.path.join(HOME, "Downloads")

# Archivo para rastrear videos ya procesados
PROCESSED_FILE = "/tmp/video-monitor-processed.txt"
LOCK_FILE = "/tmp/video-monitor.lock"

VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.m4v', '.ts', '.m3u8'}

def acquire_lock():
    """Asegura que solo corra una instancia"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            if os.path.exists(f"/proc/{pid}"):
                return False  # Ya hay otra instancia
        except:
            pass
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    return True

def release_lock():
    """Libera el lock"""
    try:
        os.remove(LOCK_FILE)
    except:
        pass

def is_video(filename):
    """Verifica si es un archivo de video (sin contar los flags)"""
    # Eliminar flags antes de revisar extensión
    base_name = filename.split('.SILENT')[0].split('.SCHED_')[0]
    ext = os.path.splitext(base_name)[1].lower()
    return ext in VIDEO_EXTENSIONS

def open_video(filepath):
    """Abre video con el reproductor por defecto"""
    filename = os.path.basename(filepath)
    print(f"🎬 Abriendo: {filename}")
    
    try:
        if platform.system() == "Linux":
            subprocess.Popen(['xdg-open', filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif platform.system() == "Darwin":
            subprocess.Popen(['open', filepath])
        elif platform.system() == "Windows":
            subprocess.Popen(['start', '', filepath], shell=True)
    except Exception as e:
        print(f"❌ Error abriendo video: {e}")

def should_play_scheduled(filename):
    """
    Verifica si un video programado debe reproducirse ahora.
    Formato: video.mp4.SCHED_14:30_monday,wednesday
    """
    if '.SCHED_' not in filename:
        return False
    
    try:
        # Extraer tiempo y días: "video.mp4.SCHED_14:30_mon,wed"
        parts = filename.split('.SCHED_')[1].split('_', 1)
        scheduled_time = parts[0]  # "14:30"
        scheduled_days = parts[1] if len(parts) > 1 else ""  # "mon,wed"
        
        # Obtener hora actual
        now = datetime.now()
        current_time = now.strftime('%H:%M')
        day_num = now.weekday()
        days_en = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        current_day = days_en[day_num]
        
        # Comparar
        if current_time == scheduled_time:
            # Verificar si el día coincide (permite abreviaturas)
            if current_day in scheduled_days or current_day[:3] in scheduled_days:
                return True
    except:
        pass
    
    return False

def get_processed_videos():
    """Lee videos ya procesados"""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def mark_as_processed(video_id):
    """Marca un video como procesado"""
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{video_id}\n")

def monitor_videos():
    """Monitorea la carpeta de descargas"""
    print(f"📁 Monitoreando: {DOWNLOADS_DIR}")
    print("⏳ Esperando videos nuevos...")
    print("")
    
    processed = get_processed_videos()
    
    while True:
        try:
            if not os.path.isdir(DOWNLOADS_DIR):
                time.sleep(2)
                continue
            
            for filename in os.listdir(DOWNLOADS_DIR):
                # Ignorar archivos especiales
                if filename.endswith('.PLAYED_') or filename.startswith('.'):
                    continue
                
                filepath = os.path.join(DOWNLOADS_DIR, filename)
                if not os.path.isfile(filepath):
                    continue
                
                # Verificar si es un video
                if not is_video(filename):
                    continue
                
                # ID único: nombre + tamaño
                file_size = os.path.getsize(filepath)
                video_id = f"{filename}:{file_size}"
                
                # Si ya fue procesado, revisar si es programado y debe reproducirse
                if video_id in processed:
                    if '.SCHED_' in filename and should_play_scheduled(filename):
                        # Renombrar para marcar como reproducido
                        new_name = filename.replace('.SCHED_', '.PLAYED_')
                        new_path = os.path.join(DOWNLOADS_DIR, new_name)
                        try:
                            os.rename(filepath, new_path)
                            open_video(new_path)
                        except:
                            pass
                    continue
                
                # Nuevo video detectado
                time.sleep(2)  # Esperar a que termine de escribirse
                
                if not os.path.exists(filepath):
                    continue
                
                print(f"📥 Video nuevo: {filename}")
                
                # Procesar según el flag
                if '.SILENT' in filename:
                    print(f"🤐 Solo descargado (sin reproducción)")
                elif '.SCHED_' in filename:
                    scheduled_time = filename.split('.SCHED_')[1].split('_')[0]
                    scheduled_days = filename.split('_', 1)[1] if '_' in filename.split('.SCHED_')[1] else ""
                    print(f"📌 Programado para {scheduled_time} ({scheduled_days})")
                else:
                    # Reproducir ahora
                    print(f"▶️ Reproduciendo ahora")
                    open_video(filepath)
                
                mark_as_processed(video_id)
                processed.add(video_id)
            
            time.sleep(2)
        
        except KeyboardInterrupt:
            print("\n✓ Monitor detenido")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    if not acquire_lock():
        print("❌ Monitor ya ejecutándose")
        exit(1)
    
    try:
        monitor_videos()
    finally:
        release_lock()

