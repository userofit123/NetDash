from flask import Flask, jsonify, send_file, request, Response
import re, time, socket, os, json
app = Flask(__name__, static_folder='static', static_url_path='/static')

# ── Speedtest architecture ───────────────────────────────────────
# LibreSpeed JS (speedtest.js + speedtest_worker.js) runs in the
# browser and connects to community test servers (fetched via the
# /api/librespeed-servers proxy).  The browser opens multiple
# parallel fetch streams — exactly like speedtest.net — so results
# are accurate and no additional software is ever required.
# The Flask backend handles live /proc/net/dev stats, WiFi diags,
# history/ settings persistence, and server-list proxy — it does
# not carry the speedtest traffic itself.

_prev = {'rx': 0, 'tx': 0, 'time': time.time()}
_host_iface = None

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'speedtest_history.json')
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'settings.json')
_speedtest_history = []

def load_history():
    global _speedtest_history
    try:
        with open(HISTORY_FILE) as f:
            _speedtest_history = json.load(f)
    except Exception:
        _speedtest_history = []

load_history()


# ── Helpers (unchanged from original) ────────────────────────────

def run(cmd):
    import subprocess
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.stdout + r.stderr
    except Exception:
        return ''

def get_host_interface():
    global _host_iface

    # 1. Try ip route show for the default route
    try:
        route_out = run(['ip', 'route', 'show'])
        match = re.search(r'default via .* dev (\S+)', route_out)
        if match:
            _host_iface = match.group(1)
            return _host_iface
        # Also try matching default route without "via" (e.g. link-local / VPN)
        match = re.search(r'default.* dev (\S+)', route_out)
        if match:
            _host_iface = match.group(1)
            return _host_iface
    except Exception:
        pass

    # 2. Try /proc/net/route for the default route interface (binary-format table)
    try:
        with open('/proc/net/route') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 8 and parts[1] == '00000000' and parts[7] == '00000000':
                    # Default route: dest=0.0.0.0, mask=0.0.0.0
                    _host_iface = parts[0]
                    return _host_iface
    except Exception:
        pass

    # 3. Dynamic discovery via /sys/class/net/ — prefer wireless, then any with carrier
    try:
        ifaces = [i for i in os.listdir('/sys/class/net/') if i != 'lo']
        # Prefer wireless interfaces
        for iface in ifaces:
            if os.path.exists(f'/sys/class/net/{iface}/wireless') or \
               os.path.exists(f'/sys/class/net/{iface}/phy80211'):
                _host_iface = iface
                return _host_iface
        # Then prefer interfaces that have a carrier (link up)
        for iface in ifaces:
            try:
                with open(f'/sys/class/net/{iface}/carrier') as cf:
                    if cf.read().strip() == '1':
                        _host_iface = iface
                        return _host_iface
            except Exception:
                pass
        # Fallback: first non-loopback interface
        if ifaces:
            _host_iface = ifaces[0]
            return _host_iface
    except Exception:
        pass

    # 4. Absolute last resort: parse /proc/net/dev for any non-lo interface
    try:
        with open('/proc/net/dev') as f:
            for line in f:
                if ':' in line:
                    iface_name = line.split(':')[0].strip()
                    if iface_name and iface_name != 'lo':
                        _host_iface = iface_name
                        return _host_iface
    except Exception:
        pass

    return 'eth0'

def get_connection_type(iface):
    # Most reliable: check /sys/class/net/<iface>/wireless/ (or phy80211)
    # These directories exist if and only if the interface is a wireless device.
    try:
        if os.path.exists(f'/sys/class/net/{iface}/wireless') or \
           os.path.exists(f'/sys/class/net/{iface}/phy80211'):
            return 'WiFi'
    except Exception:
        pass
    try:
        iwconfig_out = run(['iwconfig', iface])
        if iwconfig_out and 'IEEE' in iwconfig_out:
            return 'WiFi'
    except Exception:
        pass
    try:
        nmcli_out = run(['nmcli', 'device', 'show', iface])
        if nmcli_out and ('TYPE:' in nmcli_out or 'type:' in nmcli_out):
            lower = nmcli_out.lower()
            if 'wifi' in lower:
                return 'WiFi'
            elif 'ethernet' in lower:
                return 'Ethernet'
    except Exception:
        pass
    # Name-based heuristics as last resort
    if 'wlan' in iface or 'wlo' in iface or 'wlp' in iface or 'wlx' in iface:
        return 'WiFi'
    elif 'eth' in iface or 'en' in iface or 'docker' in iface:
        return 'Ethernet'
    return 'Unknown'

