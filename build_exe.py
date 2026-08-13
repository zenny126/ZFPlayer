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

    # Clean previous build file if unlocked
    old_exe = project_root / "dist" / "ZFPlayer.exe"
    if old_exe.exists():
        try:
            old_exe.unlink()
            print("[+] Removed previous dist/ZFPlayer.exe")
        except Exception as e:
            print(f"[!] Warning: Could not remove old {old_exe}: {e}")

    print("\n[+] Running PyInstaller build...")
    cmd = [
        sys.executable,
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

            print("\n" + "=" * 60)
            print("  BUILD SUCCESSFUL!")
            print(f"  Executable output: {exe_path}")
            print("=" * 60)
            print("\nTo test the standalone application:")
            print(f"  Run: {exe_path}")
        else:
            print(f"\n[!] Build finished but ZFPlayer.exe was not found in {project_root / 'dist'}.")
    except subprocess.CalledProcessError as e:
        print(f"\n[!] PyInstaller build failed with exit code: {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
