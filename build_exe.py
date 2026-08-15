import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    print("=" * 60)
    print("      ZFPlayer - Automated Executable Packaging Build Script")
    print("=" * 60)

    # 1. Verify PyInstaller installation
    try:
        import PyInstaller
        print("[+] PyInstaller is installed.")
    except ImportError:
        print("[!] PyInstaller is not installed. Installing now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    project_root = Path(__file__).resolve().parent
    spec_file = project_root / "zfplayer.spec"

    if not spec_file.exists():
        print(f"[!] Error: {spec_file} not found!")
        sys.exit(1)

    # 2. Generate/Ensure all icon files exist
    try:
        sys.path.insert(0, str(project_root))
        from generate_icon import create_zfp_icon
        create_zfp_icon()
    except Exception as e:
        print(f"[!] Warning generating icons: {e}")

    # 3. Clean previous build files & PyInstaller bincache
    old_exe = project_root / "dist" / "ZFPlayer.exe"
    if old_exe.exists():
        try:
            old_exe.unlink()
            print("[+] Removed previous dist/ZFPlayer.exe")
        except Exception as e:
            print(f"[!] Warning: Could not remove old {old_exe}: {e}")

    build_temp = project_root / "build"
    if build_temp.exists():
        try:
            shutil.rmtree(build_temp, ignore_errors=True)
            print("[+] Cleaned temporary build directory.")
        except Exception:
            pass

    # Clear PyInstaller bincache in LocalAppData to avoid reusing UPX-corrupted binary stubs
    appdata_local = os.getenv('LOCALAPPDATA')
    if appdata_local:
        bincache = Path(appdata_local) / 'pyinstaller'
        if bincache.exists():
            try:
                shutil.rmtree(bincache, ignore_errors=True)
                print("[+] Cleaned PyInstaller binary cache.")
            except Exception:
                pass

    print("\n[+] Running Optimized PyInstaller build (-OO bytecode)...")
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
        exe_path = project_root / "dist" / "ZFPlayer.exe"
        if not exe_path.exists():
            exe_path = project_root / "dist" / "ZFPlayer" / "ZFPlayer.exe"

        if exe_path.exists():
            zenny_exe = project_root / "dist" / "ZennyFLAC_Player.exe"
            try:
                shutil.copy2(exe_path, zenny_exe)
                print(f"[+] Created branded executable: {zenny_exe}")
            except Exception as e:
                print(f"[!] Warning: Could not create {zenny_exe}: {e}")

            file_size_mb = os.path.getsize(zenny_exe if zenny_exe.exists() else exe_path) / (1024 * 1024)

            print("\n" + "=" * 60)
            print("  OPTIMIZED BUILD SUCCESSFUL!")
            print(f"  Branded Executable: {zenny_exe}")
            print(f"  File Size:          {file_size_mb:.2f} MB")
            print("=" * 60)
            print("\nTo test the standalone application:")
            print(f"  Run: {zenny_exe}")
        else:
            print(f"\n[!] Build finished but ZFPlayer.exe was not found in {project_root / 'dist'}.")
    except subprocess.CalledProcessError as e:
        print(f"\n[!] PyInstaller build failed with exit code: {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
