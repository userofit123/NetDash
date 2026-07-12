# NetDash — Network Diagnostics Dashboard

A real-time network diagnostics dashboard that monitors your internet connection, WiFi signal strength, live throughput, and runs speed tests. Single HTML file, no build step, no JavaScript framework — just Python + Flask on the backend.

![NetDash Dashboard](screenshots/dashboard.png)

## Features

- **Live throughput gauges** — real-time download/upload speeds with SVG arc gauges
- **WiFi diagnostics** — SSID, signal strength (dBm), frequency band, WiFi standard (WiFi 4/5/6/6E), link rate
- **Internet connectivity** — DNS-based online/offline detection
- **Speedtest** — one-click test with ping, download, and upload results
- **Speedtest history** — results saved to disk with a full network snapshot at test time
- **Smart UI** — auto-detects Ethernet vs WiFi, hides irrelevant metrics
- **Tooltips** — hover over any `?` icon for an explanation of what each metric means

## Screenshots

| WiFi | Ethernet | Speedtest |
|---|---|---|
| ![WiFi](screenshots/wifi.png) | ![Ethernet](screenshots/ethernet.png) | ![Speedtest](screenshots/speedtest.png) |

> To add your own screenshots, save them to the `screenshots/` folder and update the paths above.

---

## Installation

NetDash runs on **Linux**. There are two ways to install it:

| Method | WiFi data | Easiest to set up | Survives reboot |
|---|---|---|---|
| **Direct (Python)** | Full | No (install Python deps) | Needs extra setup (systemd) |
| **Docker** | Limited on Docker Desktop; full on native Linux | Yes (Docker handles everything) | Yes (restart: unless-stopped) |

> **Recommendation:** If you're on a Linux desktop or laptop, use the **Direct** method — it gives you full WiFi signal data, band detection, and interface names. The Docker method works best on headless servers or if you already use Docker for everything.

---

### Method 1: Run directly with Python (recommended)

This runs NetDash as a normal Python program on your machine. It has full access to your network interfaces, so WiFi metrics work completely.

#### Step 1: Make sure Python is installed

Most Linux distributions come with Python already installed. Open a terminal and check:

```bash
python3 --version
```

You should see `Python 3.8` or higher. If not, install it:

```bash
# Ubuntu / Debian
sudo apt install python3 python3-pip

# Fedora
sudo dnf install python3 python3-pip

# Arch
sudo pacman -S python python-pip
```

#### Step 2: Clone the repository

```bash
git clone https://github.com/userofit123/NetDash.git
cd NetDash
```

If you don't have `git`, download the ZIP from GitHub and extract it, or install git with `sudo apt install git`.

#### Step 3: Install the Python dependencies

```bash
pip install flask speedtest-cli
```

If you get a "pip: command not found" error, try `pip3` instead of `pip`. If you get a permission error, add `--user`:

```bash
pip install --user flask speedtest-cli
```

#### Step 4: Run it

```bash
python3 app.py
```

You should see:

```
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.x.x:5000
```

#### Step 5: Open the dashboard

Open your browser and go to **http://localhost:5000**. The dashboard appears and begins updating every 3 seconds.

#### Optional: Make it start automatically on boot (systemd)

Create a systemd service file so NetDash runs in the background and starts when your computer boots:

```bash
sudo nano /etc/systemd/system/netdash.service
```

Paste this in (replace `/home/youruser/NetDash` with your actual path):

```ini
[Unit]
Description=NetDash Network Diagnostics
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/youruser/NetDash
ExecStart=/usr/bin/python3 /home/youruser/NetDash/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable netdash
sudo systemctl start netdash
```

Check that it's running:

```bash
sudo systemctl status netdash
```

---

### Method 2: Run with Docker

Docker runs NetDash in an isolated container. No Python installation needed — Docker handles everything.

#### Step 1: Install Docker

If you don't have Docker installed:

