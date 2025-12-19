import os
import json
import asyncio
import threading
import subprocess
from flask import Flask, request, redirect, render_template, flash
from aioquic.asyncio import connect, serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
import socket
import platform

def get_downloads_folder():
    """
    Detecta la carpeta de descargas correcta según el SO e idioma.
    - Windows/macOS en español: ~/Descargas
    - Otros: ~/Downloads
    Crea la carpeta si no existe.
    """
    home = os.path.expanduser("~")
    
    # Intentar Descargas primero (español)
    descargas_path = os.path.join(home, "Descargas")
    if os.path.exists(descargas_path) and os.path.isdir(descargas_path):
        return descargas_path
    
    # Fallback a Downloads (inglés)
    downloads_path = os.path.join(home, "Downloads")
    os.makedirs(downloads_path, exist_ok=True)
    return downloads_path

# ...existing code...

class FileServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._files = {}
        self._names = {}
        self._received = {}

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            stream_id = event.stream_id
            data = event.data
            length = len(data)

            if stream_id not in self._names:
                if not hasattr(self, '_tmp'):
                    self._tmp = {}
                if stream_id not in self._tmp:
                    self._tmp[stream_id] = b""
                self._tmp[stream_id] += data

                if b"\0" in self._tmp[stream_id]:
                    header, first_chunk = self._tmp[stream_id].split(b"\0", 1)
                    filename = header.decode("utf-8", errors="ignore").strip()
                    self._names[stream_id] = filename
                    self._received[stream_id] = 0

                    # Usar la carpeta de descargas correcta (Descargas o Downloads según idioma)
                    download_dir = get_downloads_folder()
                    full_path = os.path.join(download_dir, filename)
                    print(f"[DEBUG] Guardando en: {full_path}")

                    f = open(full_path, "wb")
                    if first_chunk:
                        f.write(first_chunk)
                        f.flush()
                    self._files[stream_id] = f
                    print(f"Iniciando descarga -> {filename}")
                    del self._tmp[stream_id]
                return

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
                    os.chmod(full_path, 0o644)
                    total_gb = self._received.pop(stream_id, 0) / (1024**3)
                    print(f"COMPLETADO -> {filename} ({total_gb:.2f} GB) en {full_path}")

