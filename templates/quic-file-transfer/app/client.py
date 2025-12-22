import os
import json
import asyncio
import threading
import subprocess
import requests
from flask import Flask, request, redirect, render_template, flash
from aioquic.asyncio import connect, serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
import socket
import platform
import time

def show_native_notification(title: str, message: str, duration: int = 10):
    """
    Muestra una notificación nativa del SO (Windows/Linux/macOS).
    La notificación desaparece automáticamente después de `duration` segundos.
    
    Args:
        title: Título de la notificación
        message: Contenido del mensaje
        duration: Segundos que durará la notificación (aprox.)
    """
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            # Usar osascript para notificaciones nativas macOS
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            print(f"[+] Notificación macOS mostrada")
            
        elif system == "Windows":
            # Usar PowerShell para Windows Toast notifications
            ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
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
            print(f"[+] Notificación Windows mostrada")
            
        elif system == "Linux":
            # Usar notify-send para Linux
            subprocess.run(
                ["notify-send", "-u", "critical", "-t", str(duration * 1000), title, message],
                check=True,
                capture_output=True
            )
            print(f"[+] Notificación Linux mostrada")
            
    except Exception as e:
        print(f"[-] Error mostrando notificación nativa: {e}")
        print(f"    Sistema: {system}")


def get_downloads_folder():
    """
    Detecta la carpeta de descargas correcta según el SO e idioma.
    Prioridad:
    1. Si existe ~/Descargas → usar esa
    2. Si existe ~/Downloads → usar esa
    3. Si ninguna existe → crear ~/Descargas
    """
    home = os.path.expanduser("~")
    
    # Opción 1: Intentar Descargas primero (español)
    descargas_path = os.path.join(home, "Descargas")
    if os.path.exists(descargas_path) and os.path.isdir(descargas_path):
        return descargas_path
    
    # Opción 2: Intentar Downloads (inglés)
    downloads_path = os.path.join(home, "Downloads")
    if os.path.exists(downloads_path) and os.path.isdir(downloads_path):
        return downloads_path
    
    # Opción 3: Crear Descargas si ninguna existe
    os.makedirs(descargas_path, exist_ok=True)
    return descargas_path

# ...existing code...

class FileServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._files = {}
        self._names = {}
        self._received = {}

    def show_native_notification(self, title, message, duration=8):
        system = platform.system()
        try:
            if system == "Darwin":
                script = f'display notification "{message}" with title "{title}"'
                subprocess.run(["osascript", "-e", script])
            elif system == "Windows":
                ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$APP_ID = 'QuicFileTransfer'
$template = @"
<toast>
    <visual>
        <binding template=\"ToastText02\">
            <text id=\"1\">{title}</text>
            <text id=\"2\">{message}</text>
        </binding>
    </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($APP_ID).Show($toast)
