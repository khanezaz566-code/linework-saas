"""VectorCraft Web Edition Launcher
Runs the high-performance VectorCraft web server on port 8000 and opens the browser.
"""
import os
import sys
import time
import webbrowser
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

def check_server(port=8000):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def open_browser(port=8000):
    url = f"http://localhost:{port}"
    for _ in range(30):
        if check_server(port):
            print(f"[+] Server ready! Opening browser at {url} ...")
            webbrowser.open(url)
            return
        time.sleep(0.2)

def main():
    port = 8000
    print("=" * 60)
    print("  VectorCraft AI Vector Redraw Studio — Web Edition")
    print(f"  Local Web Address: http://localhost:{port}")
    print("  Auto-Authentication: Active (Pro Unlimited Access)")
    print("=" * 60)
    
    # Open browser once server is ready
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    
    import uvicorn
    from server.app import app
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    main()
