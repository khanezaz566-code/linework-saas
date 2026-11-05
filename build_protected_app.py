"""
Build Script for VectorCraft Protected Windows Application.
1. Compiles and encrypts all proprietary engine modules into an in-memory binary vault.
2. Strips all plaintext .py files of the proprietary algorithms.
3. Freezes into a standalone native Windows desktop application via PyInstaller.
4. Generates a Desktop shortcut with VectorCraft branding.
5. Packages a clean release zip archive onto the Desktop.
"""
import sys
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

def step1_compile_vault():
    print("=" * 60)
    print("STEP 1: Compiling & Encrypting Proprietary Engine Vault...")
    print("=" * 60)
    import scratch.compile_vault
    vault_file = ROOT / "linework" / "_core_vault.dat"
    assert vault_file.exists() and vault_file.stat().st_size > 100000, "Vault build failed!"
    print(f"Verified Vault: {vault_file.stat().st_size:,} bytes")

def step2_prepare_staging():
    print("\n" + "=" * 60)
    print("STEP 2: Preparing Protected Staging Directory (No Plaintext Source)...")
    print("=" * 60)
    staging = ROOT / "build_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    # 1. Copy desktop_app.py
    shutil.copy2(ROOT / "desktop_app.py", staging / "desktop_app.py")

    # 2. Copy server/
    shutil.copytree(ROOT / "server", staging / "server", dirs_exist_ok=True)

    # 3. Copy samples/
    shutil.copytree(ROOT / "samples", staging / "samples", dirs_exist_ok=True)

    # 4. Copy icons
    if (ROOT / "vectorcraft.ico").exists():
        shutil.copy2(ROOT / "vectorcraft.ico", staging / "vectorcraft.ico")

    # 5. Copy ONLY protected vault files into linework/
    staging_lw = staging / "linework"
    staging_lw.mkdir(parents=True)
    shutil.copy2(ROOT / "linework" / "__init__.py", staging_lw / "__init__.py")
    shutil.copy2(ROOT / "linework" / "_vault.py", staging_lw / "_vault.py")
    shutil.copy2(ROOT / "linework" / "_core_vault.dat", staging_lw / "_core_vault.dat")

    # Verify NO engine .py files are in staging/linework
    leaked_files = [f.name for f in staging_lw.glob("*.py") if f.name not in ("__init__.py", "_vault.py")]
    if leaked_files:
        raise RuntimeError(f"LEAK DETECTED! Plaintext engine files found in staging: {leaked_files}")

    print("Staging verified: Zero proprietary .py files present in staging directory!")
    return staging

