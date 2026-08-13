import sys
import os
from pathlib import Path

def get_bundle_dir() -> Path:
    """Returns the base directory for bundled assets (frontend, templates, etc.)."""
    if getattr(sys, 'frozen', False):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        return Path(getattr(sys, '_MEIPASS', sys.executable)).resolve()
    # Development mode: return project root
    return Path(__file__).resolve().parent.parent.parent

def get_app_data_dir() -> Path:
    """Returns the writable directory for app data (config, db, cache)."""
    if getattr(sys, 'frozen', False):
        appdata = os.getenv('APPDATA')
        if appdata:
            data_dir = Path(appdata) / "ZFPlayer"
        else:
            data_dir = Path(sys.executable).parent / "data_user"
    else:
        # Development mode: use project root if writable or fallback to APPDATA
        project_root = Path(__file__).resolve().parent.parent.parent
        if project_root.exists():
            data_dir = project_root
        else:
            appdata = os.getenv('APPDATA')
            data_dir = Path(appdata) / "ZFPlayer" if appdata else project_root

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def get_config_path() -> str:
    path = get_app_data_dir() / "config" / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)

def get_db_path() -> str:
    path = get_app_data_dir() / "data" / "library.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)

def get_cache_dir() -> str:
    path = get_app_data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
