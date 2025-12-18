from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
import os
import asyncio

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

                    download_dir = os.path.expanduser("~/Downloads" if os.name != "nt" else "~/Downloads")
                    os.makedirs(download_dir, exist_ok=True)
                    full_path = os.path.join(download_dir, filename)

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
                    download_dir = os.path.expanduser("~/Downloads" if os.name != "nt" else "~/Downloads")
                    full_path = os.path.join(download_dir, filename)
                    os.chmod(full_path, 0o644)
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