def step3_run_pyinstaller(staging_dir):
    print("\n" + "=" * 60)
    print("STEP 3: Freezing Standalone Windows Executable with PyInstaller...")
    print("=" * 60)

    dist_dir = ROOT / "dist"
    work_dir = ROOT / "build"
    app_dist = dist_dir / "VectorCraft"
    if app_dist.exists():
        shutil.rmtree(app_dist, ignore_errors=True)

    icon_arg = []
    icon_file = staging_dir / "vectorcraft.ico"
    if icon_file.exists():
        icon_arg = ["--icon", str(icon_file)]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--noconsole",
        "--noconfirm",
        "--name", "VectorCraft",
        "--distpath", str(dist_dir),
        "--workpath", str(work_dir),
        "--clean",
        *icon_arg,
        "--add-data", f"{staging_dir / 'server' / 'static'};server/static",
        "--add-data", f"{staging_dir / 'samples'};samples",
        "--add-data", f"{staging_dir / 'linework' / '_core_vault.dat'};linework",
        "--collect-all", "scipy",
        "--collect-all", "skimage",
        "--collect-all", "threadpoolctl",
        "--collect-all", "resvg_py",
        "--hidden-import", "scipy",
        "--hidden-import", "scipy.ndimage",
        "--hidden-import", "scipy.spatial",
        "--hidden-import", "skimage",
        "--hidden-import", "skimage.morphology",
        "--hidden-import", "skimage.measure",
        "--hidden-import", "threadpoolctl",
        "--hidden-import", "uvicorn",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "fastapi",
        "--hidden-import", "resvg_py",
        "--hidden-import", "cv2",
        "--hidden-import", "numpy",
        "--hidden-import", "webview",
        "--hidden-import", "clr",
        str(staging_dir / "desktop_app.py")
    ]

    print("Executing PyInstaller command...")
    res = subprocess.run(cmd, cwd=str(staging_dir))
    if res.returncode != 0:
        raise RuntimeError(f"PyInstaller failed with exit code {res.returncode}")

    exe_path = dist_dir / "VectorCraft" / "VectorCraft.exe"
    assert exe_path.exists(), f"Expected executable not found at: {exe_path}"
    print(f"\nSUCCESS: Created frozen executable: {exe_path} ({exe_path.stat().st_size:,} bytes)")
    
    # Also copy VectorCraft into Linework_AI folder for full backward compatibility
    compat_dir = dist_dir / "Linework_AI"
    if compat_dir.exists():
        shutil.copy2(exe_path, compat_dir / "Linework_AI.exe")
        shutil.copy2(exe_path, compat_dir / "VectorCraft.exe")
        
    return exe_path

def step4_create_desktop_shortcut(exe_path):
    print("\n" + "=" * 60)
    print("STEP 4: Creating Windows Desktop Shortcut...")
    print("=" * 60)
    desktop = Path(os.environ.get("USERPROFILE", "C:/Users/USER")) / "Desktop"
    shortcut_path = desktop / "VectorCraft.lnk"

    vbs_script = f'''
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{exe_path}"
oLink.WorkingDirectory = "{exe_path.parent}"
oLink.Description = "VectorCraft — AI Vector Redraw Studio"
oLink.Save
'''
    vbs_path = ROOT / "scratch" / "create_shortcut.vbs"
    vbs_path.write_text(vbs_script, encoding="utf-8")
    subprocess.run(["wscript.exe", str(vbs_path)])
    print(f"Created Desktop shortcut: {shortcut_path}")

    # Also keep Linework AI.lnk updated
    old_shortcut = desktop / "Linework AI.lnk"
    vbs_old = f'''
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{old_shortcut}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{exe_path}"
oLink.WorkingDirectory = "{exe_path.parent}"
oLink.Description = "VectorCraft AI Redraw Studio"
oLink.Save
'''
    vbs_path.write_text(vbs_old, encoding="utf-8")
    subprocess.run(["wscript.exe", str(vbs_path)])

def step5_create_release_zip(exe_path):
    print("\n" + "=" * 60)
    print("STEP 5: Packaging Standalone Desktop Release Zip...")
    print("=" * 60)
    desktop = Path(os.environ.get("USERPROFILE", "C:/Users/USER")) / "Desktop"
    dist_dir = exe_path.parent
    
    zip_dst = desktop / "VectorCraft_Windows_App"
    archive_path = shutil.make_archive(str(zip_dst), "zip", str(dist_dir.parent), str(dist_dir.name))
    print(f"Created Release Archive: {archive_path} ({Path(archive_path).stat().st_size:,} bytes)")
    
    # Also update Linework_AI_Windows_App.zip
    shutil.copy2(archive_path, desktop / "Linework_AI_Windows_App.zip")

def main():
    step1_compile_vault()
    staging = step2_prepare_staging()
    exe = step3_run_pyinstaller(staging)
    step4_create_desktop_shortcut(exe)
    step5_create_release_zip(exe)
    print("\n" + "=" * 60)
    print("ALL BUILD STEPS COMPLETED 100% SUCCESSFULLY!")
    print(f"Application Ready at: {exe}")
    print("=" * 60)

if __name__ == "__main__":
    main()