"""
                subprocess.run(["powershell", "-Command", ps_script])
            elif system == "Linux":
                subprocess.run(["notify-send", "-u", "critical", "-t", str(duration * 1000), title, message])
        except Exception as e:
            print("Error mostrando notificación:", e)

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            stream_id = event.stream_id
            data = event.data
            length = len(data)
            
            print(f"[DEBUG QUIC] Stream {stream_id}: recibido {len(data)} bytes, end_stream={event.end_stream}")
            print(f"[DEBUG QUIC] Primeros 50 bytes: {data[:50]}")

            # NOTIFICACIÓN: Si empieza con MSG: directamente
            if data.startswith(b"MSG:"):
                print(f"[🚨 DETECTADO NOTIFICACIÓN]")
                message = data[4:].decode("utf-8", errors="ignore").strip()  # Saltar "MSG:"
                print(f"[✅ MENSAJE RECIBIDO] {message}")
                
                # Guardar en archivo
                try:
                    notification_file = "/tmp/notification.txt"
                    with open(notification_file, "w", encoding="utf-8") as f:
                        f.write(message)
                    print(f"[✅] Guardado en {notification_file}")
                except Exception as e:
                    print(f"[❌] Error guardando: {e}")
                
                # Mostrar notificación nativa
                try:
                    self.show_native_notification("🚨 ALERTA URGENTE", message, 8)
                except Exception as e:
                    print(f"[!] Error notificación nativa: {e}")
                
                return  # Importante: retornar aquí para no procesarlo como archivo

            # ARCHIVO: protocolo normal con \0 separator
            if stream_id not in self._names:
                if not hasattr(self, '_tmp'):
                    self._tmp = {}
                if stream_id not in self._tmp:
                    self._tmp[stream_id] = b""
                self._tmp[stream_id] += data

                if b"\0" in self._tmp[stream_id]:
                    header, first_chunk = self._tmp[stream_id].split(b"\0", 1)
                    header_str = header.decode("utf-8", errors="ignore").strip()
                    
                    print(f"[ARCHIVO] Header: {header_str}")
                    
                    filename = header_str
                    self._names[stream_id] = filename
                    self._received[stream_id] = 0

                    download_dir = get_downloads_folder()
                    full_path = os.path.join(download_dir, filename)
                    print(f"Iniciando descarga -> {filename}")

                    f = open(full_path, "wb")
                    if first_chunk:
                        f.write(first_chunk)
                        f.flush()
                    self._files[stream_id] = f
                    del self._tmp[stream_id]
                return

            # Continuar recibiendo datos del archivo
            if stream_id in self._files:
                self._files[stream_id].write(data)
                self._files[stream_id].flush()
                self._received[stream_id] += length

                if self._received[stream_id] % (100 * 1024 * 1024) < length:
                    print(f"  {self._names[stream_id]} -> {self._received[stream_id]/(1024**3):.2f} GB recibidos")

            self.transmit()

            if event.end_stream:
                if stream_id in self._files:
                    f = self._files.pop(stream_id)
                    os.fsync(f.fileno())
                    f.close()
                    filename = self._names.pop(stream_id)
                    download_dir = get_downloads_folder()
                    full_path = os.path.join(download_dir, filename)
                    
                    try:
                        os.chmod(full_path, 0o666)
                        print(f"[+] Permisos ajustados: {full_path}")
                    except Exception as e:
                        print(f"[-] Error permisos: {e}")
                    
                    try:
                        import pwd
                        current_user = pwd.getpwuid(os.getuid()).pw_uid
                        file_stat = os.stat(full_path)
                        if file_stat.st_uid != current_user:
                            os.chown(full_path, current_user, -1)
                            print(f"[+] Propietario cambiado")
                    except Exception as e:
                        pass
                    
                    total_gb = self._received.pop(stream_id, 0) / (1024**3)
                    print(f"COMPLETADO -> {filename} ({total_gb:.2f} GB)")

async def run_quic_server():
    print("[*] Iniciando servidor QUIC...")
    config = QuicConfiguration(
        is_client=False,
        alpn_protocols=["quic-file"],
        idle_timeout=1800,
        max_data=20 * 1024**3,
        max_stream_data=20 * 1024**3
    )
    config.load_cert_chain("certs/cert.pem", "certs/key.pem")
    print("[+] Servidor QUIC escuchando en 0.0.0.0:9999")
    await serve("0.0.0.0", 9999, configuration=config, create_protocol=FileServerProtocol)
    await asyncio.Event().wait()

app = Flask(__name__)
app.secret_key = "multicast-secret"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

config_client = QuicConfiguration(
    is_client=True,
    alpn_protocols=["quic-file"],
)
config_client.verify_mode = False
config_client.idle_timeout = 600.0
config_client.max_data = 1024 * 1024 * 1024
config_client.max_stream_data = 1024 * 1024 * 1024

def get_tailscale_ips():
    # First, try to read a pre-generated status file (written by the host) to avoid
    # requiring the container to talk to tailscaled directly. This allows a simple
    # host-side command like:
    #   tailscale status --json > templates/quic-file-transfer/app/tailscale_status.json
    # The container mounts ./app to /app so we look for /app/tailscale_status.json here.
    status_path = os.environ.get("TAILSCALE_STATUS_PATH", "/app/tailscale_status.json")
    if os.path.exists(status_path):
        try:
            # Read raw bytes and detect BOM/encoding. Some hosts (Windows tailscale.exe)
            # may emit UTF-16-LE JSON (starts with 0xFF 0xFE). Try to detect and
            # decode appropriately to avoid UnicodeDecodeError in the container.
            with open(status_path, "rb") as fh:
                raw = fh.read()
            # Detect BOM for UTF-16/UTF-32; fall back to utf-8
            encoding = None
            if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
                encoding = "utf-16"
            elif raw.startswith(b"\xff\xfe\x00\x00") or raw.startswith(b"\x00\x00\xfe\xff"):
                encoding = "utf-32"
            else:
                # try utf-8 first, then utf-16 as fallback
                encoding = "utf-8"

            try:
                text = raw.decode(encoding)
            except Exception:
                # fallback to utf-16 if utf-8 failed
                try:
                    text = raw.decode("utf-16")
                except Exception as e:
                    print("get_tailscale_ips: failed to decode status file:", repr(e))
                    text = None

            if text is not None:
                data = json.loads(text)
            else:
                data = None
        except Exception as e:
            print("get_tailscale_ips: failed to read status file:", repr(e))
            data = None
        if data:
            try:
                self_ips = set(data.get("Self", {}).get("TailscaleIPs", []))
                peers = []
                for info in data.get("Peer", {}).values():
                    if info.get("Online", False):
                        ips = info.get("TailscaleIPs", [])
                        if ips and ips[0] not in self_ips:
                            # Usar IP directamente (no DNS names - pueden fallar en contenedores)
                            peer_ip = ips[0]
                            peers.append(peer_ip)
                            hostname = info.get("HostName", "?")
                            print(f"[+] Peer detectado: {hostname} -> {peer_ip}")
                return peers
            except Exception as e:
                print("get_tailscale_ips: error parsing status file:", repr(e))

    try:
        result = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        self_ips = set(data.get("Self", {}).get("TailscaleIPs", []))
        peers = []
        for info in data.get("Peer", {}).values():
            if info.get("Online", False):
                ips = info.get("TailscaleIPs", [])
                if ips and ips[0] not in self_ips:
                    peers.append(ips[0])
        return peers
    except Exception as e:
        # show the error in the container logs so we can diagnose why tailscale is unavailable
        print("get_tailscale_ips error:", repr(e))
        # also print stderr/stdout if available
        try:
            if 'result' in locals():
                print("tailscale stdout:", result.stdout)
                print("tailscale stderr:", result.stderr)
        except Exception:
            pass
        return []

async def send_file_to_ip(ip: str, filepath: str):
    filename = os.path.basename(filepath)
    print(f"[>] Enviando '{filename}' a {ip} ...")
    try:
        print(f"[DEBUG] Intentando conectar QUIC a {ip}:9999")
        async with connect(ip, 9999, configuration=config_client) as client:
            print(f"[DEBUG] Conexión QUIC exitosa a {ip}")
            stream_id = client._quic.get_next_available_stream_id()
            header = filename.encode(errors="ignore") + b"\0"
            client._quic.send_stream_data(stream_id, header, end_stream=False)
            sent = 0
            report_step = 10 * 1024 * 1024
            next_report = report_step
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    client._quic.send_stream_data(stream_id, chunk, end_stream=False)
                    sent += len(chunk)
                    if sent % (1024 * 1024) == 0:
                        await asyncio.sleep(0)
                    if sent >= next_report:
                        print(f"[=] {ip} :: {sent/1024/1024:.1f} MB enviados")
                        next_report += report_step
            client._quic.send_stream_data(stream_id, b"", end_stream=True)
            print(f"[i] Esperando confirmación final del receptor para '{filename}'...")
            while True:
                try:
                    if client._quic._streams.get(stream_id) is None:
                        break
                    if (client._quic._loss.bytes_in_flight == 0 and
                        getattr(client._quic._streams.get(stream_id), "send_state", 0) in (3, 4)):
                        break
                except:
                    pass
                await asyncio.sleep(0.1)
            print(f"[+] COMPLETADO! '{filename}' enviado 100 % a {ip} (QUIC)")
            return
    except Exception as e:
        print(f"[!] Error QUIC a {ip}: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("[i] Intentando fallback TCP...")

    try:
        with socket.create_connection((ip, 9999), timeout=30) as s:
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 256 * 1024)
            except Exception:
                pass
            try:
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            s.sendall(filename.encode('utf-8', errors='ignore') + b'\x00')
            sent = 0
            report_step = 10 * 1024 * 1024
            next_report = report_step
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    s.sendall(chunk)
                    sent += len(chunk)
                    if sent >= next_report:
                        print(f"[=] {ip} :: {sent/1024/1024:.1f} MB enviados (TCP)")
                        next_report += report_step
        print(f"[+] COMPLETADO! '{filename}' enviado 100 % a {ip} (TCP fallback)")
    except Exception as tcp_e:
        print(f"[!] Error enviando '{filename}' por TCP a {ip}: {tcp_e}")

async def send_notification_quic(ip: str, message: str):
    """Envía una notificación de alerta a un peer vía QUIC - IGUAL QUE ARCHIVOS."""
    print(f"[🚨 ALERTA] Enviando vía QUIC a {ip}: {message[:50]}...")
    try:
        print(f"[DEBUG] Conectando QUIC a {ip}:9999...")
        async with connect(ip, 9999, configuration=config_client) as client:
            print(f"[DEBUG] Conexión QUIC exitosa a {ip}")
            
            # Usar stream_id obtenido igual que archivos
            stream_id = client._quic.get_next_available_stream_id()
            
            # Enviar con prefijo MSG: para que el servidor lo detecte
            notification_data = b"MSG:" + message.encode("utf-8")
            
            # Enviar en un solo chunk con end_stream=True (no es un stream continuo)
            client._quic.send_stream_data(stream_id, notification_data, end_stream=True)
            
            print(f"[✅] Notificación enviada vía QUIC a {ip}")
            return True
            
    except Exception as e:
        print(f"[❌] Error enviando notificación a {ip}: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("No seleccionaste archivo", "error")
            return redirect("/")
        
        # Obtener opciones de programación del video
        video_action = request.form.get("videoAction", "silent")  # now, schedule, silent
        video_time = request.form.get("videoTime", "")
        video_days = request.form.get("videoDays", "")
        
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        
        # Crear metadata del video si es un video
        filename_lower = file.filename.lower()
        is_video = any(filename_lower.endswith(ext) for ext in {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.m4v', '.ts', '.m3u8'})
        
        # Renombrar archivo con flag de acción si es un video
        if is_video:
            if video_action == "schedule" and video_time and video_days:
                # Renombrar con flag de programación: video.mp4.SCHED_14:30_mon,wed,fri
                new_filename = f"{file.filename}.SCHED_{video_time}_{video_days}"
                action_text = f"programado para {video_time}"
            elif video_action == "silent":
                # Renombrar con flag silent: video.mp4.SILENT
                new_filename = f"{file.filename}.SILENT"
                action_text = "descargándose silenciosamente"
            else:  # now (default)
                # Dejar nombre normal
                new_filename = file.filename
                action_text = "reproducirá al llegar"
            
            # Renombrar el archivo si es necesario
            if new_filename != file.filename:
                new_filepath = os.path.join(UPLOAD_FOLDER, new_filename)
                os.rename(filepath, new_filepath)
                filepath = new_filepath
        else:
            action_text = ""
        
        ips = get_tailscale_ips()
        print(f"[DEBUG INDEX] get_tailscale_ips() retornó: {ips}")
        
        if not ips:
            print("[!] No hay peers online")
            flash("No hay peers Tailscale online para enviar.", "error")
            return redirect("/")
        
        print(f"[+] Enviando a {len(ips)} peers: {ips}")
        for ip in ips:
            print(f"[THREAD] Iniciando hilo de envío para {ip}")
            threading.Thread(
                target=lambda ip=ip: asyncio.run(send_file_to_ip(ip, filepath)),
                daemon=True,
            ).start()
        
        flash(f"Archivo '{file.filename}' enviándose a {len(ips)} dispositivo(s). Video {action_text}.", "success")
        return redirect("/")
    return render_template("index.html")

# ...existing code...

@app.route("/video/<filename>")
def stream_video(filename):
    """
    Reproducir video mientras se descarga (HTTP Range Requests).
    Soporta: MP4, WebM, MKV, AVI, MOV, FLV, etc.
    """
    video_extensions = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.m3u8', '.ts', '.m4v'}
    
    if not any(filename.lower().endswith(ext) for ext in video_extensions):
        return "Not a video file", 400
    
    # Buscar en Descargas
    downloads_dir = get_downloads_folder()
    filepath = os.path.join(downloads_dir, filename)
    
    # Validar que el archivo existe y está en la carpeta de descargas
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        return "Video not found", 404
    
    # Obtener tamaño del archivo
    file_size = os.path.getsize(filepath)
    
    # Soportar HTTP Range requests para streaming
    range_header = request.headers.get('Range', None)
    
    if range_header:
        try:
            ranges = range_header.replace('bytes=', '').split('-')
            start = int(ranges[0]) if ranges[0] else 0
            end = int(ranges[1]) if ranges[1] else file_size - 1
            
            if start > end or start >= file_size:
                return "Invalid Range", 416
            
            def generate_video():
                with open(filepath, 'rb') as f:
                    f.seek(start)
                    bytes_to_read = end - start + 1
                    while bytes_to_read > 0:
                        chunk_size = min(65536, bytes_to_read)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                        bytes_to_read -= len(chunk)
            
            response = app.response_class(
                generate_video(),
                status=206,
                mimetype='video/mp4'
            )
            response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response.headers['Content-Length'] = end - start + 1
            response.headers['Accept-Ranges'] = 'bytes'
            return response
        except (ValueError, IndexError):
            pass
    
    def generate_full_video():
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                yield chunk
    
    response = app.response_class(
        generate_full_video(),
        status=200,
        mimetype='video/mp4'
    )
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Content-Length'] = file_size
    return response

@app.route("/watch/<filename>")
def watch_video(filename):
    """Página HTML para ver video en pantalla completa mientras se descarga."""
    video_extensions = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.m3u8', '.ts', '.m4v'}
    
    if not any(filename.lower().endswith(ext) for ext in video_extensions):
        return "Not a video file", 400
    
    downloads_dir = get_downloads_folder()
    filepath = os.path.join(downloads_dir, filename)
    
    if not os.path.exists(filepath):
        return "Video not found", 404
    
    file_size = os.path.getsize(filepath)
    file_size_mb = file_size / (1024 * 1024)
    
    mime_types = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.mkv': 'video/x-matroska',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
        '.flv': 'video/x-flv',
        '.m4v': 'video/x-m4v'
    }
    
    ext = os.path.splitext(filename)[1].lower()
    mime_type = mime_types.get(ext, 'video/mp4')
    
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
        <title>Reproduciendo: {filename}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            html, body {{ width: 100vw; height: 100vh; overflow: hidden; }}
            body {{ background: #000; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; flex-direction: column; height: 100vh; overflow: hidden; position: fixed; top: 0; left: 0; }}
            .video-container {{ flex: 1; display: flex; align-items: center; justify-content: center; position: absolute; width: 100vw; height: 100vh; top: 0; left: 0; }}
            video {{ width: 100vw; height: 100vh; object-fit: contain; display: block; }}
            video:fullscreen {{ width: 100vw; height: 100vh; }}
            .info {{ position: fixed; bottom: 20px; left: 20px; background: rgba(0,0,0,0.8); color: #fff; padding: 15px 20px; border-radius: 8px; font-size: 14px; z-index: 100; }}
            .info p {{ margin: 5px 0; }}
            .progress {{ width: 200px; height: 4px; background: rgba(255,255,255,0.3); border-radius: 2px; margin-top: 10px; overflow: hidden; }}
            .progress-bar {{ height: 100%; background: #4CAF50; width: 0%; transition: width 0.3s; }}
            .close-btn {{ position: fixed; top: 20px; right: 20px; background: rgba(0,0,0,0.8); color: #fff; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; font-size: 14px; z-index: 200; font-weight: bold; }}
            .close-btn:hover {{ background: rgba(0,0,0,0.95); }}
            .fullscreen-btn {{ position: fixed; bottom: 20px; right: 20px; background: rgba(0,0,0,0.8); color: #fff; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; font-size: 14px; z-index: 100; }}
            .fullscreen-btn:hover {{ background: rgba(0,0,0,0.95); }}
            .fullscreen-prompt {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.95); color: #fff; padding: 40px; border-radius: 15px; text-align: center; z-index: 150; display: none; box-shadow: 0 10px 40px rgba(0,0,0,0.9); }}
            .fullscreen-prompt p {{ margin: 15px 0; font-size: 18px; }}
            .fullscreen-prompt .shortcut {{ background: rgba(255,255,255,0.1); padding: 8px 15px; border-radius: 5px; display: inline-block; margin: 10px 0; font-family: monospace; }}
        </style>
    </head>
    <body>
        <div class="video-container" id="video-container">
            <video id="video" autoplay playsinline muted>
                <source src="/video/{filename}" type="{mime_type}">
                Tu navegador no soporta reproducción de video.
            </video>
            <button class="close-btn" onclick="window.close()">✕ Cerrar</button>
            <button class="fullscreen-btn" onclick="requestFullscreen()">⛶ Pantalla Completa</button>
            <div class="info">
                <p><strong>📹 {filename}</strong></p>
                <p>Tamaño: {file_size_mb:.1f} MB</p>
                <p>Descargado: <span id="downloaded">0</span> MB</p>
                <div class="progress"><div class="progress-bar" id="progress-bar"></div></div>
                <p style="margin-top: 10px; font-size: 12px; opacity: 0.8;">Presiona <strong>F</strong> para pantalla completa</p>
            </div>
            <div class="fullscreen-prompt" id="fullscreen-prompt">
                <p>🎬 Pantalla Completa</p>
                <p style="font-size: 14px;">Presiona <span class="shortcut">F</span> o haz click en el botón</p>
                <p style="font-size: 12px; margin-top: 20px; opacity: 0.7;">ESC para salir</p>
            </div>
        </div>
        <script>
            const video = document.getElementById('video');
            const progressBar = document.getElementById('progress-bar');
            const downloadedSpan = document.getElementById('downloaded');
            const totalSize = {file_size};
            const promptElement = document.getElementById('fullscreen-prompt');
            let promptShown = false;
            
            function requestFullscreen() {{
                const elem = document.documentElement;
                const rfs = elem.requestFullscreen || elem.webkitRequestFullscreen || elem.mozRequestFullScreen || elem.msRequestFullscreen;
                if (rfs) {{
                    rfs.call(elem).catch(err => {{
                        console.log('Fullscreen request failed:', err.message);
                    }});
                }}
            }}
            
            function showFullscreenPrompt() {{
                if (!promptShown) {{
                    promptElement.style.display = 'block';
                    promptShown = true;
                    setTimeout(() => {{
                        promptElement.style.display = 'none';
                    }}, 4000);
                }}
            }}
            
            // Mostrar prompt después de 1 segundo
            setTimeout(showFullscreenPrompt, 1000);
            
            // Atajo de teclado: F para fullscreen
            document.addEventListener('keydown', (e) => {{
                if (e.key.toLowerCase() === 'f') {{
                    e.preventDefault();
                    requestFullscreen();
                }}
                if (e.key === 'Escape') {{
                    window.close();
                }}
            }});
            
            // Cuando sale de fullscreen, mostrar prompt de nuevo
            document.addEventListener('fullscreenchange', () => {{
                if (!document.fullscreenElement) {{
                    promptShown = false;
                }}
            }});
            
            // Cuando el video tenga metadata, intentar fullscreen
            video.addEventListener('loadedmetadata', () => {{
                // Intentar activar fullscreen automáticamente
                requestFullscreen();
            }}, {{ once: true }});
            
            // Actualizar barra de progreso
            video.addEventListener('progress', () => {{
                if (video.buffered.length > 0) {{
                    const bufferedEnd = video.buffered.end(video.buffered.length - 1);
                    const percentLoaded = (bufferedEnd / video.duration) * 100;
                    const mbLoaded = (bufferedEnd / video.duration) * (totalSize / (1024 * 1024));
                    progressBar.style.width = percentLoaded + '%';
                    downloadedSpan.textContent = mbLoaded.toFixed(1);
                }}
            }});
            
            // Iniciar reproducción automática
            video.play().catch(err => {{
                console.log('Autoplay failed:', err);
                // Si autoplay falla, mostrar mensaje
                showFullscreenPrompt();
            }});
        </script>
    </body>
    </html>
    """
    return html