- **Ubuntu / Debian / Fedora:** Follow the official guide at [docs.docker.com/engine/install](https://docs.docker.com/engine/install/)
- Or use the convenience script: `curl -fsSL https://get.docker.com | sudo sh`

After installing, make sure the Docker daemon is running:

```bash
sudo systemctl enable docker --now
```

On **Docker Desktop** (GUI app for Linux/Mac/Windows), open the application.

#### Step 2: Clone the repository

```bash
git clone https://github.com/userofit123/NetDash.git
cd NetDash
```

#### Step 3: Build and start the container

```bash
docker compose up -d --build
```

This command does three things:
1. **`--build`** — builds the Docker image from the `Dockerfile` (installs Python, Flask, speedtest-cli, and networking tools)
2. **`up`** — creates and starts the container
3. **`-d`** — runs it in the background (detached mode)

The first build takes about 30 seconds. Subsequent starts are instant.

#### Step 4: Open the dashboard

Go to **http://localhost:5000**.

#### Step 5: Verify it's running

```bash
docker ps --filter name=netdash
```

You should see `netdash` with status `Up`.

#### Managing the container

```bash
# Stop it
docker compose down

# Start it again
docker compose up -d

# View logs
docker logs netdash

# Rebuild after pulling code updates
docker compose up -d --build
```

The container auto-restarts if it crashes or when your machine reboots (configured via `restart: unless-stopped`).

#### Important: Docker Desktop vs native Linux

- **Docker Desktop** (the GUI app on Linux, Mac, or Windows): The container uses `network_mode: host` to access network data, but Docker Desktop runs inside a virtual machine, so the container only sees the VM's virtual interfaces — not your real WiFi adapter. **WiFi metrics (SSID, signal, band, standard, link rate) will not appear.** Download/upload speeds and speedtest will still work.
- **Native Linux Docker** (Docker Engine installed directly): `network_mode: host` gives the container full access to your real network interfaces. All metrics work.

If you're on Docker Desktop and want full WiFi data, use Method 1 instead.

---

## Troubleshooting

### "pip: command not found"
Use `pip3` instead, or install pip: `sudo apt install python3-pip`.

### "speedtest-cli: command not found"
The `speedtest-cli` package installs a command-line tool. Make sure it's installed: `pip install speedtest-cli`. If the speedtest button fails silently, run `speedtest-cli --simple` in a terminal to see the error.

### Port 5000 is already in use
Something else is using port 5000. Change the port in `app.py` (last line: `app.run(host='0.0.0.0', port=5000)`) — change `5000` to another number like `5050`.

### WiFi data shows dashes even on WiFi
The `nmcli` and `iw` commands might not be installed. Install them:
```bash
# Ubuntu / Debian
sudo apt install network-manager iw wireless-tools

# Fedora
sudo dnf install NetworkManager-wifi iw wireless-tools

# Arch
sudo pacman -S networkmanager iw wireless_tools
```

### Speedtest button does nothing
The speedtest runs in the background for 30–60 seconds. The status text changes to "Running speedtest…" — wait for it. If it fails, an error message appears. Check that `speedtest-cli --simple` works in your terminal.

### "Connection refused" when opening localhost:5000
The Flask server isn't running. Run `python3 app.py` in a terminal and look for error messages. Common issues: Python not installed, Flask not installed, or port already in use.

---

## How It Works

| Metric | How it's measured |
|---|---|
| Download / Upload speed | Reads `/proc/net/dev` byte counters, computes delta between polls |
| Internet status | Attempts DNS resolution of `8.8.8.8` |
| Connection type | Reads `ip route show` to find the default route interface, then checks if it's WiFi or Ethernet via `iwconfig` / `nmcli` |
| SSID | `nmcli device wifi list` — parses the line marked with `*` (current connection) |
| Signal strength | Same `nmcli` output — signal percentage converted to approximate dBm |
| WiFi standard | `iw dev <iface> link` output — detects HE (WiFi 6), VHT (WiFi 5), HT (WiFi 4) |
| Frequency band | `iw dev <iface> link` — extracts `freq:` value and classifies as 2.4 / 5 / 6 GHz |
| Link rate | `nmcli device wifi list` — the RATE column for the current connection |
| Access point IP | `ip addr show <iface>` — extracts the `inet` address |
| Speedtest | Runs `speedtest-cli --simple` in a background thread, parses the ping/download/upload values |

---

## API Reference

All responses are JSON.

| Endpoint | Method | Returns |
|---|---|---|
| `/api/stats` | GET | All live network metrics (internet status, connection type, SSID, band, signal, speeds, timestamp) |
| `/api/speedtest/run` | POST | `{"status": "started"}` — begins a speed test in the background |
| `/api/speedtest/result` | GET | Current test status (`running` boolean) and result when complete (ping, download, upload, timestamp) |
| `/api/speedtest/history` | GET | Array of all past speed test results, each with a `network` snapshot |

---

## Project Structure

```
netdash/
  app.py                  # Flask backend — API routes + network detection logic
  index.html              # Complete frontend — HTML, CSS, and JavaScript in one file
  Dockerfile              # Docker image definition (Alpine Linux + Python + tools)
  docker-compose.yml      # Docker Compose config (host networking, auto-restart)
  speedtest_history.json  # Speed test history (auto-created, gitignored)
  screenshots/            # Screenshot images for the README
  .gitignore
  README.md
```

---

## License

MIT — use it, modify it, share it.
