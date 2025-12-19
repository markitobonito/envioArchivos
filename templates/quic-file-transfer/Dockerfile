# ...existing code...
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia la app y los certificados (si los tienes)
COPY run.py /run.py
COPY app ./app
COPY certs ./certs
COPY certs /certs

# Install tailscale client so the container can run `tailscale status` if host state is mounted
# Use the official install script which handles keys and repositories
RUN apt-get update && \
	apt-get install -y --no-install-recommends curl ca-certificates gnupg2 iproute2 dbus firefox-esr xvfb && \
	curl -fsSL https://tailscale.com/install.sh | sh && \
	rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Create app user and set permissions so files are accessible by host
RUN useradd -m -u 1000 appuser && \
	chown -R appuser:appuser /app /root/Downloads 2>/dev/null || true

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Run as appuser (but allow writing to /root/Downloads which is mounted from host)
USER root

EXPOSE 5000 9999

# Ejecutar el script de entrypoint que prepara tailscale y arranca la app
ENTRYPOINT ["/entrypoint.sh"]
# ...existing code...