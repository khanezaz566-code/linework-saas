import sys
import os
import time
import threading
import multiprocessing as mp
import urllib.request
from pathlib import Path

# Fix Windows GUI / noconsole issue where sys.stdout and sys.stderr are None
if sys.stdout is None:
    try:
        sys.stdout = open(os.devnull, "w")
    except Exception:
        import io
        sys.stdout = io.StringIO()
if sys.stderr is None:
    try:
        sys.stderr = open(os.devnull, "w")
    except Exception:
        import io
        sys.stderr = io.StringIO()

# Multiprocessing freeze support for Windows executables
mp.freeze_support()

# Add root directory to sys.path
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
    if hasattr(sys, "_MEIPASS"):
        BUNDLE_ROOT = Path(sys._MEIPASS)
        sys.path.insert(0, str(BUNDLE_ROOT))
    sys.path.insert(0, str(ROOT))
else:
    ROOT = Path(__file__).resolve().parent
    sys.path.insert(0, str(ROOT))

try:
    import numpy
    import cv2
    import scipy
    import scipy.ndimage
    import scipy.spatial
    import skimage
    import skimage.morphology
    import skimage.measure
    import threadpoolctl
    import resvg_py
    import uvicorn
    import fastapi
except ImportError:
    pass

def is_server_running(port=8000):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False

def run_embedded_server(port=8000):
    log_file = ROOT / "server.log"
    try:
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w")
            
        import uvicorn
        from server.app import app
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting VectorCraft server on port {port}...\n")
        uvicorn.run(app, host="127.0.0.1", port=port, log_config=None)
    except Exception as e:
        import traceback
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Server startup error: {e}\n{traceback.format_exc()}\n")

def main():
    port = 8000
    
    # 1. Start embedded uvicorn server in background thread if not already running
    if not is_server_running(port):
        t = threading.Thread(target=run_embedded_server, args=(port,), daemon=True)
        t.start()
        
        # Wait up to 6 seconds for backend to be fully initialized
        for _ in range(60):
            if is_server_running(port):
                break
            time.sleep(0.1)

    # 2. Always launch directly into the responsive live VectorCraft Studio interface
    start_url = f"http://127.0.0.1:{port}"

    import webview
    
    window = webview.create_window(
        title="VectorCraft — AI Vector Redraw Studio",
        url=start_url,
        width=1360,
        height=860,
        min_size=(960, 640),
        background_color="#05080c",
        text_select=True,
    )
    
    webview.start(gui="edgechromium", debug=False)

if __name__ == "__main__":
    main()