async def run_quic_server():
    config = QuicConfiguration(
        is_client=False,
        alpn_protocols=["quic-file"],
        idle_timeout=1800,
        max_data=20 * 1024**3,
        max_stream_data=20 * 1024**3
    )
    config.load_cert_chain("certs/cert.pem", "certs/key.pem")
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
                        # Preferir DNS name para mejor resolucion en contenedores
                        dns_name = info.get("DNSName", "").rstrip(".")
                        ips = info.get("TailscaleIPs", [])
                        if ips and ips[0] not in self_ips:
                            # Si tenemos DNSName, usarlo; si no, usar IP
                            peer_addr = dns_name if dns_name else ips[0]
                            peers.append(peer_addr)
                            print(f"[DEBUG] Added peer: {peer_addr} (DNS: {dns_name}, IP: {ips[0]})")
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
        
        # Guardar información de programación en archivo JSON para todos los videos
        if is_video:
            metadata_file = os.path.join(UPLOAD_FOLDER, f"{file.filename}.schedule.json")
            
            if video_action == "schedule" and video_time and video_days:
                schedule_data = {
                    "filename": file.filename,
                    "action": "schedule",
                    "time": video_time,
                    "days": video_days.split(","),
                    "created_at": str(os.path.getmtime(filepath))
                }
                action_text = f"programado para {video_time}"
            elif video_action == "now":
                schedule_data = {
                    "filename": file.filename,
                    "action": "now",
                    "created_at": str(os.path.getmtime(filepath))
                }
                action_text = "reproducirá al llegar"
            else:  # silent
                schedule_data = {
                    "filename": file.filename,
                    "action": "silent",
                    "created_at": str(os.path.getmtime(filepath))
                }
                action_text = "descargándose silenciosamente"
            
            with open(metadata_file, 'w') as f:
                json.dump(schedule_data, f)
        else:
            action_text = ""
        
        ips = get_tailscale_ips()
        if not ips:
            flash("No hay peers Tailscale online para enviar.", "error")
            return redirect("/")
        
        for ip in ips:
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
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reproduciendo: {filename}</title>
        <style>
            * {{ margin: 0; padding: 0; }}
            html, body {{ width: 100%; height: 100%; }}
            body {{ background: #000; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}
            .video-container {{ flex: 1; display: flex; align-items: center; justify-content: center; position: relative; width: 100%; height: 100%; }}
            video {{ width: 100vw; height: 100vh; object-fit: contain; }}
            video:fullscreen {{ width: 100vw; height: 100vh; }}
            .info {{ position: absolute; bottom: 20px; left: 20px; background: rgba(0,0,0,0.7); color: #fff; padding: 15px 20px; border-radius: 8px; font-size: 14px; z-index: 5; }}
            .info p {{ margin: 5px 0; }}
            .progress {{ width: 200px; height: 4px; background: rgba(255,255,255,0.3); border-radius: 2px; margin-top: 10px; overflow: hidden; }}
            .progress-bar {{ height: 100%; background: #4CAF50; width: 0%; transition: width 0.3s; }}
            .close-btn {{ position: absolute; top: 20px; right: 20px; background: rgba(0,0,0,0.7); color: #fff; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; font-size: 14px; z-index: 10; }}
            .close-btn:hover {{ background: rgba(0,0,0,0.9); }}
            .fullscreen-prompt {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.9); color: #fff; padding: 30px; border-radius: 10px; text-align: center; z-index: 20; display: none; }}
            .fullscreen-prompt p {{ margin: 10px 0; font-size: 16px; }}
        </style>
    </head>
    <body>
        <div class="video-container" id="video-container">
            <video id="video" controls autoplay playsinline>
                <source src="/video/{filename}" type="{mime_type}">
                Tu navegador no soporta reproducción de video.
            </video>
            <button class="close-btn" onclick="window.close()">Cerrar (ESC)</button>
            <div class="info">
                <p><strong>📹 {filename}</strong></p>
                <p>Tamaño: {file_size_mb:.1f} MB</p>
                <p>Descargado: <span id="downloaded">0</span> MB</p>
                <div class="progress"><div class="progress-bar" id="progress-bar"></div></div>
                <p style="margin-top: 10px; font-size: 12px; opacity: 0.8;">Presiona F para pantalla completa</p>
            </div>
            <div class="fullscreen-prompt" id="fullscreen-prompt">
                <p>Presiona <strong>F</strong> para pantalla completa</p>
                <p style="font-size: 12px; margin-top: 20px;">O haz click en el botón de pantalla completa del reproductor</p>
            </div>
        </div>
        <script>
            const video = document.getElementById('video');
            const progressBar = document.getElementById('progress-bar');
            const downloadedSpan = document.getElementById('downloaded');
            const totalSize = {file_size};
            
            // Auto-intentar fullscreen
            function tryFullscreen() {{
                const elem = document.documentElement;
                const rfs = elem.requestFullscreen || elem.webkitRequestFullscreen || elem.mozRequestFullScreen || elem.msRequestFullscreen;
                if (rfs) {{
                    rfs.call(elem).catch(err => {{
                        console.log('Fullscreen request failed:', err.message);
                    }});
                }}
            }}
            
            // Cuando el video empieza a reproducirse, intentar fullscreen
            video.addEventListener('play', () => {{
                // Esperar un poco para que el navegador esté listo
                setTimeout(tryFullscreen, 500);
            }}, {{ once: true }});
            
            // Atajo de teclado: F para fullscreen
            document.addEventListener('keydown', (e) => {{
                if (e.key.toLowerCase() === 'f') {{
                    if (video.requestFullscreen) {{
                        video.requestFullscreen().catch(err => console.log(err));
                    }} else if (video.webkitRequestFullscreen) {{
                        video.webkitRequestFullscreen();
                    }}
                }}
                if (e.key === 'Escape') {{
                    window.close();
                }}
            }});
            
            // Mostrar prompt después de 2 segundos si no está en fullscreen
            setTimeout(() => {{
                if (!document.fullscreenElement && !document.webkitFullscreenElement) {{
                    document.getElementById('fullscreen-prompt').style.display = 'block';
                    setTimeout(() => {{
                        document.getElementById('fullscreen-prompt').style.display = 'none';
                    }}, 4000);
                }}
            }}, 2000);
            
            video.addEventListener('progress', () => {{
                if (video.buffered.length > 0) {{
                    const bufferedEnd = video.buffered.end(video.buffered.length - 1);
                    const percentLoaded = (bufferedEnd / video.duration) * 100;
                    const mbLoaded = (bufferedEnd / video.duration) * (totalSize / (1024 * 1024));
                    progressBar.style.width = percentLoaded + '%';
                    downloadedSpan.textContent = mbLoaded.toFixed(1);
                }}
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

def run_flask():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(run_quic_server())