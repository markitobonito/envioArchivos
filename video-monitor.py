#!/usr/bin/env python3
"""
Monitor de videos inteligente que respeta la programación.
- Abre videos "Reproducir Ahora" inmediatamente
- Abre videos "Programar Reproducción" solo a la hora exacta
- No abre videos "Solo Descargar"
"""
import os
import json
import time
import subprocess
import platform
from datetime import datetime
from pathlib import Path

# Detectar carpeta de descargas
HOME = os.path.expanduser("~")
if os.path.isdir(os.path.join(HOME, "Descargas")):
    DOWNLOADS_DIR = os.path.join(HOME, "Descargas")
else:
    DOWNLOADS_DIR = os.path.join(HOME, "Downloads")

# Archivo para registrar videos ya procesados
PROCESSED_FILE = "/tmp/video-monitor-processed.txt"

VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.m4v', '.ts', '.m3u8'}

def get_processed_videos():
    """Leer videos ya procesados"""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def mark_as_processed(video_id):
    """Marcar video como procesado"""
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{video_id}\n")

def mark_as_played(video_path):
    """Marcar video como reproducido hoy"""
    played_file = f"/tmp/video-played-{os.path.basename(video_path)}.txt"
    Path(played_file).touch()

def was_played_today(video_path):
    """Verificar si se reprodujo hoy"""
    played_file = f"/tmp/video-played-{os.path.basename(video_path)}.txt"
    if not os.path.exists(played_file):
        return False
    # Verificar que fue creado hoy
    return (datetime.now() - datetime.fromtimestamp(os.path.getmtime(played_file))).days == 0

def open_video(video_path):
    """Abrir video con el reproductor disponible"""
    filename = os.path.basename(video_path)
    print(f"🎬 Abriendo video: {filename}")
    
    try:
        if platform.system() == "Linux":
            # En Linux, VLC en fullscreen
            subprocess.Popen(['vlc', '--fullscreen', video_path], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
        elif platform.system() == "Darwin":  # macOS
            subprocess.Popen(['open', video_path])
        elif platform.system() == "Windows":
            subprocess.Popen(['start', '', video_path], shell=True)
    except Exception as e:
        print(f"Error abriendo video: {e}")

def get_video_action(video_path):
    """
    Leer la acción programada para el video.
    Retorna: ('now', None, None) | ('schedule', time, days) | ('silent', None, None)
    """
    schedule_file = f"{video_path}.schedule.json"
    
    if not os.path.exists(schedule_file):
        # Sin archivo de programación = reproducir ahora (comportamiento por defecto)
        return ('now', None, None)
    
    try:
        with open(schedule_file, 'r') as f:
            data = json.load(f)
        
        action = data.get('action', 'now')
        
        if action == 'schedule':
            scheduled_time = data.get('time', '')  # HH:MM
            scheduled_days = data.get('days', [])  # ['monday', 'wednesday', ...]
            return ('schedule', scheduled_time, scheduled_days)
        elif action == 'silent':
            return ('silent', None, None)
        else:  # 'now' o default
            return ('now', None, None)
    except Exception as e:
        print(f"Error leyendo {schedule_file}: {e}")
        return ('now', None, None)

def should_play_scheduled_now(scheduled_time, scheduled_days):
    """Verificar si es hora de reproducir un video programado"""
    now = datetime.now()
    current_time = now.strftime('%H:%M')
    
    # Obtener día actual en inglés (0=Monday, 6=Sunday)
    day_num = now.weekday()
    days_en = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    current_day = days_en[day_num]
    
    # Verificar si coincide hora y día
    if current_time == scheduled_time and current_day in scheduled_days:
        return True
    
    return False

def monitor_videos():
    """Monitorear cambios en la carpeta de videos"""
    print(f"📁 Monitoreando: {DOWNLOADS_DIR}")
    print("⏳ Esperando videos nuevos...")
    print("")
    
    processed = get_processed_videos()
    
    while True:
        try:
            if os.path.isdir(DOWNLOADS_DIR):
                # Encontrar todos los videos
                for filename in os.listdir(DOWNLOADS_DIR):
                    if filename.endswith('.schedule.json'):
                        continue  # Ignorar archivos de programación
                    
                    filepath = os.path.join(DOWNLOADS_DIR, filename)
                    
                    # Verificar si es video
                    if not os.path.isfile(filepath):
                        continue
                    
                    ext = os.path.splitext(filename)[1].lower()
                    if ext not in VIDEO_EXTENSIONS:
                        continue
                    
                    # Crear ID único basado en nombre y tamaño
                    file_size = os.path.getsize(filepath)
                    video_id = f"{filename}:{file_size}"
                    
                    # Si ya fue procesado, revisar si es hora de reproducción programada
                    if video_id in processed:
                        action, sched_time, sched_days = get_video_action(filepath)
                        
                        if action == 'schedule' and sched_time and sched_days:
                            # Verificar si es hora y no se reprodujo hoy
                            if should_play_scheduled_now(sched_time, sched_days) and not was_played_today(filepath):
                                print(f"⏰ Reproduciendo video programado: {filename}")
                                open_video(filepath)
                                mark_as_played(filepath)
                        continue
                    
                    # Nuevo video detectado
                    print(f"📥 Video nuevo: {filename}")
                    
                    # Esperar a que se escriba completamente
                    time.sleep(2)
                    
                    if os.path.exists(filepath):
                        action, sched_time, sched_days = get_video_action(filepath)
                        
                        if action == 'now':
                            print(f"▶ Reproducir Ahora: {filename}")
                            open_video(filepath)
                        elif action == 'schedule':
                            print(f"📌 Video programado para {sched_time} en {', '.join(sched_days)}: {filename}")
                        elif action == 'silent':
                            print(f"🤐 Descargado en silencio: {filename}")
                        
                        mark_as_processed(video_id)
                        processed.add(video_id)
            
            time.sleep(2)
        
        except KeyboardInterrupt:
            print("\n✓ Monitor detenido")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    monitor_videos()
