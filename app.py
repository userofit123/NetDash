from flask import Flask, jsonify, send_file
import subprocess, re, time, threading, socket, os

app = Flask(__name__)

_prev = {'rx': 0, 'tx': 0, 'time': time.time()}
_speedtest_running = False
_speedtest_result = None
_host_iface = None

def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
        return r.stdout + r.stderr
    except:
        return ''

def get_host_interface():
    """Detect the primary network interface on the host"""
    global _host_iface
    
    try:
        # Get the default route interface
        route_out = run(['ip', 'route', 'show'])
        match = re.search(r'default via .* dev (\S+)', route_out)
        if match:
            _host_iface = match.group(1)
            return _host_iface
    except:
        pass
    
    # Fallback: try common interface names
    for iface in ['eth0', 'wlan0', 'enp0s3', 'wlp3s0', 'eno1', 'wlo1']:
        try:
            with open(f'/proc/net/dev') as f:
                if iface in f.read():
                    _host_iface = iface
                    return _host_iface
        except:
            pass
    
    return 'eth0'

def get_connection_type(iface):
    """Determine if connection is WiFi or Ethernet"""
    try:
        # Check if it's a WiFi interface using iwconfig
        iwconfig_out = run(['iwconfig', iface])
        if iwconfig_out and 'IEEE' in iwconfig_out:
            return 'WiFi'
    except:
        pass
    
    # Check using nmcli device show
    try:
        nmcli_out = run(['nmcli', 'device', 'show', iface])
        if 'TYPE:' in nmcli_out:
            if 'wifi' in nmcli_out.lower():
                return 'WiFi'
            elif 'ethernet' in nmcli_out.lower():
                return 'Ethernet'
    except:
        pass
    
    # Fallback: check interface name pattern
    if 'wlan' in iface or 'wlo' in iface or 'wlp' in iface:
        return 'WiFi'
    elif 'eth' in iface or 'en' in iface or 'docker' in iface:
        return 'Ethernet'
    
    return 'Unknown'

def check_internet():
    """Check internet by trying DNS resolution"""
    try:
        socket.gethostbyname('8.8.8.8')
        return True
    except:
        pass
    try:
        socket.gethostbyname('google.com')
        return True
    except:
        pass
    return False

def get_host_network_info():
    """Get network info from the host system"""
    info = {
        'ssid': '—',
        'frequency': '—',
        'band': '—',
        'signal_dbm': '—',
        'quality_pct': None,
        'bit_rate': '—',
        'access_point': '—',
        'wifi_standard': '—',
        'conn_type_label': 'Unknown'
    }
    
    iface = get_host_interface()
    info['conn_type_label'] = get_connection_type(iface)
    
    # Get IP address
    try:
        iface_out = run(['ip', 'addr', 'show', iface])
        if 'inet ' in iface_out:
            match = re.search(r'inet\s+([\d.]+)', iface_out)
            if match:
                info['access_point'] = f"IP: {match.group(1)}"
    except:
        pass
    
    # Try nmcli device wifi list (currently connected network)
    try:
        nmcli_out = run(['nmcli', 'device', 'wifi', 'list'])
        if nmcli_out and '*' in nmcli_out:
            # Find the line with * (current connection)
            for line in nmcli_out.split('\n'):
                if line.startswith('*'):
                    # Use regex to parse the line more robustly
                    # Format: * BSSID SSID MODE CHAN RATE SIGNAL BARS SECURITY
                    match = re.search(r'^\*\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s+([\d\s]+Mbit/s)\s+(\d+)\s+', line)
                    if match:
                        info['ssid'] = match.group(2)
                        info['bit_rate'] = match.group(5).strip()
                        signal_pct = int(match.group(6))
                        info['quality_pct'] = signal_pct
                        # Convert percentage to dBm
                        info['signal_dbm'] = str(int(-100 + (signal_pct * 0.7))) + ' dBm'
                    break
    except:
        pass
    
    # Get WiFi standard and band using iw command
    try:
        iw_out = run(['iw', 'dev', iface, 'link'])
        if iw_out:
            # Look for standard indicators (HE, VHT, HT, 802.11ax, 802.11ac, etc.)
            if 'HE-' in iw_out or 'HE MCS' in iw_out:
                info['wifi_standard'] = '802.11ax (WiFi 6)'
            elif 'VHT' in iw_out:
                info['wifi_standard'] = '802.11ac (WiFi 5)'
            elif 'HT' in iw_out:
                info['wifi_standard'] = '802.11n (WiFi 4)'
            elif '802.11a' in iw_out:
                info['wifi_standard'] = '802.11a'
            elif '802.11b' in iw_out or '802.11g' in iw_out:
                info['wifi_standard'] = '802.11b/g'
            
            # Extract frequency (in MHz) to determine band
            freq_match = re.search(r'freq:\s+([\d.]+)', iw_out)
            if freq_match:
                freq = float(freq_match.group(1))
                if freq < 3000:
                    info['band'] = '2.4 GHz'
                elif freq < 6000:
                    info['band'] = '5 GHz'
                else:
                    info['band'] = '6 GHz'
    except:
        pass
    
    # Fallback: try iwconfig for older systems or additional info
    if info['ssid'] == '—':
        try:
            iwconfig_out = run(['iwconfig', iface])
            if iwconfig_out and 'ESSID' in iwconfig_out:
                essid_match = re.search(r'ESSID:"(.+?)"', iwconfig_out)
                if essid_match:
                    info['ssid'] = essid_match.group(1)
                
                signal_match = re.search(r'Signal level[=:](\S+)', iwconfig_out)
                if signal_match:
                    info['signal_dbm'] = signal_match.group(1)
        except:
            pass
    
    return info, iface

