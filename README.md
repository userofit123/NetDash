# NetDash — Network Diagnostics Dashboard

Real-time network monitoring dashboard with live speed gauges, WiFi diagnostics, speed testing, and test history.

![NetDash Dashboard](screenshots/dashboard.png)

## Features

- Live download/upload throughput with SVG arc gauges
- WiFi diagnostics: SSID, signal strength (dBm), band, WiFi standard, link rate
- Internet connectivity check
- One-click speedtest with persistent history
- Auto-detects Ethernet vs WiFi, hides irrelevant metrics
- Tooltips on every metric explaining what it means

## Installation

### Direct (Python)

```bash
pip install flask
python3 app.py
```

Open **http://localhost:5000**. Gives full WiFi data.

To keep running after closing the terminal, use a systemd service:

```ini
# /etc/systemd/system/netdash.service
[Unit]
Description=NetDash
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/NetDash
ExecStart=/usr/bin/python3 /path/to/NetDash/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now netdash
```

### Docker

```bash
git clone https://github.com/userofit123/NetDash.git
cd NetDash
docker compose up -d --build
```

Open **http://localhost:5000**. Auto-restarts on reboot.

To add HTTPS via Caddy, edit `Caddyfile` with your domain, then uncomment the Caddy service block in `docker-compose.yml`.

> On Docker Desktop, `network_mode: host` runs inside a VM, so WiFi metrics (SSID, signal, band) won't appear. Live speeds and speedtest work fine. Use the direct method for full WiFi data.

## Troubleshooting

**WiFi data shows dashes:** Install `network-manager`, `iw`, and `wireless-tools`.

**Speedtest button fails:** Ensure your browser can reach external LibreSpeed test servers (check firewall/proxy).

**Port 5000 in use:** Change the port at the bottom of `app.py`.

## How it works

| Metric | Source |
|---|---|
| Download/Upload speed | `/proc/net/dev` byte counters, polled on interval |
| Internet status | DNS resolution of `dns.google` |
| Connection type, SSID, signal, band | `nmcli device wifi list` and `ip route show` |
| WiFi standard, link rate, frequency | `iw dev <iface> link` |
| Speedtest | LibreSpeed JS in the browser, connects to community test servers via `/api/librespeed-servers` proxy |

## API

| Endpoint | Method | Returns |
|---|---|---|
| `/api/stats` | GET | All live network metrics |
| `/api/speedtest/history` | GET | All past results with network snapshots |
| `/api/speedtest/history/save` | POST | Persist a completed test result |
| `/api/speedtest/history/<id>` | DELETE | Remove a history entry |
| `/api/settings` | GET/POST | User preferences (highlight rules, auto-test) |
| `/api/librespeed-servers` | GET | Proxied LibreSpeed server list for speedtest |

## License

MIT
