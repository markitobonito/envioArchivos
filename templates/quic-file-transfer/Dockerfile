# ...existing code...
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia la app y los certificados
COPY run.py /run.py
COPY app ./app
COPY certs ./certs
COPY certs /certs

# Instalar dependencias del sistema
RUN apt-get update && \
	apt-get install -y --no-install-recommends curl ca-certificates gnupg2 iproute2 dbus && \
	rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Create app user
RUN useradd -m -u 1000 appuser && \
	chown -R appuser:appuser /app /root/Downloads 2>/dev/null || true

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER root

EXPOSE 5000 9999

# Ejecutar el script de entrypoint que prepara y arranca la app
ENTRYPOINT ["/entrypoint.sh"]
# ...existing code...