@app.route("/videos")
def videos_page():
    """Página para ver videos recibidos."""
    return render_template("videos.html")

@app.route("/api/videos")
def api_videos():
    """API JSON para listar videos en descargas."""
    video_extensions = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.m3u8', '.ts', '.m4v'}
    
    downloads_dir = get_downloads_folder()
    videos = []
    
    try:
        if os.path.exists(downloads_dir):
            for filename in sorted(os.listdir(downloads_dir), key=lambda x: os.path.getmtime(os.path.join(downloads_dir, x)), reverse=True):
                if any(filename.lower().endswith(ext) for ext in video_extensions):
                    filepath = os.path.join(downloads_dir, filename)
                    if os.path.isfile(filepath):
                        size = os.path.getsize(filepath)
                        size_mb = size / (1024 * 1024)
                        mtime = os.path.getmtime(filepath)
                        videos.append({
                            "name": filename,
                            "size": f"{size_mb:.1f} MB",
                            "path": filepath,
                            "mtime": mtime
                        })
    except Exception as e:
        print(f"Error listing videos: {e}")
    
    return json.dumps(videos)

@app.route("/send-notification", methods=["POST"])
@app.route("/send-notification", methods=["POST"])
def send_notification():
    """Envía una notificación de alerta a todos los receptores."""
    print("[*] RUTA: /send-notification - Notificación POST recibida")
    
    message = request.form.get("message", "").strip()
    print(f"[DEBUG] Mensaje recibido: '{message}'")
    
    if not message:
        print("[!] Mensaje vacío")
        flash("El mensaje no puede estar vacío", "error")
        return redirect("/")
    
    if len(message) > 500:
        print("[!] Mensaje muy largo")
        flash("El mensaje es muy largo (máximo 500 caracteres)", "error")
        return redirect("/")
    
    # Obtener IPs de receptores
    print("[*] Obteniendo peers...")
    peers = get_tailscale_ips()
    print(f"[DEBUG] Peers detectados: {peers}")
    
    if not peers:
        print("[!] No hay peers disponibles")
        flash("❌ No hay receptores conectados", "error")
        return redirect("/")
    
    print(f"[+] Enviando a {len(peers)} peers")
    
    # Enviar notificación a todos los peers de forma asíncrona
    def send_alerts():
        print(f"[*] THREAD: Iniciando envío de alertas a {len(peers)} peers")
        for peer in peers:
            print(f"[*] THREAD: Enviando a {peer}")
            try:
                success = asyncio.run(send_notification_quic(peer, message))
                if success:
                    print(f"[✅] Alerta enviada a {peer}")
                else:
                    print(f"[⚠️] Alerta posiblemente no enviada a {peer}")
            except Exception as e:
                print(f"[!] THREAD ERROR: {e}")
                import traceback
                traceback.print_exc()
    
    threading.Thread(target=send_alerts, daemon=True).start()
    flash(f"🚨 ALERTA enviada a {len(peers)} receptores", "success")
    return redirect("/")

