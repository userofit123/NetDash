# NetDash — Developer Documentation

## Overview

NetDash is a real-time network diagnostics dashboard. It displays live download/upload throughput with SVG arc gauges, WiFi connection details (SSID, signal strength, band, WiFi standard, link rate), an internet connectivity check, and a speed test with persistent history. The entire frontend is a single HTML file with embedded CSS and vanilla JavaScript. The backend is a Flask application.

**What it runs on**: Linux (bare metal or Docker). WiFi diagnostics require Linux host tools and only work on bare-metal Linux — they degrade gracefully to dashes otherwise.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│  SERVER (Linux host or Docker container)                                    │
│                                                                            │
│  ┌──────────────────────────┐    ┌──────────────────────────────────────┐  │
│  │  waitress WSGI server    │    │  Linux system tools                   │  │
│  │  (production, 8 threads) │    │  ip route, iw, iwconfig, nmcli        │  │
│  │  port 5000               │    │  /proc/net/dev                       │  │
│  │                          │    │  /sys/class/net/*                    │  │
│  │  ┌────────────────────┐  │    └──────────────┬───────────────────────┘  │
│  │  │  Flask application │  │                   │                          │
│  │  │  app.py (407 LOC)  │◄─────────────────────┘                          │
│  │  │                    │  │                                               │
│  │  │  /api/stats        │  │  ← live throughput, WiFi diags, internet     │
│  │  │  /api/speedtest/*  │  │  ← history CRUD                              │
│  │  │  /api/settings     │  │  ← highlight rules, auto-test config         │
│  │  │  /api/librespeed-* │  │  ← proxied server list (avoids CORS)         │
│  │  │  /                 │  │  ← serves index.html                         │
│  │  │  /static/*         │  │  ← favicons, speedtest JS libraries          │
│  │  └────────────────────┘  │                                               │
│  └──────────┬───────────────┘                                               │
│             │ HTTP (same-origin)                                            │
└─────────────┼──────────────────────────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────────────┐
│  BROWSER (index.html)                                           │
│                                                                 │
│  Vanilla JS SPA — no frameworks. Polls /api/stats on timer.     │
│  Speedtest uses LibreSpeed JS library against external servers.  │
│                                                                 │
│  ┌──────────┐  ┌────────────┐  ┌──────────────┐                 │
│  │  Gauges  │  │  Info      │  │  Speedtest   │                 │
│  │  (3 SVG  │  │  Strip     │  │  Section     │                 │
│  │   arcs)  │  │  (5 cols)  │  │              │                 │
│  └──────────┘  └────────────┘  └──────┬───────┘                 │
│                                       │                          │
│                      ┌────────────────┴─────────────┐            │
│                      │  LibreSpeed JS                │            │
│                      │  speedtest.js                 │            │
│                      │  speedtest_worker.js (Web      │            │
│                      │    Worker, also loaded from    │            │
│                      │    /speedtest_worker.js)       │            │
│                      └──────────────────────────────┘            │
│                               │                                    │
└───────────────────────────────┼────────────────────────────────────┘
                                │ fetch() to external servers
                                ▼
                  ┌─────────────────────────────┐
                  │  LibreSpeed community        │
                  │  test servers                │
                  │  (fetched via Flask proxy)    │
                  └─────────────────────────────┘
```

### Key architectural decisions

1. **Speedtest runs in the browser, not the server.** The Flask backend does NOT proxy speedtest traffic. It only proxies the server list from `librespeed.org` to avoid CORS. The browser's LibreSpeed JS worker connects directly to whichever community test server is fastest. This means the speedtest measures the client device's actual internet speed.

2. **No frontend framework.** The entire UI is vanilla JS in a single `index.html` file (~1280 lines). There is no build step, no bundler, no npm. This keeps deployment trivial — serve one file.

3. **Throughput comes from the kernel.** Live download/upload speeds are computed by reading `/proc/net/dev` byte counters, taking the delta between successive polls. No external monitoring daemon needed.

4. **Everything degrades gracefully.** If `iw`, `nmcli`, or `/proc/net/dev` are unavailable (Docker, macOS, Windows), those metrics show dashes instead of crashing.

---

## Tech Stack

| Layer | Technology | Version / Notes |
|---|---|---|
| **Language** | Python 3 | 3.12+ |
| **Web framework** | Flask | 3.x |
| **WSGI server** | waitress | 3.x, 8 threads |
| **Frontend** | Vanilla HTML/CSS/JS | No frameworks, no build step |
| **Speedtest** | LibreSpeed JS | v6.1.0, `speedtest.js` + `speedtest_worker.js` |
| **Fonts** | Google Fonts | JetBrains Mono, Space Grotesk |
| **Containerization** | Docker + Docker Compose | Alpine Linux base |
| **Reverse proxy** | Caddy | v2, optional, for HTTPS/TLS |
| **Process manager** | systemd | `netdash.service` with `Restart=always` |
| **Data storage** | JSON files | `data/speedtest_history.json`, `data/settings.json` |

### Python dependencies

| Package | Purpose |
|---|---|
| `flask` | Web framework, routing, JSON responses |
| `waitress` | Production WSGI server (replaces `app.run()`) |
| `re`, `time`, `socket`, `os`, `json` | stdlib — regex parsing, timing, DNS checks, file I/O |
| `subprocess` | stdlib — running `ip`, `iw`, `nmcli`, `iwconfig` |
| `urllib.request` | stdlib — proxy LibreSpeed server list |

### System dependencies (Linux host only, optional)

| Tool | Purpose | Package |
|---|---|---|
| `ip` | Interface detection, local IP | `iproute2` |
| `iw` | WiFi band, rate, signal, standard | `iw` |
| `iwconfig` | Fallback SSID/signal | `wireless-tools` |
| `nmcli` | SSID detection (primary) | `network-manager` or `NetworkManager` |
| `/proc/net/dev` | Live throughput byte counters | Linux kernel, always available |

---

## File Structure

```
netdash/
├── app.py                  # Flask backend (407 lines)
├── index.html              # SPA frontend (1280 lines, embedded CSS + JS)
├── static/
│   ├── speedtest.js        # LibreSpeed main client library (v6.1.0)
│   ├── speedtest_worker.js # LibreSpeed Web Worker (runs speedtest in background)
│   ├── favicon.svg         # SVG favicon
│   ├── favicon-32.png      # 32×32 PNG favicon
│   └── favicon.ico         # ICO fallback
├── data/
│   ├── .gitkeep            # Ensures directory exists in git
│   ├── speedtest_history.json  # Created at runtime, gitignored
│   └── settings.json           # Created at runtime, gitignored
├── Dockerfile              # Docker image build
├── docker-compose.yml      # Docker Compose orchestration
├── Caddyfile               # Caddy reverse proxy template (HTTPS)
├── netdash.service         # systemd unit file
├── .dockerignore           # Slim Docker build context
├── .gitignore              # Excludes runtime data, venv, pycache
├── README.md               # User-facing readme
├── ROADMAP.md              # Multi-platform and Capacitor analysis
├── archive/                # Old design artifacts (not used in build)
│   ├── app_librespeed.py   # Previous iteration of app.py
│   ├── speedtest_frontend.js # Old frontend (pointed at Flask, not external)
│   ├── Caddyfile           # Old Caddy config
│   ├── Dockerfile          # Old Dockerfile
│   └── docker-compose.yml  # Old compose file
└── .kilo/                  # Kilo agent config (project tooling, not app code)
```

---

## API Reference

All endpoints are same-origin (no CORS needed). The base URL is the Flask server root.

### `GET /api/stats`

Returns live network metrics. Called by the frontend on a configurable interval (default 3 seconds).

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `internet` | bool | `true` if DNS resolution succeeds |
| `conn_type` | string | `"WiFi (wlo1)"` or `"Ethernet (eth0)"` |
| `ssid` | string | WiFi network name, or `–` |
| `frequency` | string | Always `–` (placeholder) |
| `band` | string | `"2.4 GHz"`, `"5 GHz"`, `"6 GHz"`, or `–` |
| `bit_rate` | string | Negotiated PHY rate, e.g. `"1134.2 Mbit/s"`, or `–` |
| `signal_dbm` | string | Signal strength, e.g. `"-54 dBm"`, or `–` |
| `quality_pct` | int or null | Signal quality 0–100%, or `null` |
| `access_point` | string | Local IP, e.g. `"IP: 192.168.1.34"`, or `–` |
| `wifi_standard` | string | e.g. `"802.11be (WiFi 7)"`, or `–` |
| `download` | string | Live DL throughput, e.g. `"1.8 KB/s"` or `"2.13 MB/s"` |
| `upload` | string | Live UL throughput |
| `timestamp` | string | Server time, e.g. `"12:34:26 PM"` |

### `GET /api/speedtest/history`

Returns the full speedtest history as a JSON array.

### `POST /api/speedtest/history/save`

Called by the frontend after a speedtest completes. Persists the result with a snapshot of the current network state.

**Request body:**
```json
{
  "dlStatus": "945.32",
  "ulStatus": "42.18",
  "ping": "12",
  "jitter": "3.2",
  "network": {
    "internet": true,
    "conn_type": "WiFi (wlo1)",
    "ssid": "Horn",
    "band": "5 GHz",
    "bit_rate": "1134.2 Mbit/s",
    "signal_dbm": "-54 dBm",
    "quality_pct": 92,
    "access_point": "IP: 192.168.1.34",
    "wifi_standard": "802.11be (WiFi 7)"
  }
}
```

### `DELETE /api/speedtest/history/<int:index>`

Removes a single entry from the history array by its 0-based index.

### `GET /api/settings`

Returns the user settings object (highlight rules, auto-test state).

### `POST /api/settings`

Saves user settings. Request body replaces the entire settings object.

**Settings schema:**
```json
{
  "auto_test": { "minutes": 5, "last_end": 1784451347546 },
  "highlight_rules": [
    { "metric": "download", "direction": "over", "threshold": 500, "color": "#4ade80" }
  ]
}
```

### `GET /api/librespeed-servers`

Returns the LibreSpeed community server list. Fetched server-side from `https://librespeed.org/backend-servers/servers.json` and returned as-is to the browser. This proxy exists because the LibreSpeed endpoint doesn't set CORS headers.

---

## How Speedtest Works — Step by Step

1. User clicks "Run Speedtest" (or auto-test timer fires).
2. Frontend calls `GET /api/librespeed-servers` via Flask proxy → receives list of LibreSpeed community test servers.
3. Each server object has: `name`, `server` (base URL), `dlURL`, `ulURL`, `pingURL`, `getIpURL`.
4. `_st.selectServer(callback)` pings ALL servers from the list, measures latency to each, and picks the fastest one.
5. `_st.start()` begins the test:
   - **Download**: Opens 6 parallel fetch streams to `{server}{dlURL}` (e.g. `https://nyc.speedtest.server/garbage.php`). Downloads random data, measures Mbps.
   - **Ping + Jitter**: Sends small requests to `{server}{pingURL}`, measures round-trip time.
   - **Upload**: Creates blobs of random data and POSTs them to `{server}{ulURL}` in parallel streams, measures Mbps.
6. `_st.onupdate(data)` fires repeatedly during the test → updates UI with live numbers.
7. `_st.onend(aborted)` fires when the test completes → frontend snapshots the current network state via `GET /api/stats` and POSTs the combined result to `/api/speedtest/history/save`.

**Important**: The speedtest traffic flows from the **browser directly to external community servers**. The Flask backend is not involved in the speedtest data path at all — it only proxies the server list and stores the results afterward.

---

## How Live Throughput Works

1. `GET /api/stats` reads `/proc/net/dev` for the detected network interface.
2. `/proc/net/dev` contains cumulative byte counters: `rx_bytes` (column 2) and `tx_bytes` (column 10).
3. The delta between consecutive polls ÷ elapsed time = current throughput in bytes/second.
4. `fmt_speed()` converts to human-readable format: `B/s`, `KB/s`, or `MB/s`.
5. The global `_prev` dict stores the last poll's counters and timestamp.

**Gauge calibration**: The SVG arc gauges scale relative to the last speedtest result. If you scored 500 Mbps download, the DL gauge's "full arc" = 500 Mbps. If no speedtest has been run, the default cap is 10 MB/s (80 Mbps).

---

## How WiFi Diagnostics Work

The `get_host_network_info()` function in `app.py` is a multi-tier fallback chain:

| Step | Tool | What it gets |
|---|---|---|
| 1 | `ip route show` | Default route interface |
| 2 | `/proc/net/route` | Fallback interface detection |
| 3 | `/sys/class/net/*` | Wireless vs wired detection, carrier check |
| 4 | `iw dev <iface> link` | Primary: WiFi standard (EHT/HE/VHT/HT), band, signal dBm, link rate |
| 5 | `nmcli -t -f IN-USE,SSID,SIGNAL device wifi list` | Primary: SSID |
| 6 | `iwconfig <iface>` | Fallback: SSID, signal if `iw`/`nmcli` unavailable |
| 7 | Interface name pattern | Heuristic: `wlan*`/`wlo*` → WiFi, `eth*`/`en*` → Ethernet |

If any step fails, the next one is tried. If ALL fail, the metric shows `–` (en dash).

---

## How History Filtering & Highlighting Works

Both are implemented client-side in `index.html`:

**Filters**: Three filter controls (Ping, Download, Upload) with direction (`over`/`under`) and numeric threshold. `applyRowFilters()` iterates all `<tr>` rows in the history table and sets `display:none` on non-matching rows. Applied on every keystroke in the filter inputs.

**Highlight Rules**: User-defined rules stored in `/api/settings`. Each rule has: metric (ping/download/upload), direction (over/under), threshold, and a hex color. `renderHistory()` checks each row against all rules; the last matching rule's color is used as a left border + tinted background. Rules are additive — later rules override earlier ones.

**Auto-test persistence**: The auto-test timer state (interval minutes + `last_end` timestamp) is stored in `/api/settings`. On page load, `restoreAutoState()` reads the saved state and resumes the countdown from where it left off. This survives page reloads and server restarts.

---

## Running the App

### Bare metal (Linux)

```bash
pip install flask waitress
python3 app.py
# → http://localhost:5000
```

For production persistence:
```bash
sudo cp netdash.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now netdash
```

### Docker

```bash
docker compose up -d --build
# → http://localhost:5000
```

`network_mode: host` gives the container access to the host's network interfaces and `/proc/net/dev` for accurate throughput stats and WiFi diagnostics (on real Linux, not Docker Desktop).

### Behind reverse proxy (HTTPS)

The existing `caddy-proxy` container routes `netdash.local` → `host.docker.internal:5000` with TLS certs from `/home/rr/NovityMedia/proxy/certs/`. To add HTTPS for a different domain, edit `Caddyfile` in the repo root and use the optional Caddy service block in `docker-compose.yml`.

---

## Responsive Breakpoints

The CSS has three breakpoints in `index.html`:

| Breakpoint | Layout |
|---|---|
| Default (>768px) | 3-column gauges, 5-column info strip, full history table |
| ≤768px (tablet) | 3-column gauges, 3-column strip, scrollable history table |
| ≤480px (phone) | 1-column gauges, 2-column strip, scrollable history, stacked filters |

Touch devices (`@media (hover: none)`) always show delete buttons and tooltip icons — no hover required.

---

## Production Considerations

### What was fixed (vs. the original)

| Issue | Original | Fixed |
|---|---|---|
| WSGI server | `app.run()` — Flask dev server, single-threaded, fragile | `waitress.serve()` — 8 threads, production-grade |
| Process supervision | Bare `python3 app.py &` — dies silently | systemd service with `Restart=always` |
| Dead code | `/backend/garbage`, `/backend/upload`, `/backend/ping`, `/backend/getIp` endpoints (leftover from old design where Flask was the speedtest server) | Removed |
| Docker files | Missing from repo root (were in `archive/`) | Fixed and moved to root |

### Known limitations

- **WiFi diagnostics require bare-metal Linux** with `network-manager`, `iw`, and `wireless-tools` installed. Docker and Docker Desktop show dashes for WiFi metrics.
- **Throughput stats require `/proc/net/dev`** (Linux only). macOS/Windows would need `psutil` as a cross-platform replacement — see `ROADMAP.md`.
- **Speedtest depends on external LibreSpeed community servers** being reachable. If none are available, the test fails gracefully with "No servers available."
- **No authentication.** Designed for trusted home networks behind a firewall. If exposed to the internet, put it behind a reverse proxy with auth (Caddy supports `basicauth`).
- **In-memory state.** `_speedtest_history`, `_prev` (throughput counters), and `_host_iface` are global Python variables. They survive across requests but are lost on server restart. History and settings are persisted to JSON files so they survive restarts.

---

## Quick Reference for Common Tasks

```bash
# Restart the app
sudo systemctl restart netdash

# View logs
journalctl -u netdash -f

# Pull latest from git and restart
git pull && sudo systemctl restart netdash

# Rebuild Docker
docker compose up -d --build

# Test the API directly
curl http://localhost:5000/api/stats | jq

# Test through Caddy proxy (HTTPS)
curl -k https://netdash.local/api/stats | jq
```
