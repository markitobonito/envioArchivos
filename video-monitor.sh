#!/bin/bash
# Script que monitorea la carpeta de descargas y abre videos automáticamente
# También maneja videos programados según su horario

# Detectar carpeta de descargas
if [ -d "$HOME/Descargas" ]; then
    DOWNLOADS_DIR="$HOME/Descargas"
else
    DOWNLOADS_DIR="$HOME/Downloads"
fi

echo "📁 Monitoreando carpeta: $DOWNLOADS_DIR"
echo "⏳ Esperando videos nuevos..."
echo ""
echo "Presiona Ctrl+C para detener"

# Archivo para guardar timestamps de videos procesados
PROCESSED_FILE="/tmp/video-monitor-processed.txt"
touch "$PROCESSED_FILE"

# Función para abrir video
open_video() {
    local video_path="$1"
    local filename=$(basename "$video_path")
    
    echo "🎬 Abriendo video en pantalla completa: $filename"
    
    # Detectar aplicación de video disponible
    if command -v mpv &> /dev/null; then
        mpv --fullscreen "$video_path" &
    elif command -v vlc &> /dev/null; then
        vlc --fullscreen "$video_path" &
    elif command -v firefox &> /dev/null; then
        firefox "$video_path" &
    elif command -v xdg-open &> /dev/null; then
        xdg-open "$video_path" &
    else
        xdg-open "$video_path" 2>/dev/null || echo "No se encontró reproductor de video"
    fi
}

# Función para verificar si debe reproducirse según el horario
should_play_now() {
    local schedule_file="$1"
    
    if [ ! -f "$schedule_file" ]; then
        return 1  # No hay programación
    fi
    
    # Leer tiempo y días programados
    local scheduled_time=$(grep -o '"time":"[^"]*' "$schedule_file" | cut -d'"' -f4)
    local scheduled_days=$(grep -o '"days":\s*\[[^]]*\]' "$schedule_file" | grep -o '"[^"]*"' | tr -d '":')
    
    # Obtener hora y día actual
    local current_time=$(date +%H:%M)
    local current_day=$(date +%A | tr '[:upper:]' '[:lower:]')
    
    # Mapear día inglés a español para comparación
    case "$current_day" in
        monday) current_day="monday" ;;
        tuesday) current_day="tuesday" ;;
        wednesday) current_day="wednesday" ;;
        thursday) current_day="thursday" ;;
        friday) current_day="friday" ;;
        saturday) current_day="saturday" ;;
        sunday) current_day="sunday" ;;
    esac
    
    # Verificar si coinciden hora y día
    if [ "$current_time" = "$scheduled_time" ] && echo "$scheduled_days" | grep -q "$current_day"; then
        return 0  # Sí, reproducir ahora
    fi
    
    return 1  # No, no reproducir
}

# Monitorear cambios
while true; do
    if [ -d "$DOWNLOADS_DIR" ]; then
        # Buscar todos los videos
        find "$DOWNLOADS_DIR" -maxdepth 1 -type f \( -iname "*.mp4" -o -iname "*.webm" -o -iname "*.mkv" -o -iname "*.avi" -o -iname "*.mov" -o -iname "*.flv" -o -iname "*.m4v" -o -iname "*.ts" -o -iname "*.m3u8" \) | while read video_file; do
            filename=$(basename "$video_file")
            
            # Obtener timestamp del archivo
            mtime=$(stat -c %Y "$video_file" 2>/dev/null || stat -f %m "$video_file" 2>/dev/null || echo 0)
            file_id="${filename}:${mtime}"
            
            # Verificar si tiene programación
            schedule_file="${video_file}.schedule.json"
            
            # Si no está en el registro de procesados
            if ! grep -q "^${file_id}$" "$PROCESSED_FILE" 2>/dev/null; then
                echo "$file_id" >> "$PROCESSED_FILE"
                
                # Esperar a que termine de escribirse
                sleep 2
                
                if [ -f "$video_file" ]; then
                    # Si tiene programación, verificar horario
                    if [ -f "$schedule_file" ]; then
                        if should_play_now "$schedule_file"; then
                            echo "⏰ Es hora de reproducir: $filename"
                            open_video "$video_file"
                        else
                            echo "📌 Video programado guardado: $filename"
                        fi
                    else
                        # Sin programación, reproducir automáticamente
                        open_video "$video_file"
                    fi
                fi
            else
                # Video ya fue procesado, pero verificar si es hora de reproducción programada
                schedule_file="${video_file}.schedule.json"
                if [ -f "$schedule_file" ]; then
                    # Marca para saber si ya se reprodujo hoy
                    played_file="/tmp/video-played-$(md5sum <<< "$video_file" | cut -d' ' -f1).txt"
                    
                    if should_play_now "$schedule_file" && [ ! -f "$played_file" ]; then
                        echo "⏰ Reproduciendo video programado: $filename"
                        open_video "$video_file"
                        touch "$played_file"
                        # Limpiar marca al día siguiente
                        echo "0 0 * * * rm -f $played_file" | crontab - 2>/dev/null || true
                    fi
                fi
            fi
        done
    fi
    
    sleep 2
done
