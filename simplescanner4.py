import sys
import time
import os
import socket
import csv
import threading
import io
from datetime import datetime
from scapy.all import ARP, Ether, srp, send, sniff

# =========================================================
# CRITICAL FIX FOR WINDOWS: Force UTF-8 Encoding for Emojis
# This prevents "UnicodeEncodeError" when printing 🚨 or ╔════
# =========================================================
try:
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

# Attempt to load MAC Vendor lookup
try:
    from mac_vendor_lookup import MacLookup
    mac_lookup = MacLookup()
    HAS_VENDOR_LOOKUP = True
except ImportError:
    HAS_VENDOR_LOOKUP = False

# Attempt to load Windows sound
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# Attempt to load plyer for desktop notifications
try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# =========================================================
# God Mode Configuration
# =========================================================
TRUSTED_FILE = "trusted_devices.txt"
BLOCK_LIST_FILE = "block_list.txt"     
LOG_FILE = "intruder_log.csv"
TRAFFIC_LOG_FILE = "traffic_logs.csv"
HTML_REPORT = "dashboard.html"

# If True, blocks ALL unknown devices automatically.
AUTO_BLOCK_INTRUDERS = False

TARGET_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 80: "HTTP",
    443: "HTTPS", 445: "SMB", 3389: "RDP", 8080: "Proxy"
}

DEFAULT_TRUSTED = ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"]

seen_intruders = set()
active_blocked_ips = set()

def print_banner():
    banner = f"""
{Colors.RED}{Colors.BOLD}
  ██████╗ ██╗   ██╗██████╗ ███████╗██████╗     ███╗   ███╗ ██████╗ ██████╗ ███████╗
 ██╔════╝  ██║   ██║██╔══██╗██╔════╝██╔══██╗    ████╗ ████║██╔═══██╗██╔══██╗██╔════╝
 ██║  ███╗ ██║   ██║██████╔╝█████╗  ██████╔╝    ██╔████╔██║██║   ██║██║  ██║█████╗  
 ██║   ██║██║   ██║██╔══██╗██╔══╝  ██╔══██╗    ██║╚██╔╝██║██║   ██║██║  ██║██╔══╝  
 ╚██████╔╝╚██████╔╝██████╔╝███████╗██║  ██║    ██║ ╚═╝ ██║╚██████╔╝██████╔╝███████╗
  ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝    ╚═╝     ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝
                                                                                   
     ► ULTIMATE CYBER ENGINE - MANUAL TARGETING & ACTIVE DEFENSE ◄
{Colors.RESET}"""
    print(banner)

