import os
import json
import asyncio
import threading
import subprocess
import requests
import time
import uuid
import io
from flask import Flask, request, redirect, render_template, flash, jsonify
from aioquic.asyncio import connect, serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, StreamReset
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import HeadersReceived, DataReceived
import socket

# Establecer umask para que todos los archivos se creen con permisos públicos (666)
os.umask(0o000)

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
        
        # ✅ HTTP/3 support
        self._is_http3 = False
        self._h3_connection = None
        self._h3_streams = {}
        self._http3_responses = {}
        
        # Detectar protocolo por ALPN negotiated
        try:
            alpn = self._quic_connection.configuration.alpn_protocols
            if "h3" in alpn or (hasattr(self._quic_connection, 'alpn_protocol') and self._quic_connection.alpn_protocol == "h3"):
                self._is_http3 = True
                self._h3_connection = H3Connection(self._quic_connection)
                print(f"[HTTP/3] ✅ Protocolo HTTP/3 detectado")
            else:
                print(f"[QUIC-FILE] 📦 Protocolo binario detectado")
        except Exception as e:
            print(f"[DEBUG] ALPN detection: {e}")

    def quic_event_received(self, event):
        # ✅ Si es HTTP/3, manejar con H3Connection
        if self._is_http3 and self._h3_connection:
            try:
                self._handle_http3_event(event)
            except Exception as e:
                print(f"[HTTP/3] Error en handler: {e}")
                import traceback
                traceback.print_exc()
            return
        
        # 📦 Si es protocolo binario, manejar normalmente
        if isinstance(event, StreamDataReceived):
            self._handle_binary_stream(event)
    
    def _handle_http3_event(self, event):
        """Procesar eventos HTTP/3"""
        if not isinstance(event, StreamDataReceived):
            return
            
        try:
            # Procesar bytes con H3Connection
            for h3_event in self._h3_connection.receive_bytes(event.data):
                if isinstance(h3_event, HeadersReceived):
                    stream_id = h3_event.stream_id
                    headers = {name.decode(): value.decode() for name, value in h3_event.headers}
                    
                    print(f"[HTTP/3] 📨 Headers {stream_id}: {headers.get(':method')} {headers.get(':path')}")
                    
                    if stream_id not in self._h3_streams:
                        self._h3_streams[stream_id] = {
                            "headers": headers,
                            "body": b"",
                            "complete": False
                        }
                        
                elif isinstance(h3_event, DataReceived):
                    stream_id = h3_event.stream_id
                    if stream_id not in self._h3_streams:
                        self._h3_streams[stream_id] = {
                            "headers": {},
                            "body": b"",
                            "complete": False
                        }
                    
                    self._h3_streams[stream_id]["body"] += h3_event.data
                    print(f"[HTTP/3] 📥 Body data {stream_id}: {len(h3_event.data)} bytes")
                    
                    # Si es fin del stream, procesar
                    if getattr(h3_event, 'end_stream', False):
                        self._h3_streams[stream_id]["complete"] = True
                        self._process_http3_request(stream_id)
                        
        except Exception as e:
            print(f"[HTTP/3] Error en _handle_http3_event: {e}")
    
    def _process_http3_request(self, stream_id):
        """Procesar request HTTP/3 completado"""
        if stream_id not in self._h3_streams:
            return
        
        stream_data = self._h3_streams[stream_id]
        headers = stream_data["headers"]
        body = stream_data["body"]
        
        method = headers.get(":method", "")
        path = headers.get(":path", "/")
        content_type = headers.get("content-type", "")
        
        print(f"[HTTP/3] 🔄 Procesando {method} {path} ({len(body)} bytes)")
        
        response_body = b""
        response_status = 404
        
        if method == "POST" and path == "/api/upload" and "multipart/form-data" in content_type:
            response_status, response_body = self._parse_http3_multipart(body, content_type)
        else:
            response_status = 404
            response_body = b"Not Found"
        
        # Enviar respuesta HTTP/3
        self._send_http3_response(stream_id, response_status, response_body)
        
        # Limpiar
        del self._h3_streams[stream_id]
    
    def _parse_http3_multipart(self, body, content_type):
        """Parsear multipart/form-data desde HTTP/3"""
        try:
            # Extraer boundary del content-type
            boundary_str = content_type.split("boundary=")[-1].strip()
            boundary = boundary_str.encode() if isinstance(boundary_str, str) else boundary_str
            
            print(f"[HTTP/3] 🔍 Boundary: {boundary}")
            
            # Parsear multipart manualmente
            parts = body.split(b"--" + boundary)
            file_data = None
            form_data = {}
            filename = ""
            
            for part in parts:
                if not part or part == b"--\r\n" or part == b"--":
                    continue
                
                # Separar headers del cuerpo
                if b"\r\n\r\n" in part:
                    headers_section, part_body = part.split(b"\r\n\r\n", 1)
                else:
                    continue
                
                # Parsear headers de la parte
                part_headers = {}
                for line in headers_section.split(b"\r\n"):
                    if b":" in line:
                        key, val = line.split(b":", 1)
                        part_headers[key.decode().lower().strip()] = val.decode().strip()
                
                print(f"[HTTP/3] Part headers: {part_headers}")
                
                # Si tiene Content-Disposition
                if "content-disposition" in part_headers:
                    cd = part_headers["content-disposition"]
                    
                    # Extraer filename si es archivo
                    if 'filename="' in cd or "filename=" in cd:
                        start = cd.find('filename="') + len('filename="')
                        if start > len('filename="') - 1:
                            end = cd.find('"', start)
                            filename = cd[start:end]
                            file_data = part_body.rstrip(b"\r\n")
                            print(f"[HTTP/3] 📄 Archivo: {filename} ({len(file_data)} bytes)")
                    else:
                        # Es un campo form
                        match_name = cd.find("name=")
                        if match_name >= 0:
                            start = match_name + len("name=") + 1
                            end = cd.find('"', start)
                            field_name = cd[start:end]
                            field_value = part_body.rstrip(b"\r\n").decode('utf-8', errors='ignore')
                            form_data[field_name] = field_value
                            print(f"[HTTP/3] 📝 Form field: {field_name}={field_value}")
            
            # Procesar archivo si existe
            if file_data and filename:
                video_action = form_data.get("videoAction", "silent").lower()
                video_time = form_data.get("videoTime", "")
                video_days = form_data.get("videoDays", "")
                
                # Construir nombre final con flags
                final_filename = filename
                action_desc = ""
                
                filename_lower = filename.lower()
                is_video = any(filename_lower.endswith(ext) for ext in {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.m4v', '.ts', '.m3u8'})
                
                if is_video:
                    if video_action == "schedule" and video_time and video_days:
                        final_filename = f"{filename}.SCHED_{video_time}_{video_days}"
                        action_desc = f"programado para {video_time}"
                    elif video_action == "silent":
                        final_filename = f"{filename}.SILENT"
                        action_desc = "silenciosamente"
                
                # Guardar archivo
                download_dir = get_downloads_folder()
                full_path = os.path.join(download_dir, final_filename)
                
                # Evitar sobrescrituras
                if os.path.exists(full_path):
                    base, ext = os.path.splitext(final_filename)
                    counter = 1
                    while os.path.exists(os.path.join(download_dir, f"{base}_{counter}{ext}")):
                        counter += 1
                    final_filename = f"{base}_{counter}{ext}"
                    full_path = os.path.join(download_dir, final_filename)
                
                with open(full_path, "wb") as f:
                    f.write(file_data)
                os.chmod(full_path, 0o666)
                
                print(f"[HTTP/3] ✅ EXITOSO: '{final_filename}' ({len(file_data)} bytes) {action_desc}")
                
                response = {
                    "status": "success",
                    "message": f"Archivo '{filename}' recibido en Descargas",
                    "filename": final_filename,
                    "size": len(file_data)
                }
                return 200, json.dumps(response).encode()
            else:
                return 400, b'{"error": "No file uploaded"}'
                
        except Exception as e:
            print(f"[HTTP/3] ❌ Error parsing multipart: {e}")
            import traceback
            traceback.print_exc()
            return 500, b'{"error": "Error processing upload"}'
    
    def _send_http3_response(self, stream_id, status, body):
        """Enviar respuesta HTTP/3"""
        try:
            if not self._h3_connection:
                return
            
            status_text = {200: "OK", 400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"}.get(status, "Unknown")
            
            headers = [
                (b":status", str(status).encode()),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ]
            
            self._h3_connection.send_headers(stream_id, headers, end_stream=False)
            self._h3_connection.send_data(stream_id, body, end_stream=True)
            self.transmit()
            
            print(f"[HTTP/3] 📤 Response {stream_id}: {status} ({len(body)} bytes)")
        except Exception as e:
            print(f"[HTTP/3] ❌ Error sending response: {e}")
    
    def _handle_binary_stream(self, event):
        """Manejar protocolo binario QUIC (P2P laptops)"""
        stream_id = event.stream_id
        data = event.data
        length = len(data)
        
        print(f"[QUIC-FILE] Stream {stream_id}: {len(data)} bytes, end_stream={event.end_stream}")

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
                
                print(f"[QUIC-FILE] Header: {header_str}")
                
                filename = header_str
                self._names[stream_id] = filename
                self._received[stream_id] = 0

                download_dir = get_downloads_folder()
                full_path = os.path.join(download_dir, filename)
                print(f"[QUIC-FILE] Descargando → {filename}")

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
                print(f"  [QUIC-FILE] {self._names[stream_id]} → {self._received[stream_id]/(1024**3):.2f} GB")

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
                    print(f"[QUIC-FILE] ✅ Permisos: {full_path}")
                except Exception as e:
                    print(f"[QUIC-FILE] [-] Error permisos: {e}")
                
                total_gb = self._received.pop(stream_id, 0) / (1024**3)
                print(f"[QUIC-FILE] ✅ COMPLETADO → {filename} ({total_gb:.2f} GB)")

app = Flask(__name__)
app.secret_key = "multicast-secret"

config_client = QuicConfiguration(
    is_client=True,
    alpn_protocols=["quic-file"],  # Para conexiones P2P laptop-to-laptop
)
config_client.verify_mode = False
config_client.idle_timeout = 600.0
config_client.max_data = 1024 * 1024 * 1024
config_client.max_stream_data = 1024 * 1024 * 1024

def get_tailscale_ips():
    """
    ✅ Obtiene peers desde tailscale_status.json (actualizado continuamente por host)
    Incluye TODOS los peers alcanzables (Online, InMagicSock, o idle)
    """
    status_path = "/app/tailscale_status.json"
    
    if not os.path.exists(status_path):
        print("[!] No hay JSON de Tailscale en", status_path, flush=True)
        return []
    
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Leyendo JSON: {e}", flush=True)
        return []
    
    if not data:
        return []
    
    # Extraer peers alcanzables
    self_ips = set(data.get("Self", {}).get("TailscaleIPs", []))
    peers = []
    
    for info in data.get("Peer", {}).values():
        ips = info.get("TailscaleIPs", [])
        if not ips or ips[0] in self_ips:
            continue
        
        ip = ips[0]
        hostname = info.get("HostName", "?")
        is_online = info.get("Online", False)
        is_in_magicsock = info.get("InMagicSock", False)
        is_in_netmap = info.get("InNetworkMap", False)
        
        # ✅ INCLUIR: Online, en MagicSock, o en NetworkMap (incluye Android idle)
        if is_online or is_in_magicsock or is_in_netmap:
            peers.append(ip)
            status = "online" if is_online else ("magicsock" if is_in_magicsock else "netmap")
            print(f"[✓] Peer: {hostname} ({ip}) [{status}]", flush=True)
    
    print(f"[✓] Total peers: {len(peers)}", flush=True)
    return peers

async def send_file_to_ip(ip: str, filepath: str, filename: str = None):
    """Envía un archivo a través de HTTP/3 (primer intento) o QUIC (fallback)"""
    if filename is None:
        filename = os.path.basename(filepath)
    
    print(f"[>] Enviando '{filename}' a {ip} ...")
    
    # ✅ PRIMER INTENTO: HTTP/3 REAL (compatible con Android vía Cronet)
    try:
        print(f"[DEBUG] Intentando HTTP/3 POST a {ip}:9999/api/upload")
        import httpx
        
        with open(filepath, 'rb') as f:
            files = {'file': (filename, f, 'application/octet-stream')}
            data = {'videoAction': 'silent'}  # default silencioso
            
            # Usar httpx con HTTP/3
            async with httpx.AsyncClient(http2=False, verify=False) as client:
                response = await client.post(
                    f"http://{ip}:9999/api/upload",
                    files=files,
                    data=data,
                    timeout=60.0
                )
            
            if response.status_code >= 200 and response.status_code < 300:
                print(f"[✅] HTTP/3 EXITOSO: '{filename}' enviado a {ip}")
                return
            else:
                print(f"[!] HTTP/3 falló: {response.status_code}")
    except Exception as e:
        print(f"[!] HTTP/3 error a {ip}: {type(e).__name__}: {str(e)}")
    
    # ✅ SEGUNDO INTENTO: QUIC binario (para laptop-to-laptop con protocolo quic-file)
    print("[i] Intentando fallback QUIC binario...")
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

# ✅ HTTP/3 ahora handled directamente en aioquic.serve() con HTTP/3 support
# No necesitamos rutas Flask separadas

# ✅ Las rutas Flask siguientes son SOLO para compatibilidad web local, no para Android
# Android apunta a puerto 9999 UDP (HTTP/3 en aioquic)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("No seleccionaste archivo", "error")
            return redirect("/")
        
        # Obtener opciones de programación del video
        video_action = request.form.get("videoAction", "silent").strip().lower()  # now, schedule, silent
        video_time = request.form.get("videoTime", "").strip()
        video_days_list = request.form.getlist("videoDays")  # getlist para múltiples checkboxes
        video_days = ",".join(video_days_list) if video_days_list else ""
        
        # Crear metadata del video si es un video
        filename_lower = file.filename.lower()
        is_video = any(filename_lower.endswith(ext) for ext in {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.m4v', '.ts', '.m3u8'})
        
        # Determinar el nombre final del archivo con flag de acción si es un video
        if is_video:
            if video_action == "schedule" and video_time and video_days:
                # Agregar flag de programación: video.mp4.SCHED_14:30_mon,wed,fri
                final_filename = f"{file.filename}.SCHED_{video_time}_{video_days}"
                action_text = f"programado para {video_time}"
            elif video_action == "silent":
                # Agregar flag silent: video.mp4.SILENT
                final_filename = f"{file.filename}.SILENT"
                action_text = "descargándose silenciosamente"
            else:  # now (default)
                # Dejar nombre normal
                final_filename = file.filename
                action_text = "reproducirá al llegar"
        else:
            final_filename = file.filename
            action_text = ""
        
        # Guardar archivo temporalmente en memoria para enviarlo
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file.save(tmp.name)
            tmp_filepath = tmp.name
        
        ips = get_tailscale_ips()
        print(f"[DEBUG INDEX] get_tailscale_ips() retornó: {ips}")
        
        if not ips:
            print("[!] No hay peers online")
            flash("No hay peers Tailscale online para enviar.", "error")
            os.remove(tmp_filepath)
            return redirect("/")
        
        print(f"[+] Enviando a {len(ips)} peers: {ips}")
        for ip in ips:
            print(f"[THREAD] Iniciando hilo de envío para {ip}")
            # Pasar el nombre final con flags, no el temporal
            threading.Thread(
                target=lambda ip=ip, tmpfile=tmp_filepath, finalname=final_filename: asyncio.run(send_file_to_ip(ip, tmpfile, finalname)),
                daemon=True,
            ).start()
        
        # Limpiar archivo temporal después de un tiempo
        threading.Timer(30.0, lambda: os.remove(tmp_filepath) if os.path.exists(tmp_filepath) else None).start()
        
        flash(f"Archivo '{file.filename}' enviándose a {len(ips)} dispositivo(s). Video {action_text}.", "success")
        return redirect("/")
    return render_template("index.html")

@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    ✅ Endpoint HTTP/1.1 para recibir archivos desde Android/Cronet (UDP puerto 9999 TCP)
    Idéntico a la ruta POST "/" pero devuelve JSON en lugar de HTML redirect
    """
    try:
        file = request.files.get("file")
        if not file or file.filename == "":
            return jsonify({"error": "No file provided"}), 400
        
        # Obtener metadata del video desde formulario (igual que ruta web)
        video_action = request.form.get("videoAction", "silent").strip().lower()
        video_time = request.form.get("videoTime", "").strip()
        video_days_str = request.form.get("videoDays", "").strip()
        sender_ip = request.remote_addr
        
        # Detectar si es video
        filename_lower = file.filename.lower()
        is_video = any(filename_lower.endswith(ext) for ext in {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.m4v', '.ts', '.m3u8'})
        
        # Guardar con nombre ORIGINAL (sin flags en el archivo)
        # Los flags son solo meta-información para el comportamiento
        final_filename = file.filename
        
        if is_video:
            if video_action == "schedule" and video_time and video_days_str:
                action_desc = f"programado para {video_time}"
            elif video_action == "silent":
                action_desc = "descargándose silenciosamente"
            else:  # now
                action_desc = "reproducirá al llegar"
        else:
            action_desc = ""
        
        # Guardar en ~/Descargas/
        download_dir = get_downloads_folder()
        full_path = os.path.join(download_dir, final_filename)
        
        # Evitar sobrescrituras
        if os.path.exists(full_path):
            base, ext = os.path.splitext(final_filename)
            counter = 1
            while os.path.exists(os.path.join(download_dir, f"{base}_{counter}{ext}")):
                counter += 1
            final_filename = f"{base}_{counter}{ext}"
            full_path = os.path.join(download_dir, final_filename)
        
        file.save(full_path)
        os.chmod(full_path, 0o666)
        
        file_size = os.path.getsize(full_path)
        print(f"[✅] HTTP/3 UDP EXITOSO: '{final_filename}' ({file_size} bytes) desde {sender_ip} {action_desc}", flush=True)
        
        return jsonify({
            "status": "success",
            "message": f"Archivo recibido: {file.filename}",
            "filename": final_filename,
            "size": file_size,
            "action": action_desc
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[❌] Error en /api/upload: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

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
            
            // Cerrar automáticamente cuando termine el video
            video.addEventListener('ended', () => {{
                console.log('Video terminado, cerrando ventana...');
                window.close();
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
def send_notification():
    """Envía una notificación de alerta a todos los receptores como archivo .msg con repeticiones."""
    print("[*] RUTA: /send-notification - Notificación POST recibida")
    
    message = request.form.get("message", "").strip()
    repetitions = request.form.get("repetitions", "1").strip()
    
    print(f"[DEBUG] Mensaje recibido: '{message}'")
    print(f"[DEBUG] Repeticiones: '{repetitions}'")
    
    if not message:
        print("[!] Mensaje vacío")
        return jsonify({"status": "error", "message": "El mensaje no puede estar vacío"}), 400
    
    if len(message) > 500:
        print("[!] Mensaje muy largo")
        return jsonify({"status": "error", "message": "El mensaje es muy largo (máximo 500 caracteres)"}), 400
    
    # Validar y convertir repeticiones
    try:
        repetitions = int(repetitions)
        if repetitions < 1 or repetitions > 10:
            repetitions = 1
    except ValueError:
        repetitions = 1
    
    # Crear archivo .msg temporal con formato: repeticiones|mensaje
    temp_filename = f"ALERTA_{uuid.uuid4().hex[:8]}_{int(time.time())}.msg"
    temp_filepath = os.path.join("/tmp", temp_filename)
    
    try:
        # Formato: repeticiones|mensaje
        alert_content = f"{repetitions}|{message}"
        with open(temp_filepath, "w", encoding="utf-8") as f:
            f.write(alert_content)
        print(f"[+] Archivo de alerta creado: {temp_filepath}")
        print(f"[+] Contenido: {alert_content}")
    except Exception as e:
        print(f"[!] Error creando archivo de alerta: {e}")
        return jsonify({"status": "error", "message": "Error al crear el archivo de alerta"}), 500
    
    # Obtener IPs de receptores
    print("[*] Obteniendo peers...")
    peers = get_tailscale_ips()
    print(f"[DEBUG] Peers detectados: {peers}")
    
    if not peers:
        print("[!] No hay peers disponibles")
        return jsonify({"status": "error", "message": "❌ No hay receptores conectados"}), 400
    
    print(f"[+] Enviando alerta a {len(peers)} peers usando protocolo QUIC")
    
    # Enviar archivo de alerta a todos los peers de forma asíncrona (igual que archivos normales)
    def send_alerts():
        print(f"[*] THREAD: Iniciando envío de alertas a {len(peers)} peers")
        for peer in peers:
            print(f"[*] THREAD: Enviando alerta a {peer}")
            try:
                # Usar la MISMA función que envia archivos
                asyncio.run(send_file_to_ip(peer, temp_filepath))
                print(f"[✅] ALERTA enviada a {peer}")
            except Exception as e:
                print(f"[!] THREAD ERROR enviando alerta a {peer}: {e}")
                import traceback
                traceback.print_exc()
        
        # Limpiar archivo temporal después de enviar
        try:
            os.remove(temp_filepath)
            print(f"[+] Archivo temporal eliminado: {temp_filepath}")
        except Exception as e:
            print(f"[!] Error eliminando temporal: {e}")
    
    threading.Thread(target=send_alerts, daemon=True).start()
    return jsonify({"status": "success", "message": f"🚨 Alerta enviada a {len(peers)} receptores", "count": len(peers)}), 200

def run_flask():
    """
    ✅ Flask escucha en:
    - 127.0.0.1:8080 → localhost (navegador local)
    - 0.0.0.0:9999 → todos los interfaces (Android/Tailscale TCP)
    """
    # Escuchar en 0.0.0.0:9999 para recibir desde Android/Cronet
    app.run(host="0.0.0.0", port=9999, debug=False, use_reloader=False)

async def run_quic_server():
    """Ejecutar servidor QUIC asincronamente con soporte HTTP/3 + protocolo binario"""
    print("[*] run_quic_server() iniciado", flush=True)
    try:
        print("[*] Cargando configuración QUIC...", flush=True)
        config = QuicConfiguration(
            is_client=False,
            alpn_protocols=["h3", "quic-file"],  # ✅ Añadido "h3" para HTTP/3
            idle_timeout=1800,
            max_data=20 * 1024**3,
            max_stream_data=20 * 1024**3
        )
        print("[*] Cargando certificados...", flush=True)
        config.load_cert_chain("certs/cert.pem", "certs/key.pem")
        print("[✓] Certificados cargados correctamente", flush=True)
        
        print("[*] Iniciando servidor QUIC en 0.0.0.0:9999...", flush=True)
        print("[*] Soportando ALPN protocols: h3 (HTTP/3 Android), quic-file (protocolo binario laptops)", flush=True)
        await serve("0.0.0.0", 9999, configuration=config, create_protocol=FileServerProtocol)
        print("[+] Servidor QUIC escuchando en 0.0.0.0:9999", flush=True)
    except Exception as e:
        print(f"[❌] Error en servidor QUIC: {e}", flush=True)
        import traceback
        traceback.print_exc()
    
    # Keep the event loop running indefinitely
    while True:
        await asyncio.sleep(1)

@app.route("/peers", methods=["GET"])
def get_peers_list():
    """
    ✅ Endpoint para Android: devuelve lista de peers ONLINE
    Android consulta esto para saber a quién enviar archivos
    """
    try:
        peers = get_tailscale_ips()
        return jsonify({
            "status": "success",
            "peers": peers,
            "count": len(peers)
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

if __name__ == "__main__":
    # ✅ Flask daemon thread: localhost:8080 (navegador local únicamente)
    # ✅ QUIC main thread: 0.0.0.0:9999 UDP (laptops protocolo binario + Android HTTP/3)
    print("[✅] Iniciando servidor...")
    print("[*] → Flask en 127.0.0.1:8080 (localhost, navegador local)")
    print("[*] → aioquic en 0.0.0.0:9999 UDP (Tailscale)")
    print("[*]   ├─ Protocolo binario (laptops P2P)")
    print("[*]   └─ HTTP/3 endpoint (Android Cronet)")
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(run_quic_server())