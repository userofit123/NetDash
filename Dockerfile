FROM python:3.12-alpine

# System tools for network diagnostics (all optional — app degrades gracefully)
#   iproute2  → ip command (interface detection)
#   iw         → iw dev <iface> link (WiFi band, rate, signal)
#   wireless-tools → iwconfig fallback (SSID, signal)
#   nmcli is NOT installed here — it requires NetworkManager + D-Bus.
#   The app falls back to iwconfig for SSID when nmcli is missing.
RUN apk add --no-cache iproute2 iw wireless-tools

# Python dependencies — only Flask needed
RUN pip install flask --no-cache-dir

WORKDIR /app

# Application files
COPY app.py index.html ./
COPY static/ ./static/
COPY data/ ./data/

EXPOSE 5000

CMD ["python3", "app.py"]