def check_internet():
    # Resolve a real domain — actual DNS lookup proves connectivity
    try:
        socket.gethostbyname('dns.google')
        return True
    except Exception:
        pass
    # Fallback: TCP connect to a known-reachable host
    try:
        s = socket.create_connection(('8.8.8.8', 53), timeout=3)
        s.close()
        return True
    except Exception:
        pass
    return False

def get_host_network_info():
    info = {
        'ssid': '\u2013',
        'frequency': '\u2013',
        'band': '\u2013',
        'signal_dbm': '\u2013',
        'quality_pct': None,
        'bit_rate': '\u2013',
        'access_point': '\u2013',
        'wifi_standard': '\u2013',
        'conn_type_label': 'Unknown'
    }
    iface = get_host_interface()
    info['conn_type_label'] = get_connection_type(iface)
    try:
        iface_out = run(['ip', 'addr', 'show', iface])
        if 'inet ' in iface_out:
            match = re.search(r'inet\s+([\d.]+)', iface_out)
            if match:
                info['access_point'] = f"IP: {match.group(1)}"
    except Exception:
        pass
    # ── Primary: iw dev <iface> link ── most reliable signal / rate / band / standard
    try:
        iw_out = run(['iw', 'dev', iface, 'link'])
        if iw_out:
            # WiFi standard
            if 'EHT' in iw_out:
                info['wifi_standard'] = '802.11be (WiFi 7)'
            elif 'HE-' in iw_out or 'HE MCS' in iw_out:
                info['wifi_standard'] = '802.11ax (WiFi 6)'
            elif 'VHT' in iw_out:
                info['wifi_standard'] = '802.11ac (WiFi 5)'
            elif 'HT' in iw_out:
                info['wifi_standard'] = '802.11n (WiFi 4)'

            # Band — use highest freq (handles MLO dual-link)
            freqs = re.findall(r'freq:\s+([\d.]+)', iw_out)
            if freqs:
                freq = max(float(f) for f in freqs)
                if freq < 3000:
                    info['band'] = '2.4 GHz'
                elif freq < 6000:
                    info['band'] = '5 GHz'
                else:
                    info['band'] = '6 GHz'

            # Signal strength (dBm) — real measurement from the driver
            sig_match = re.search(r'signal:\s+([-\d]+)\s*dBm', iw_out)
            if sig_match:
                dbm = int(sig_match.group(1))
                info['signal_dbm'] = f'{dbm} dBm'
                # Convert dBm → quality %:  -30 dBm = 100%,  -90 dBm = 0%
                info['quality_pct'] = max(0, min(100, int(2 * (dbm + 100))))

            # Link rate (RX bitrate) — actual negotiated PHY rate
            rate_match = re.search(r'rx bitrate:\s+([\d.]+)\s*MBit/s', iw_out)
            if rate_match:
                info['bit_rate'] = rate_match.group(1) + ' Mbit/s'
    except Exception:
        pass

    # ── SSID: use nmcli wifi list (terse, without BSSID to avoid escaped-colon bug) ──
    try:
        nmcli_out = run(['nmcli', '-t', '-f', 'IN-USE,SSID,SIGNAL', 'device', 'wifi', 'list'])
        if nmcli_out:
            for line in nmcli_out.split('\n'):
                # Terse format:  IN-USE:SSID:SIGNAL   (no BSSID = no escaped colons)
                if line.startswith('*:'):
                    parts = line.split(':', 2)  # split at most 2 colons: [*, SSID, SIGNAL]
                    if len(parts) >= 2 and parts[1]:
                        info['ssid'] = parts[1]
                    # If we didn't get signal from iw, use nmcli's percentage
                    if info['quality_pct'] is None and len(parts) >= 3 and parts[2].isdigit():
                        pct = int(parts[2])
                        info['quality_pct'] = pct
                        info['signal_dbm'] = f'{int(-100 + (pct * 0.7))} dBm'
                    break
    except Exception:
        pass

    # ── Fallback: iwconfig for SSID / signal ──
    if info['ssid'] == '\u2013' or info['signal_dbm'] == '\u2013':
        try:
            iwconfig_out = run(['iwconfig', iface])
            if iwconfig_out:
                if info['ssid'] == '\u2013' and 'ESSID' in iwconfig_out:
                    essid_match = re.search(r'ESSID:"(.+?)"', iwconfig_out)
                    if essid_match:
                        info['ssid'] = essid_match.group(1)
                if info['signal_dbm'] == '\u2013':
                    sig_match = re.search(r'Signal level[=:](\S+)', iwconfig_out)
                    if sig_match:
                        info['signal_dbm'] = sig_match.group(1)
        except Exception:
            pass
    return info, iface