def send_notification_to_peer(ip: str, message: str):
    """Envía una notificación a un peer específico mediante HTTP POST."""
    try:
        import requests
        response = requests.post(
            f"http://{ip}:5000/receive-notification",
            json={"message": message},
            timeout=5
        )
        if response.status_code == 200:
            print(f"[+] Notificación enviada a {ip}")
        else:
            print(f"[-] Error al enviar a {ip}: {response.status_code}")
    except Exception as e:
        print(f"[-] Error enviando a {ip}: {e}")

@app.route("/receive-notification", methods=["POST"])
def receive_notification():
    """Recibe una notificación de alerta y la guarda en archivo temporal."""
    try:
        data = request.get_json()
        message = data.get("message", "").strip() if data else ""
        
        print(f"[🚨 NOTIFICACIÓN RECIBIDA] {message}")
        
        if not message:
            print(f"[!] Mensaje vacío recibido")
            return {"status": "error", "message": "Empty message"}, 400
        
        # Crear directorio /tmp si no existe (importante en algunos sistemas)
        os.makedirs("/tmp", exist_ok=True)
        
        # Guardar notificación en archivo temporal
        notification_file = "/tmp/notification.txt"
        try:
            with open(notification_file, "w", encoding="utf-8") as f:
                f.write(message)
            print(f"[✅] Notificación guardada en {notification_file}")
            print(f"[✅] Contenido: {message}")
        except Exception as e:
            print(f"[❌] Error escribiendo archivo: {e}")
            return {"status": "error", "message": f"Failed to write file: {str(e)}"}, 500
        
        # Mostrar notificación nativa del SO
        try:
            print(f"[*] Intentando mostrar notificación nativa...")
            show_native_notification("🚨 ALERTA URGENTE", message, duration=10)
            print(f"[✅] Notificación nativa mostrada")
        except Exception as e:
            print(f"[⚠️] Error mostrando notificación nativa: {e}")
        
        return {"status": "ok", "message": "Notification received and saved"}, 200
        
    except Exception as e:
        print(f"[-] Error procesando notificación: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}, 500

@app.route("/show-notification")
def show_notification():
    """Muestra la página de notificación."""
    return render_template("notification.html")

@app.route("/api/pending-notification")
def api_pending_notification():
    """API para obtener la notificación pendiente."""
    try:
        notification_file = "/tmp/notification.txt"
        if os.path.exists(notification_file):
            with open(notification_file, "r", encoding="utf-8") as f:
                message = f.read().strip()
            
            # Eliminar el archivo después de leerlo
            try:
                os.remove(notification_file)
            except:
                pass
            
            if message:
                return {"message": message}, 200
    except Exception as e:
        print(f"Error leyendo notificación: {e}")
    
    return {"message": ""}, 200

def run_flask():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(run_quic_server())