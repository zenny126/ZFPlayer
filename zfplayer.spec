# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Bundle frontend assets, static files and icons
datas = [
    ('frontend', 'frontend'),
    ('app_icon.ico', '.'),
]

# Collect soundfile DLLs if present
try:
    datas += collect_data_files('soundfile')
except Exception:
    pass

hiddenimports = [
    'bottle',
    'webview',
    'soundfile',
    'sounddevice',
    'mutagen',
    'numpy',
    'syncedlyrics',
    'PIL',
    'PIL.Image',
    'sqlite3',
    'wsgiref',
    'wsgiref.simple_server',
    'socketserver',
    'backend.api.player_api',
    'backend.api.library_api',
    'backend.api.lyrics_api',
    'backend.api.config_api',
    'backend.audio.engine',
    'backend.audio.decoder',
    'backend.audio.buffer',
    'backend.services.player_service',
    'backend.services.library_service',
    'backend.storage.database',
    'backend.storage.config',
    'backend.storage.cache',
    'backend.workers.scanner',
    'backend.workers.lyrics_worker',
    'backend.workers.metadata_worker',
    'backend.utils.path_utils',
]

a = Analysis(
    ['backend/app.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ZFPlayer',
    icon=os.path.abspath('app_icon.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
