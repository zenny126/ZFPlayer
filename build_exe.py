import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    print("=" * 60)
    print("      ZennyFLAC Player - Executable Packaging Build Script")
    print("=" * 60)

    project_root = Path(__file__).resolve().parent
    spec_file = project_root / "zfplayer.spec"

    if not spec_file.exists():
        print(f"[!] Error: {spec_file} not found!")
        sys.exit(1)

    # 1. Kill any existing instances before building
    try:
        subprocess.run(["taskkill", "/F", "/IM", "ZennyFLAC_Player.exe"], capture_output=True)
        subprocess.run(["taskkill", "/F", "/IM", "ZFPlayer.exe"], capture_output=True)
    except Exception:
        pass

    # 2. Ensure all icon files exist
    try:
        sys.path.insert(0, str(project_root))
        from generate_icon import create_zfp_icon
        create_zfp_icon()
    except Exception as e:
        print(f"[!] Warning generating icons: {e}")

    # 3. Clean previous build & dist directories completely
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"
    
    if dist_dir.exists():
        shutil.rmtree(dist_dir, ignore_errors=True)
        print("[+] Cleaned dist directory.")
        
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
        print("[+] Cleaned build directory.")

    # 4. Run PyInstaller
    print("\n[+] Running PyInstaller build (-OO bytecode, clean environment)...")
    cmd = [
        sys.executable,
        "-OO",
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec_file)
    ]

    try:
        subprocess.check_call(cmd, cwd=str(project_root))
        exe_path = project_root / "dist" / "ZennyFLAC_Player.exe"

        if exe_path.exists():
            file_size_mb = os.path.getsize(exe_path) / (1024 * 1024)

            print("\n" + "=" * 60)
            print("  BUILD SUCCESSFUL!")
            print(f"  Executable: {exe_path}")
            print(f"  File Size:  {file_size_mb:.2f} MB")
            print("=" * 60)
            print("\nTo launch the standalone application:")
            print(f"  Run: {exe_path}")
        else:
            print(f"\n[!] Build finished but ZennyFLAC_Player.exe was not found in {dist_dir}.")
    except subprocess.CalledProcessError as e:
        print(f"\n[!] PyInstaller build failed with exit code: {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
