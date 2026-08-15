# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# 1. Collect all data files (Frontend glassmorphism UI, icons, soundfile C-libraries)
datas = [
    ('frontend', 'frontend'),
    ('app_icon.ico', '.'),
]

try:
    datas += collect_data_files('soundfile')
except Exception:
    pass

# 2. Collect all hidden imports cleanly
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
] + collect_submodules('backend')

# 3. PyInstaller Analysis
a = Analysis(
    ['backend/app.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'tcl', '_tkinter', 'matplotlib', 'scipy', 'pandas',
        'IPython', 'pydoc', 'doctest', 'unittest', 'xmlrpc', 'curses',
        'test', 'tests'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 4. Pure Python Bytecode Archive
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 5. Executable Binary Generation (upx=False for 100% WASAPI / PortAudio C-driver stability)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ZennyFLAC_Player',
    icon=os.path.abspath('app_icon.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