def get_proc_bytes(iface):
    try:
        with open('/proc/net/dev') as f:
            for line in f:
                if iface in line:
                    p = line.split()
                    return int(p[1]), int(p[9])
    except Exception:
        pass
    return 0, 0

def fmt_speed(bps):
    if bps >= 1_000_000: return f"{bps/1_000_000:.2f} MB/s"
    if bps >= 1_000:     return f"{bps/1_000:.1f} KB/s"
    return f"{int(bps)} B/s"


# ── History: the JS frontend POSTs results here when a test ends ──

@app.route('/api/speedtest/history/save', methods=['POST'])
def save_result():
    """Frontend calls this after a test completes to persist the result."""
    global _speedtest_history
    data = request.get_json(silent=True) or {}
    entry = {
        'timestamp': time.strftime('%Y-%m-%d %I:%M:%S %p'),
        'ping':      f"{data.get('ping', '–')} ms",
        'download':  f"{data.get('dlStatus', '–')} Mbps",
        'upload':    f"{data.get('ulStatus', '–')} Mbps",
        'jitter':    f"{data.get('jitter', '–')} ms",
        'network':   data.get('network', {}),
    }
    _speedtest_history.append(entry)
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(_speedtest_history, f, indent=2)
    except Exception:
        pass
    return jsonify({'status': 'saved'})


@app.route('/api/speedtest/history')
def speedtest_history():
    return jsonify(_speedtest_history)


@app.route('/api/speedtest/history/<int:index>', methods=['DELETE'])
def delete_history_entry(index):
    global _speedtest_history
    if 0 <= index < len(_speedtest_history):
        _speedtest_history.pop(index)
        try:
            with open(HISTORY_FILE, 'w') as f:
                json.dump(_speedtest_history, f, indent=2)
        except Exception:
            pass
        return jsonify({'status': 'deleted'})
    return jsonify({'status': 'not found'}), 404


# ── User settings: highlight rules, auto-test state ──

def _load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_settings(data):
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


@app.route('/api/settings', methods=['GET', 'POST'])
def user_settings():
    if request.method == 'GET':
        return jsonify(_load_settings())
    data = request.get_json(silent=True) or {}
    _save_settings(data)
    return jsonify({'status': 'saved'})


import urllib.request


# ── Proxy the LibreSpeed server list (browser can't fetch cross-origin) ──

@app.route('/api/librespeed-servers')
def librespeed_servers():
    """Return the community server list — fetched server-side to avoid CORS."""
    try:
        resp = urllib.request.urlopen(
            'https://librespeed.org/backend-servers/servers.json', timeout=10
        )
        return Response(resp.read(), mimetype='application/json')
    except Exception:
        return jsonify([])


# ── Live network stats (unchanged) ───────────────────────────────

@app.route('/api/stats')
def stats():
    global _prev
    internet = check_internet()
    net_info, iface = get_host_network_info()
    conn_display = f"{net_info['conn_type_label']} ({iface})"
    now = time.time()
    rx, tx = get_proc_bytes(iface)
    elapsed = now - _prev['time']
    dl = fmt_speed((rx - _prev['rx']) / elapsed) if elapsed > 0 else '\u2013'
    ul = fmt_speed((tx - _prev['tx']) / elapsed) if elapsed > 0 else '\u2013'
    _prev = {'rx': rx, 'tx': tx, 'time': now}
    return jsonify({
        'internet':      internet,
        'conn_type':     conn_display,
        'ssid':          net_info['ssid'],
        'frequency':     net_info['frequency'],
        'band':          net_info['band'],
        'bit_rate':      net_info['bit_rate'],
        'signal_dbm':    net_info['signal_dbm'],
        'quality_pct':   net_info['quality_pct'],
        'access_point':  net_info['access_point'],
        'wifi_standard': net_info['wifi_standard'],
        'download':      dl,
        'upload':        ul,
        'timestamp':     time.strftime('%I:%M:%S %p'),
    })


@app.route('/')
def index():
    return send_file('index.html')


# LibreSpeed loads the worker from "/speedtest_worker.js" (hardcoded in speedtest.js)
@app.route('/speedtest_worker.js')
def serve_worker():
    return send_file('static/speedtest_worker.js')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
