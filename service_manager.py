"""Linework AI Service Manager & Permanent Localhost Setup
Provides background service management, auto-start on Windows boot/logon,
and one-click control scripts.
"""
import os
import sys
import time
import subprocess
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable
# Prefer pythonw.exe for completely silent background execution
PYTHONW_CANDIDATES = [
    Path(PYTHON_EXE).parent / "pythonw.exe",
    Path("C:/Users/USER/AppData/Local/Python/bin/pythonw.exe"),
    Path("C:/Users/USER/AppData/Local/Microsoft/WindowsApps/pythonw.exe"),
]
PYTHONW_EXE = next((str(p) for p in PYTHONW_CANDIDATES if p.exists()), PYTHON_EXE)
STARTUP_DIR = Path(os.environ.get("APPDATA", "C:/Users/USER/AppData/Roaming")) / "Microsoft/Windows/Start Menu/Programs/Startup"
DESKTOP_DIR = Path("C:/Users/USER/Desktop")


def get_server_pid(port=8000):
    """Find PID of process listening on port 8000."""
    try:
        cmd = f'netstat -ano | findstr :{port}'
        out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3] == "LISTENING":
                return int(parts[4])
    except Exception:
        pass
    return None


def is_server_healthy(port=8000, timeout=1.5):
    """Check if server is responding to HTTP requests."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=timeout) as resp:
            return resp.status in (200, 405)
    except Exception:
        return False


def start_service(port=8000):
    """Start the server silently in the background."""
    pid = get_server_pid(port)
    if pid and is_server_healthy(port):
        print(f"[OK] Linework AI is ALREADY running on http://localhost:{port} (PID: {pid})")
        return True

    print(f"[*] Starting Linework AI server on port {port} in background...")
    # Launch via pythonw.exe detached from console
    cmd = [PYTHONW_EXE, str(BASE_DIR / "run.py")]
    subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )

    # Wait up to 6 seconds for healthy response
    for _ in range(12):
        time.sleep(0.5)
        if is_server_healthy(port):
            new_pid = get_server_pid(port)
            print(f"[SUCCESS] Linework AI is now live at http://localhost:{port} (PID: {new_pid})")
            return True

    print("[!] Server started but health check pending. Verify at http://localhost:8000")
    return False


def stop_service(port=8000):
    """Stop the running server."""
    pid = get_server_pid(port)
    if not pid:
        print(f"[*] No Linework AI server process found listening on port {port}.")
        return True

    print(f"[*] Stopping Linework AI server (PID: {pid})...")
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], check=True, capture_output=True)
        time.sleep(1)
        print("[SUCCESS] Server stopped cleanly.")
        return True
    except Exception as e:
        print(f"[!] Error stopping server: {e}")
        return False


def restart_service(port=8000):
    """Restart server to apply updates."""
    print("[*] Restarting Linework AI...")
    stop_service(port)
    time.sleep(1)
    return start_service(port)


def install_permanent_startup(port=8000):
    """Install auto-start scripts in Windows Startup folder and Task Scheduler."""
    print("[*] Installing Permanent Localhost Setup for Linework AI...")

    # 1. Create silent VBS script for Startup folder
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    vbs_path = STARTUP_DIR / "Start_Linework_AI.vbs"
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{BASE_DIR}"
WshShell.Run "\"{PYTHONW_EXE}\" \"{BASE_DIR / 'run.py'}\"", 0, False
'''
    vbs_path.write_text(vbs_content, encoding="utf-8")
    print(f"  [+] Windows Startup entry created: {vbs_path.name}")

    # 2. Also keep a copy of the silent launcher in BASE_DIR
    local_vbs = BASE_DIR / "start_silent.vbs"
    local_vbs.write_text(vbs_content, encoding="utf-8")

    # 3. Create Windows Task Scheduler task for reboot auto-start
    try:
        task_name = "LineworkAIServer"
        # schtasks command to run on user logon
        cmd = f'schtasks /Create /F /TN "{task_name}" /TR "wscript.exe \\"{vbs_path}\\"" /SC ONLOGON /RL LIMITED'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"  [+] Windows Task Scheduler task '{task_name}' registered successfully.")
        else:
            print(f"  [-] Task Scheduler note: {res.stderr.strip() or res.stdout.strip()}")
    except Exception as e:
        print(f"  [-] Task Scheduler registration skipped: {e}")

    # 4. Create Desktop Browser Shortcut (.url)
    if DESKTOP_DIR.exists():
        url_file = DESKTOP_DIR / "Linework AI.url"
        url_content = f"""[InternetShortcut]
URL=http://localhost:{port}/
IconIndex=0
IconFile={PYTHON_EXE}
"""
        url_file.write_text(url_content, encoding="utf-8")
        print(f"  [+] Desktop Web App shortcut created: {url_file.name}")

        # 5. Create Desktop Restart Control Script (.bat)
        restart_bat = DESKTOP_DIR / "Restart_Linework_AI.bat"
        restart_bat_content = f"""@echo off
title Linework AI - Restart
echo ===================================================
echo   Restarting Linework AI Server on localhost:{port}...
echo ===================================================
cd /d "{BASE_DIR}"
"{PYTHON_EXE}" "{BASE_DIR / 'service_manager.py'}" restart
echo.
echo Server restarted! Opening browser...
start http://localhost:{port}/
timeout /t 3
"""
        restart_bat.write_text(restart_bat_content, encoding="utf-8")
        print(f"  [+] Desktop Restart control script created: {restart_bat.name}")

    # Ensure service is running right now
    start_service(port)
    print("\n[PERMANENT SETUP COMPLETE]")
    print(f"* Linework AI will now automatically start on every PC boot / login.")
    print(f"* Even if you shut down or restart your computer, it will stay active.")
    print(f"* Access anytime at: http://localhost:{port}/")
    print(f"* Desktop shortcut 'Linework AI' opens the web UI instantly.")
    return True


def uninstall_permanent_startup():
    """Remove startup scripts and scheduled tasks."""
    print("[*] Removing Linework AI permanent startup entries...")
    vbs_path = STARTUP_DIR / "Start_Linework_AI.vbs"
    if vbs_path.exists():
        vbs_path.unlink()
        print(f"  [-] Removed: {vbs_path}")

    try:
        subprocess.run('schtasks /Delete /F /TN "LineworkAIServer"', shell=True, capture_output=True)
        print("  [-] Removed Windows Scheduled Task 'LineworkAIServer'")
    except Exception:
        pass

    url_file = DESKTOP_DIR / "Linework AI.url"
    if url_file.exists():
        url_file.unlink()
        print(f"  [-] Removed: {url_file}")

    restart_bat = DESKTOP_DIR / "Restart_Linework_AI.bat"
    if restart_bat.exists():
        restart_bat.unlink()
        print(f"  [-] Removed: {restart_bat}")

    print("[DONE] Permanent startup uninstalled.")


if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "status"

    if action == "status":
        pid = get_server_pid()
        healthy = is_server_healthy()
        print(f"Linework AI Server Status:")
        print(f"  Port: 8000")
        print(f"  PID: {pid if pid else 'Not running'}")
        print(f"  Health Check: {'Responding (UP)' if healthy else 'Not responding (DOWN)'}")
        print(f"  URL: http://localhost:8000/")
    elif action == "start":
        start_service()
    elif action == "stop":
        stop_service()
    elif action == "restart":
        restart_service()
    elif action in ("install", "setup", "permanent"):
        install_permanent_startup()
    elif action in ("uninstall", "remove"):
        uninstall_permanent_startup()
    else:
        print("Usage: python service_manager.py [status|start|stop|restart|install|uninstall]")