def load_trusted_macs():
    trusted_macs = set()
    if not os.path.exists(TRUSTED_FILE):
        try:
            with open(TRUSTED_FILE, 'w', encoding='utf-8') as f:
                f.write("# Put your Secure MAC Addresses below.\n")
                for mac in DEFAULT_TRUSTED:
                    f.write(f"{mac}\n")
        except Exception: pass

    try:
        with open(TRUSTED_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    trusted_macs.add(line.strip().upper())
    except Exception:
        trusted_macs = {m.upper() for m in DEFAULT_TRUSTED}
    return trusted_macs

def load_block_list():
    block_ips = set()
    if not os.path.exists(BLOCK_LIST_FILE):
        try:
            with open(BLOCK_LIST_FILE, 'w', encoding='utf-8') as f:
                f.write("# TARGET LOCK: Enter the IP addresses you want to permanently disconnect.\n")
                f.write("# (Example: 192.168.1.15)\n")
        except Exception: pass

    try:
        with open(BLOCK_LIST_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    block_ips.add(line.strip())
    except Exception: pass
    return block_ips

def generate_html_dashboard():
    html_head = """
    <html><head><title>Cyber Security Dashboard</title>
    <style>
        body { font-family: consolas, monospace; background-color: #0d1117; color: #c9d1d9; padding: 20px; }
        h1, h2 { text-align: center; color: #ff7b72; text-transform: uppercase; }
        .container { max-width: 1000px; margin: 0 auto; background: #161b22; padding: 20px; border-radius: 8px; border: 1px solid #30363d; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #30363d; }
        th { background-color: #21262d; color: #58a6ff; }
        .danger { color: #f85149; font-weight: bold; }
        .safe { color: #3fb950; font-weight: bold; }
        .sniff { color: #d2a8ff; }
    </style>
    </head><body><div class="container">
    <h1>🌐 Live Cyber Dashboard 🌐</h1>
    """

    intruder_table = "<h2>🚨 Detected Intruders</h2><table><tr><th>Time</th><th>IP</th><th>MAC</th><th>Vendor</th><th>Threat</th></tr>"
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader, None)
            for r in reader:
                if len(r) >= 5:
                    cls = "danger" if "HIGH" in r[4] else ("safe" if "LOW" in r[4] else "")
                    intruder_table += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td class='{cls}'>{r[4]}</td></tr>"
    except Exception: pass
    intruder_table += "</table>"

    traffic_table = "<h2>👁️ Live Sniffed Traffic</h2><table><tr><th>Time</th><th>Target IP</th><th>Activity Type</th><th>Details</th></tr>"
    try:
        with open(TRAFFIC_LOG_FILE, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader, None)
            for r in reader:
                if len(r) >= 4:
                    traffic_table += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td class='sniff'>{r[3]}</td></tr>"
    except Exception: pass
    traffic_table += "</table>"

    html_tail = f"<div style='text-align:center;'>Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div></div></body></html>"

    try:
        with open(HTML_REPORT, "w", encoding='utf-8') as f:
            f.write(html_head + intruder_table + traffic_table + html_tail)
    except Exception: pass

def log_intruder(device, vendor, timestamp, threat_level):
    file_exists = os.path.isfile(LOG_FILE)
    try:
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if not file_exists: w.writerow(['Timestamp', 'IP Address', 'MAC Address', 'Vendor', 'Threat Level'])
            w.writerow([timestamp, device['ip'], device['mac'], vendor, threat_level])
        generate_html_dashboard()
    except Exception: pass

def log_traffic(ip, activity_type, details):
    file_exists = os.path.isfile(TRAFFIC_LOG_FILE)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(TRAFFIC_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if not file_exists: w.writerow(['Timestamp', 'IP', 'Activity Type', 'Details'])
            w.writerow([timestamp, ip, activity_type, details])
        generate_html_dashboard()
    except Exception: pass

def sniff_intruder_traffic(target_ip):
    def analyze_packet(packet):
        if packet.haslayer('IP') and packet['IP'].src == target_ip:
            if packet.haslayer('DNSQR'):
                try:
                    query = packet['DNSQR'].qname.decode('utf-8').strip('.')
                    log_traffic(target_ip, "DNS Search", f"Connecting to: {query}")
                    print("\r" + " " * 80 + "\r", end="")
                    print(f"{Colors.MAGENTA}  [SNIFFER] {target_ip} requested -> {query}{Colors.RESET}")
                except Exception: pass
            elif packet.haslayer('TCP') and packet['TCP'].dport in [80, 443]:
                dst_ip = packet['IP'].dst
                log_traffic(target_ip, "TCP Connection", f"Connected to IP: {dst_ip}")

    try:
        sniff(filter=f"host {target_ip}", prn=analyze_packet, store=0)
    except Exception: pass

def get_local_info():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split('.')
        return f"{parts[0]}.{parts[1]}.{parts[2]}.1/24", f"{parts[0]}.{parts[1]}.{parts[2]}.1"
    except Exception:
        return "172.16.215.135/24", "172.16.215.1"

def active_defense_blocker(target_ip, gateway_ip):
    print(f"\n{Colors.RED}[!!!] FIRING ARP CYBER-MISSLES! Targeting IP {target_ip}!{Colors.RESET}")
    print(f"{Colors.RED}      (Target {target_ip} is now disconnected from internet){Colors.RESET}")
    try:
        packet = ARP(op=2, pdst=target_ip, psrc=gateway_ip, hwdst="ff:ff:ff:ff:ff:ff")
        while True:
            # We catch exceptions internally here so threaded function doesn't crash silently
            try:
                send(packet, verbose=0)
            except Exception as inner_e:
                pass
            time.sleep(1) 
    except Exception:
        pass

def get_vendor(mac_address):
    if not HAS_VENDOR_LOOKUP: return "Unknown Origin"
    try:
        v = mac_lookup.lookup(mac_address)
        return v if v else "Unknown Origin"
    except Exception: return "Unknown Origin"

def scan_intruder_ports(target_ip):
    open_ports = []
    def check_port(port, name):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            if s.connect_ex((target_ip, port)) == 0:
                open_ports.append(f"Port {port} ({name})")
            s.close()
        except Exception: pass

    threads = [threading.Thread(target=check_port, args=(p, n)) for p, n in TARGET_PORTS.items()]
    for t in threads: t.start()
    for t in threads: t.join()
    return open_ports

def play_siren():
    if not HAS_WINSOUND: return
    try:
        for _ in range(4):
            winsound.Beep(2000, 200)
            winsound.Beep(1000, 200)
    except Exception: pass

def alert_intruder(device, gateway_ip):
    mac = device['mac']
    ip = device['ip']
    
    if mac in seen_intruders: return
    seen_intruders.add(mac)

    threading.Thread(target=play_siren, daemon=True).start()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vendor = get_vendor(mac)
    open_ports = scan_intruder_ports(ip)
    
    if len(open_ports) > 0:
        threat_level = "HIGH THREAT"
        color = Colors.RED
    elif vendor == "Unknown Origin":
        threat_level = "MEDIUM THREAT"
        color = Colors.YELLOW
    else:
        threat_level = "LOW THREAT"
        color = Colors.CYAN

    log_intruder(device, vendor, timestamp, threat_level)
    
    defense_status = "DISABLED"
    if AUTO_BLOCK_INTRUDERS:
        defense_status = "🚨 ACTIVE! Blocking Network Access!"
        # We don't start it here! It's started in the main loop to prevent duplicate threads per IP

    threading.Thread(target=sniff_intruder_traffic, args=(ip,), daemon=True).start()

    print("\r" + " " * 80 + "\r", end="")
    print(f"\n{color}{Colors.BOLD}╔════════════════════════════════════════════════════════════════════════╗")
    print(f"║ 🚨 SECURITY BREACH! DEEP SENSORS & SNIFFER TRIGGERED 🚨                ║")
    print(f"╠════════════════════════════════════════════════════════════════════════╣")
    print(f"║ 🌐 Target IP   : {Colors.RESET}{ip:<54}{color}║")
    print(f"║ 🏷️  MAC Address: {Colors.RESET}{mac:<54}{color}║")
    print(f"║ 🏢 Identity    : {Colors.RESET}{vendor:<54}{color}║")
    print(f"║ ⚡ Threat Level: {color}{threat_level:<54}{color}║")
    print(f"╚════════════════════════════════════════════════════════════════════════╝{Colors.RESET}\n")

    if HAS_PLYER:
        try:
            notification.notify(
                title=f"🚨 Threat: {threat_level}",
                message=f"Sniffing traffic for {ip}...",
                app_name="Intruder Detector", timeout=8)
        except Exception: pass

def scan_network(ip_range):
    # CRITICAL FIX: Report real exceptions instead of ignoring them!
    try:
        arp = ARP(pdst=ip_range)
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = ether / arp
        result, _ = srp(packet, timeout=2, verbose=0)
        return [{"ip": r.psrc, "mac": r.hwsrc.upper()} for s, r in result]
    except PermissionError:
        print(f"\n{Colors.RED}❌ Windows Permission Error: RUN POWERSHELL AS ADMINISTRATOR!{Colors.RESET}")
        print(f"{Colors.YELLOW}Please close this window, right-click PowerShell, and select 'Run as Administrator'.{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Scapy Network Engine Error: {e}{Colors.RESET}")
        print(f"{Colors.YELLOW}(Make sure WinPcap/Npcap is installed correctly!){Colors.RESET}")
        sys.exit(1)

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print_banner()

    target_subnet, router_ip = get_local_info()
    generate_html_dashboard()

    print(f"{Colors.BOLD}{Colors.YELLOW}[+] Initializing Packet Sniffers & Threat Engines...{Colors.RESET}")
    time.sleep(0.5)
    print(f"{Colors.CYAN}    ► Target Subnet    : {target_subnet}{Colors.RESET}")
    print(f"{Colors.CYAN}    ► Gateway Router   : {router_ip}{Colors.RESET}")
    print(f"{Colors.CYAN}    ► Web Dashboard    : {HTML_REPORT}{Colors.RESET}")
    print(f"{Colors.MAGENTA}    ► PACKET SNIFFER   : 👁️ ACTIVE{Colors.RESET}")
        
    print(f"{Colors.GREEN}{Colors.BOLD}🛡️  SYSTEM ARMED. Press CTRL+C to abort.{Colors.RESET}\n")

    scan_count = 0
    try:
        while True:
            scan_count += 1
            devices = scan_network(target_subnet)
            
            # If devices comes back strictly empty or none, network scan might be failing 
            # but usually it returns at least your own device or router
            
            t = datetime.now().strftime("%H:%M:%S")
            sys.stdout.write(f"\r{Colors.BLUE}[~] {t} | Sweep #{scan_count:04d} | Scanning Network {Colors.RESET}   ")
            sys.stdout.flush()

            trusted_macs = load_trusted_macs()
            ips_to_manually_block = load_block_list()

            for device in devices:
                ip = device['ip']
                mac = device['mac']

                # Alert if unfamiliar MAC
                if mac not in trusted_macs:
                    alert_intruder(device, router_ip)

                # Target specific IP blocking dynamically!
                should_block = False
                if AUTO_BLOCK_INTRUDERS and mac not in trusted_macs:
                    should_block = True
                if ip in ips_to_manually_block:
                    should_block = True

                if should_block and (ip not in active_blocked_ips):
                    active_blocked_ips.add(ip)
                    # Deploy the ARP Cyber-missile thread safely
                    threading.Thread(target=active_defense_blocker, args=(ip, router_ip), daemon=True).start()

            time.sleep(10)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.RED}[!] System halted.{Colors.RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
