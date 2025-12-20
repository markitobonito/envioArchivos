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

class FileServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._files = {}
        self._names = {}
        self._received = {}

    def show_native_notification(self, title, message, duration=8):
        import platform
        import subprocess
        system = platform.system()
        try:
            print(f"[LOG] Mostrando notificación nativa: {title} - {message}")
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
        <binding template=\"ToastText02">
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
            print(f"[ERROR] Error mostrando notificación: {e}")

    def handle_stream_data_received(self, stream_id: int, data: bytes, end_stream: bool):
        length = len(data)
        print(f"[LOG] Stream {stream_id} recibió {length} bytes")

        if stream_id not in self._names:
            if not hasattr(self, '_tmp'):
                self._tmp = {}
            if stream_id not in self._tmp:
                self._tmp[stream_id] = b""
            self._tmp[stream_id] += data
            print(f"[LOG] Stream {stream_id} buffer: {len(self._tmp[stream_id])} bytes acumulados")

            if b"\0" in self._tmp[stream_id]:
                header, first_chunk = self._tmp[stream_id].split(b"\0", 1)
                header_str = header.decode("utf-8", errors="ignore").strip()
                print(f"[LOG] Stream {stream_id} header: '{header_str}'")
                if header_str == "MSG:":
                    message = first_chunk.decode("utf-8", errors="ignore").strip()
                    print(f"[ALERTA] Notificación recibida: {message}")
                    self.show_native_notification("🚨 ALERTA URGENTE", message, 8)
                    del self._tmp[stream_id]
                    print(f"[LOG] Stream {stream_id} notificación procesada y buffer eliminado")
                    return
                else:
                    filename = header_str
                    self._names[stream_id] = filename
                    self._received[stream_id] = 0
                    download_dir = os.path.expanduser("~/Downloads" if os.name != "nt" else "~/Downloads")
                    os.makedirs(download_dir, exist_ok=True)
                    full_path = os.path.join(download_dir, filename)
                    print(f"[LOG] Stream {stream_id} iniciando descarga de archivo: {full_path}")
                    f = open(full_path, "wb")
                    if first_chunk:
                        f.write(first_chunk)
                        f.flush()
                    self._files[stream_id] = f
                    print(f"[LOG] Stream {stream_id} archivo abierto y primer chunk escrito")
                    del self._tmp[stream_id]
            return

        if stream_id in self._files:
            self._files[stream_id].write(data)
            self._files[stream_id].flush()
            self._received[stream_id] += length
            print(f"[LOG] Stream {stream_id} archivo: {self._received[stream_id]} bytes recibidos en total")
            if self._received[stream_id] % (100 * 1024 * 1024) < length:
                print(f"  {self._names[stream_id]} -> {self._received[stream_id]/(1024**3):.2f} GB recibidos")
        self.transmit()
        if end_stream:
            if stream_id in self._files:
                f = self._files.pop(stream_id)
                os.fsync(f.fileno())
                f.close()
                filename = self._names.pop(stream_id)
                download_dir = os.path.expanduser("~/Downloads" if os.name != "nt" else "~/Downloads")
                full_path = os.path.join(download_dir, filename)
                os.chmod(full_path, 0o644)
                total_gb = self._received.pop(stream_id, 0) / (1024**3)
                print(f"[LOG] Stream {stream_id} COMPLETADO -> {filename} ({total_gb:.2f} GB)")

async def run_quic_server():
    config = QuicConfiguration(
        is_client=False,
        alpn_protocols=["quic-file"],
        idle_timeout=1800,
        max_data=20 * 1024**3,
        max_stream_data=20 * 1024**3
    )
    config.load_cert_chain("cert.pem", "key.pem")
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
    try:
        result = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        self_ips = set(data.get("Self", {}).get("TailscaleIPs", []))
        peers = []
        for info in data.get("Peer", {}).values():
            if info.get("Online", False):
                dns_name = info.get("DNSName", "").rstrip(".")
                ips = info.get("TailscaleIPs", [])
                if ips and ips[0] not in self_ips:
                    peer_addr = dns_name if dns_name else ips[0]
                    peers.append(peer_addr)
                    print(f"[DEBUG] Added peer: {peer_addr} (DNS: {dns_name}, IP: {ips[0]})")
        print(f"[DEBUG] Total peers found: {len(peers)}")
        return peers
    except Exception as e:
        print(f"[ERROR] get_tailscale_ips: {e}")
        return []

async def send_file_to_ip(ip: str, filepath: str):
    filename = os.path.basename(filepath)
    print(f"\n[>] Enviando '{filename}' a {ip}:9999")
    print(f"    IP resolved: {ip}")
    
    # Try QUIC first (original behavior)
    try:
        print(f"[*] Intentando QUIC a {ip}:9999...")
        async with connect(ip, 9999, configuration=config_client) as client:
            print(f"[✓] Conexión QUIC exitosa a {ip}")
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
        print(f"[!] Error QUIC a {ip}: {type(e).__name__}: {e}")
        print("[i] Intentando fallback TCP...")

    # TCP fallback (exact same payload format: filename\\0 + bytes)
    try:
        print(f"[*] Intentando TCP a {ip}:9999...")
        with socket.create_connection((ip, 9999), timeout=30) as s:
            print(f"[✓] Conexión TCP exitosa a {ip}")
            # tune socket for better throughput: increase send buffer and disable Nagle
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 256 * 1024)
            except Exception:
                pass
            try:
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            # send header (filename + NUL)
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
            # close socket -> server treats end-of-stream as completed
        print(f"[+] COMPLETADO! '{filename}' enviado 100 % a {ip} (TCP fallback)")
    except Exception as tcp_e:
        print(f"[!] Error TCP a {ip}: {type(tcp_e).__name__}: {tcp_e}")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("No seleccionaste archivo", "error")
            return redirect("/")
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        ips = get_tailscale_ips()
        if not ips:
            flash("No hay peers Tailscale online para enviar.", "error")
            return redirect("/")
        for ip in ips:
            threading.Thread(
                target=lambda ip=ip: asyncio.run(send_file_to_ip(ip, filepath)),
                daemon=True,
            ).start()
        flash(f"Archivo '{file.filename}' enviándose a {len(ips)} dispositivo(s).", "success")
        return redirect("/")
    return render_template("index.html")

def run_flask():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(run_quic_server())