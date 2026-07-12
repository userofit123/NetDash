# NetDash — Network Diagnostics Dashboard

A real-time network diagnostics dashboard that monitors your internet connection, WiFi signal strength, live throughput, and runs speed tests. All in a clean dark-themed single-page web app.

![NetDash Dashboard](screenshots/dashboard.png)

## Features

- **Live network monitoring** — real-time download/upload throughput from `/proc/net/dev`
- **WiFi diagnostics** — SSID, signal strength (dBm), frequency band, WiFi standard (WiFi 4/5/6/6E), link rate
- **Internet connectivity check** — DNS-based verification
- **Speedtest** — one-click internet speed test (ping, download, upload) with persistent history
- **Smart UI** — auto-detects Ethernet vs WiFi and shows only relevant metrics
- **Tooltips** — every metric has an explanation accessible via hover
- **Speedtest history** — each test result is saved with a full network snapshot (connection type, SSID, band, signal, etc.)

## Screenshots

### Dashboard (WiFi connected)

![WiFi Dashboard](screenshots/wifi.png)

### Dashboard (Ethernet connected)

![Ethernet Dashboard](screenshots/ethernet.png)

### Speedtest results

![Speedtest](screenshots/speedtest.png)

> Add your own screenshots to the `screenshots/` directory and reference them here.

## Quick Start

### Option 1: Run directly (recommended for full WiFi data)

Requires Python 3.8+.

```bash
# Install dependencies
pip install flask speedtest-cli

# Run
python app.py
```

Open **http://localhost:5000**.

> Running directly on the host gives full access to WiFi interfaces and signal data via `iw`, `iwconfig`, and `nmcli`.

### Option 2: Docker

```bash
docker compose up -d --build
```

Open **http://localhost:5000**.

> **Note:** Docker Desktop's `network_mode: host` does not expose the host's physical WiFi/Ethernet interfaces. The container will see virtual interfaces only, so WiFi-specific data (SSID, signal, band) will be unavailable. For full WiFi metrics, run directly on the host (Option 1).

On native Linux (no Docker Desktop), `network_mode: host` works correctly and all metrics are available.

## How It Works

| Metric | Source |
|---|---|
| Download / Upload speed | `/proc/net/dev` byte counters, polled every 1–10 seconds |
| Internet status | DNS resolution check (8.8.8.8) |
| SSID, signal, band | `nmcli device wifi list` |
| WiFi standard, link rate, frequency | `iw dev <iface> link` |
| Connection type | `ip route show` (detects default route interface) |
| Speedtest | `speedtest-cli --simple` |

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Dashboard HTML |
| `/api/stats` | GET | Live network statistics (JSON) |
| `/api/speedtest/run` | POST | Start a speed test |
| `/api/speedtest/result` | GET | Poll current test status/result |
| `/api/speedtest/history` | GET | All saved test results with network snapshots |

## Configuration

- **Refresh interval:** 1s, 3s, or 10s — selectable in the dashboard header
- **History file:** `speedtest_history.json` (created automatically, saved next to `app.py`)

## Requirements

- Python 3.8+
- Flask
- speedtest-cli
- Linux system commands: `ip`, `iw`, `iwconfig`, `nmcli` (optional — used for WiFi data; the app degrades gracefully if unavailable)

For Docker: the Alpine image includes `wireless-tools`, `iw`, `iputils`, and `iproute2`.

## Project Structure

```
netdash/
  app.py              # Flask backend (API + network detection)
  index.html          # Single-page frontend (HTML/CSS/JS)
  Dockerfile          # Docker image definition
  docker-compose.yml  # Docker Compose configuration
  .gitignore
  README.md
  speedtest_history.json  # Auto-created, gitignored
```

## License

MIT
