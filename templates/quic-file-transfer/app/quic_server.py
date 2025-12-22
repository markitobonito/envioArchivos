from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
import os
import asyncio
import platform
import subprocess

class FileServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._files = {}
        self._names = {}
        self._received = {}

def show_native_notification_server(title: str, message: str):
    """Muestra notificación nativa en el servidor."""
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script])
        elif system == "Windows":
            ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$APP_ID = 'QuicFileTransfer'
$template = @"
<toast><visual><binding template=\"ToastText02\"><text id=\"1\">{title}</text><text id=\"2\">{message}</text></binding></visual></toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($APP_ID).Show($toast)
"""
            subprocess.run(["powershell", "-Command", ps_script])
        elif system == "Linux":
            subprocess.run(["notify-send", "-u", "critical", "-t", "10000", title, message])
    except Exception as e:
        print(f"[!] Error mostrando notificación: {e}")

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

            # Detectar si es una NOTIFICACIÓN (no un archivo)
            if stream_id not in self._names and stream_id not in self._files:
                if not hasattr(self, '_tmp'):
                    self._tmp = {}
                if stream_id not in self._tmp:
                    self._tmp[stream_id] = b""
                self._tmp[stream_id] += data

                # Detectar si es notificación o archivo
                if b"\0" in self._tmp[stream_id]:
                    header, rest = self._tmp[stream_id].split(b"\0", 1)
                    header_str = header.decode("utf-8", errors="ignore").strip()
                    
                    # Si empieza con NOTIFICATION:, es una alerta
                    if header_str.startswith("NOTIFICATION:"):
                        message = header_str.replace("NOTIFICATION:", "", 1)
                        print(f"[🚨 NOTIFICACIÓN QUIC RECIBIDA] {message}")
                        
                        # Guardar en /tmp/notification.txt
                        os.makedirs("/tmp", exist_ok=True)
                        with open("/tmp/notification.txt", "w", encoding="utf-8") as f:
                            f.write(message)
                        print(f"[✅] Notificación guardada en /tmp/notification.txt")
                        
                        # Mostrar notificación nativa
                        try:
                            show_native_notification_server("🚨 ALERTA URGENTE", message)
                            print(f"[✅] Notificación nativa mostrada")
                        except Exception as e:
                            print(f"[⚠️] Error mostrando notificación: {e}")
                        
                        # Limpiar el buffer
                        del self._tmp[stream_id]
                        return
                    
                    # Si NO es notificación, es un archivo (como antes)
                    filename = header_str
                    self._names[stream_id] = filename
                    self._received[stream_id] = 0

                    download_dir = os.path.expanduser("~/Downloads" if os.name != "nt" else "~/Downloads")
                    os.makedirs(download_dir, exist_ok=True)
                    full_path = os.path.join(download_dir, filename)

                    f = open(full_path, "wb")
                    if rest:
                        f.write(rest)
                        f.flush()
                    self._files[stream_id] = f
                    print(f"[ARCHIVO] Iniciando descarga -> {filename}")
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
                    download_dir = os.path.expanduser("~/Downloads" if os.name != "nt" else "~/Downloads")
                    full_path = os.path.join(download_dir, filename)
                    os.chmod(full_path, 0o666)
                    total_gb = self._received.pop(stream_id, 0) / (1024**3)
                    print(f"COMPLETADO -> {filename} ({total_gb:.2f} GB)")

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