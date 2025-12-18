import os
import threading
import asyncio
from app.client import run_flask
from app.quic_server import run_quic_server

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(run_quic_server())