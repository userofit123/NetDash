# NetDash — Roadmap for Multi-User, Cross-Platform & Mobile

## 1. Current Architecture Recap

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR HOME SERVER                          │
│  ┌──────────────────────┐    ┌────────────────────────────┐  │
│  │   Flask (app.py)     │    │   Linux system tools       │  │
│  │   port 5000, HTTP    │    │   /proc/net/dev, iw,       │  │
│  │                      │    │   nmcli, iproute2          │  │
│  │  Endpoints:          │    │                            │  │
│  │  /api/stats          │◄───┤  Live throughput, WiFi     │  │
│  │  /api/speedtest/*    │    │  diags, connection type    │  │
│  │  /api/settings       │    └────────────────────────────┘  │
│  │  /api/librespeed-*   │                                    │
│  └──────┬───────────────┘                                    │
│         │ serves index.html + static JS                       │
└─────────┼────────────────────────────────────────────────────┘
          │ HTTP
          ▼
   ┌──────────────┐       ┌──────────────────────────┐
   │  Browser     │──────▶│  External LibreSpeed      │
   │  (JS/SPA)    │       │  Community Servers        │
   │              │       │  (mixed HTTP/HTTPS)       │
   └──────────────┘       └──────────────────────────┘
```

**Key fact**: The speedtest JS in the browser connects directly to external LibreSpeed community servers. The Flask server does NOT proxy speedtest traffic — it only proxies the server list to avoid CORS.

---

## 2. Making It Work on Other People's Servers

### 2.1 What's already portable

| Component | Portability | Notes |
|---|---|---|
| Flask app.py | ✅ Works anywhere Python 3 runs | Only depends on `flask` |
| Live throughput | ⚠️ Linux only | `/proc/net/dev` — no macOS/Windows equivalent |
| WiFi diagnostics | ⚠️ Linux only | `iw`, `nmcli`, `iwconfig` — gracefully degrades to dashes |
| Speedtest JS | ✅ Works in any browser | Needs internet access to external servers |
| History/settings | ✅ Local JSON files | `data/` directory, relative paths |

### 2.2 What needs to change

#### A. Remove Linux lock-in for throughput stats
- **Problem**: `/proc/net/dev` doesn't exist on macOS or Windows.
- **Solution**: Use `psutil` (`pip install psutil`) which provides cross-platform network I/O counters:
  ```python
  import psutil
  net_io = psutil.net_io_counters(pernic=True)
  bytes_sent = net_io[iface].bytes_sent
  bytes_recv = net_io[iface].bytes_recv
  ```
- **Priority**: Medium — makes the app usable on any OS for basic monitoring.

#### B. Remove Linux lock-in for WiFi diagnostics
- **Problem**: `iw`, `nmcli`, `iwconfig` are Linux-only.
- **Solution**: `psutil` can detect connection type. For SSID/signal on macOS, use `/System/Library/PrivateFrameworks/Apple80211.framework` or `airport -I`. On Windows, `netsh wlan show interfaces`.
- **Priority**: Low — WiFi diags gracefully degrade to dashes today.

#### C. Provide a Docker image
- Already partly in `archive/` — needs to be moved to root, updated.
- Docker removes OS dependency headaches for users.
- **Priority**: High — Docker is the standard way to ship self-hosted apps.

---

## 3. HTTPS Requirement

### 3.1 Why HTTPS is needed

The **Flask server itself** doesn't strictly need HTTPS (it's just a dashboard). But:

1. **Speedtest mixed content**: If you serve NetDash over HTTPS, the browser blocks HTTP requests from the LibreSpeed JS to community test servers that only support HTTP. Many community servers are HTTP-only.
2. **Public access**: If you expose this to the internet, you MUST use HTTPS for security.
3. **Capacitor WebView**: Less restrictive than browsers — you can allow cleartext traffic.

### 3.2 Solutions (in order of simplicity)

**Option 1: Reverse proxy with Caddy (recommended)**
```bash
# Caddy auto-obtains Let's Encrypt certificates
# caddy reverse-proxy --from netdash.your-domain.com --to :5000
```
- Zero config TLS
- Flask stays HTTP internally
- Speedtest still breaks for HTTP-only external servers

**Option 2: Self-hosted speedtest backend**
- Re-add `/backend/garbage`, `/backend/upload`, `/backend/ping` endpoints to Flask
- They proxy/download real internet data (like the old `garbage()` design)
- Since the JS connects to same-origin endpoints, no mixed content issues
- HTTP → HTTPS → HTTP chain lives entirely on your server
- This is the **most robust** solution — works regardless of external server availability

**Option 3: Filter to HTTPS-only servers**
- In the `/api/librespeed-servers` proxy, filter the server list to only include servers whose URL starts with `https://`
- Simplest code change, but server selection may be limited

### 3.3 Recommended deployment stack

```
Internet → Caddy (HTTPS, auto-TLS) → Flask :5000 (HTTP)
                │
                ├── /api/*        → Flask
                ├── /static/*     → Flask (or Caddy directly)
                └── /backend/*    → Flask (self-hosted speedtest)
```

---

## 4. Capacitor / Android App — Feasibility Analysis

### 4.1 Can this be converted to an Android app? **Yes, with caveats.**

Capacitor wraps web assets (HTML/JS/CSS) in a native WebView. The HTML frontend works as-is in a WebView. The question is: **where does the backend live?**

### 4.2 Three architectural options

#### Option A: Thin Client (simplest, 1-2 hours)
```
┌─────────────────────────┐      HTTPS      ┌────────────────────┐
│  Android Capacitor App  │ ──────────────▶  │  Home Server       │
│  (WebView loads your    │                  │  Flask + Caddy     │
│   server's URL)         │                  │  Full stack        │
└─────────────────────────┘                  └────────────────────┘
```
- The Capacitor app is just a wrapper that loads `https://your-server.com`
- **Pros**: Zero backend rewrite, full WiFi data from server, quick to build
- **Cons**: Requires server to be always online; shows the server's network, not the phone's; needs internet

#### Option B: Hybrid — Local Stats + Remote History (3-5 days)
```
┌──────────────────────────────────────────────────────────────────┐
│  Android Capacitor App                                           │
│  ┌─────────────────────┐    ┌──────────────────────────────────┐ │
│  │  WebView (HTML/JS)  │    │  Capacitor Plugins               │ │
│  │  - Speedtest JS     │    │  @capacitor/network (internet)   │ │
│  │  - All UI/gauges    │    │  Custom plugin (TrafficStats)    │ │
│  │  - History table    │    │  Custom plugin (WifiManager)     │ │
│  └─────────────────────┘    └──────────────────────────────────┘ │
│         │                              │                          │
│         ▼                              ▼                          │
│  ┌─────────────────┐    ┌──────────────────────────────────────┐ │
│  │  localStorage   │    │  Android Native APIs                  │ │
│  │  (settings,     │    │  TrafficStats → live throughput      │ │
│  │   history)      │    │  WifiManager  → SSID, signal, band   │ │
│  └─────────────────┘    │  ConnectivityManager → conn type     │ │
│                         └──────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```
- Reimplement the `/api/stats` data source using Capacitor plugins
- Speedtest JS connects directly to external LibreSpeed servers from the phone
- History/settings stored in `localStorage` or Capacitor Preferences plugin
- **Pros**: Full standalone app, measures phone's actual network, works without a server
- **Cons**: Significant rewrite of the data layer; custom Capacitor plugins needed

#### Option C: Dual-Mode (5-8 days)
```
┌──────────────────────────────────────────────────────┐
│  Capacitor App                                       │
│  ┌────────────────────────────────────────────────┐  │
│  │  window.Capacitor?                             │  │
│  │    ├── YES → use Capacitor plugins (phone)     │  │
│  │    └── NO  → use fetch('/api/stats') (server)  │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```
- Detect runtime environment; use appropriate data source
- Works as a standalone phone app AND as a remote dashboard for your server
- **Pros**: Most flexible, one codebase for everything
- **Cons**: Most development effort

### 4.3 What needs native Capacitor plugins

| Feature | Android API | Difficulty |
|---|---|---|
| Live throughput (DL/UL) | `TrafficStats.getTotalRxBytes()` / `getUidRxBytes()` | Medium — rate calculation needed |
| WiFi SSID | `WifiManager.getConnectionInfo().getSSID()` | Easy — but requires `ACCESS_FINE_LOCATION` on Android 8+ |
| Signal strength (dBm) | `WifiManager.getConnectionInfo().getRssi()` | Easy |
| Frequency band | `WifiManager.getConnectionInfo().getFrequency()` | Easy |
| WiFi standard (ax/ac/n) | Parse frequency + link speed heuristics | Medium |
| Connection type | `ConnectivityManager` → `@capacitor/network` | Easy (existing plugin) |
| Internet check | `Network` plugin `getStatus()` | Easy (existing plugin) |
| Speedtest | LibreSpeed JS runs in WebView as-is | Already works |

### 4.4 HTTPS in Capacitor

Capacitor WebViews are **more permissive** than browsers:
- You can allow cleartext (HTTP) traffic via `AndroidManifest.xml`:
  ```xml
  <application android:usesCleartextTraffic="true">
  ```
- Or allow it for specific domains only via `network_security_config.xml`
- This means the speedtest JS can connect to HTTP LibreSpeed servers without blocked requests
- **Ironically, the speedtest works BETTER in Capacitor than in an HTTPS browser** — no mixed content blocking

### 4.5 Build steps for a Capacitor thin client (Option A)

```bash
# 1. Create Capacitor project
npm init @capacitor/app netdash-mobile
cd netdash-mobile

# 2. Add Android platform
npm install @capacitor/android
npx cap add android

# 3. Replace the default app with a redirect to your server
#    In capacitor.config.ts, set server.url to your HTTPS server
#    OR use a simple HTML page that redirects

# 4. Build and open in Android Studio
npx cap sync
npx cap open android
```

---

## 5. Action Items — Prioritized Checklist

### Phase 1: Multi-Server Deployment (1-2 days)
- [ ] Move `archive/Dockerfile` and `archive/docker-compose.yml` to root, update for current code
- [ ] Create `requirements.txt` (`flask` only)
- [ ] Add `psutil` for cross-platform throughput stats
- [ ] Add Caddyfile to root for HTTPS reverse proxy
- [ ] Add self-hosted speedtest mode (re-add `/backend/*` endpoints) so speedtest works over HTTPS without external server dependency

### Phase 2: Public-Ready (2-3 days)
- [ ] HTTPS via Caddy with auto Let's Encrypt
- [ ] Filter `/api/librespeed-servers` to prefer HTTPS servers, fall back to self-hosted
- [ ] Add optional basic auth or Tailscale for access control
- [ ] Environment variable for port, data directory

### Phase 3: Capacitor / Android (3-7 days depending on scope)
- [ ] Scaffold Capacitor project with thin-client mode (Option A above)
- [ ] Implement native Capacitor plugin for `TrafficStats` (live throughput)
- [ ] Implement native Capacitor plugin for `WifiManager` (SSID, signal, band, freq)
- [ ] Add runtime detection: use plugins if native, use `/api/stats` if web
- [ ] Store history/settings in localStorage for offline capability
- [ ] `AndroidManifest.xml` — cleartext traffic, location permission for SSID

---

## 6. Summary Table

| Goal | Effort | Key Changes |
|---|---|---|
| Run on other Linux servers | Low | Dockerize, requirements.txt |
| Run on macOS/Windows | Medium | Replace `/proc/net/dev` with `psutil` |
| HTTPS for public access | Low | Caddy reverse proxy + self-hosted speedtest |
| Capacitor thin client (remote server) | Low | Wrap your server URL in Capacitor |
| Capacitor standalone (phone's own network) | High | Native plugins for TrafficStats + WifiManager |
| Dual-mode (web + native) | High | Runtime detection + dual data sources |

---

## 7. Self-Hosted Speedtest Endpoints (Reference)

These were the original Flask endpoints that turned your server into a LibreSpeed-compatible test endpoint. They were removed during cleanup because the current HTML uses external community servers. They need to be re-added if you want HTTPS-safe speedtests:

| Endpoint | Purpose |
|---|---|
| `GET /backend/garbage?ckSize=20` | Streams random/downloaded bytes for download test |
| `POST /backend/upload` | Receives blobs, discards them, measures upload |
| `GET /backend/ping` | Returns `pong` for latency measurement |
| `GET /backend/getIp` | Returns client IP |

The old implementation in `archive/app_librespeed.py` lines 280-332 contains the reference code.