def get_proc_bytes(iface='eth0'):
    """Get network bytes from /proc/net/dev"""
    try:
        with open('/proc/net/dev') as f:
            for line in f:
                if iface in line:
                    p = line.split()
                    return int(p[1]), int(p[9])
    except:
        pass
    return 0, 0

def fmt_speed(bps):
    if bps >= 1_000_000: return f"{bps/1_000_000:.2f} MB/s"
    if bps >= 1_000:     return f"{bps/1_000:.1f} KB/s"
    return f"{int(bps)} B/s"

def run_speedtest_bg():
    global _speedtest_running, _speedtest_result
    try:
        r = subprocess.run(['speedtest-cli', '--simple'], capture_output=True, text=True, timeout=60)
        out = r.stdout
        ping  = re.search(r'Ping:\s+([\d.]+)\s+ms', out)
        dl    = re.search(r'Download:\s+([\d.]+)\s+Mbit/s', out)
        ul    = re.search(r'Upload:\s+([\d.]+)\s+Mbit/s', out)
        _speedtest_result = {
            'ping':     ping.group(1) + ' ms' if ping else '—',
            'download': dl.group(1) + ' Mbps' if dl else '—',
            'upload':   ul.group(1) + ' Mbps' if ul else '—',
            'timestamp': time.strftime('%I:%M:%S %p'),
            'error': None
        }
    except Exception as e:
        _speedtest_result = {'error': str(e)}
    finally:
        _speedtest_running = False

@app.route('/api/speedtest/run', methods=['POST'])
def start_speedtest():
    global _speedtest_running, _speedtest_result
    if _speedtest_running:
        return jsonify({'status': 'running'})
    _speedtest_running = True
    _speedtest_result = None
    threading.Thread(target=run_speedtest_bg, daemon=True).start()
    return jsonify({'status': 'started'})

@app.route('/api/speedtest/result')
def speedtest_result():
    return jsonify({
        'running': _speedtest_running,
        'result':  _speedtest_result
    })

@app.route('/api/stats')
def stats():
    global _prev
    
    internet = check_internet()
    net_info, iface = get_host_network_info()
    conn_display = f"{net_info['conn_type_label']} ({iface})"
    
    now = time.time()
    rx, tx = get_proc_bytes(iface)
    elapsed = now - _prev['time']
    dl = fmt_speed((rx - _prev['rx']) / elapsed) if elapsed > 0 else '—'
    ul = fmt_speed((tx - _prev['tx']) / elapsed) if elapsed > 0 else '—'
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
