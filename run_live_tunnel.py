"""Linework AI - Public Live Cloud Runner (100% Free Forever)
Runs the local high-performance vectorizer connected to Supabase Cloud,
and opens a secure public HTTPS tunnel via Cloudflare.
"""
import os
import sys
import time
import subprocess
import threading
import webbrowser
import re
from pathlib import Path

# Configure UTF-8 encoding for Windows CMD / PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Guarantee permanent Supabase PostgreSQL connection
SUPABASE_URL = "postgresql://postgres.aqilhnaqytvgdaqxobmn:ezaz%40566%40%3F%3F@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"
os.environ["DATABASE_URL"] = SUPABASE_URL

CLOUDFLARED_EXE = ROOT / "cloudflared.exe"

def run_server():
    import uvicorn
    from server.app import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

def monitor_tunnel():
    if not CLOUDFLARED_EXE.exists():
        print("[-] cloudflared.exe not found.")
        return

    cmd = [str(CLOUDFLARED_EXE), "tunnel", "--url", "http://127.0.0.1:8000"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding="utf-8", errors="replace")
    
    tunnel_url = None
    for line in iter(proc.stdout.readline, ""):
        match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
        if match:
            tunnel_url = match.group(0)
            break
            
    if tunnel_url:
        print("\n" + "=" * 65)
        print("  *** LINEWORK AI IS NOW LIVE TO THE WORLD (100% FREE FOREVER)! ***")
        print("=" * 65)
        print(f"  >> PUBLIC HTTPS URL : {tunnel_url}")
        print(f"  >> ADMIN CRM PORTAL : {tunnel_url}/admin")
        print(f"  >> DATABASE BACKEND : Supabase Cloud PostgreSQL (Permanent)")
        print(f"  >> COMPUTE ENGINE   : Local Dedicated Multi-Core CPU (Superfast)")
        print("=" * 65)
        print("  Share the Public URL above with your clients or open it on mobile!\n")
        
        # Save current live URL to a text file
        (ROOT / "LIVE_PUBLIC_URL.txt").write_text(
            f"Public URL: {tunnel_url}\nAdmin Portal: {tunnel_url}/admin\nGenerated at: {time.ctime()}\n",
            encoding="utf-8"
        )
        
        time.sleep(1)
        webbrowser.open(tunnel_url)
    
    proc.wait()

def main():
    print("=" * 65)
    print("  Starting Linework AI Local Engine + Cloudflare Live Tunnel...")
    print("=" * 65)
    
    # Start web server thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    time.sleep(1)
    
    # Start and monitor tunnel
    monitor_tunnel()

if __name__ == "__main__":
    main()
