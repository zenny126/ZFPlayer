# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import webview
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None

# 1. Collect all frontend UI, icons and package data files
datas = [
    ('frontend', 'frontend'),
    ('app_icon.ico', '.'),
]

for pkg in ['webview', 'clr_loader', 'pythonnet', '_sounddevice_data', '_soundfile_data', 'syncedlyrics', 'certifi', 'mutagen']:
    try:
        datas += collect_data_files(pkg)
    except Exception as e:
        print(f"Notice: collect_data_files('{pkg}'): {e}")

# Explicitly map webview native libraries for pywebview interop resolution
webview_lib = os.path.join(os.path.dirname(webview.__file__), 'lib')
if os.path.exists(webview_lib):
    for f in os.listdir(webview_lib):
        full = os.path.join(webview_lib, f)
        if os.path.isfile(full):
            datas.append((full, '.'))
    native_x64 = os.path.join(webview_lib, 'runtimes', 'win-x64', 'native', 'WebView2Loader.dll')
    if os.path.exists(native_x64):
        datas.append((native_x64, '.'))
        datas.append((native_x64, 'runtimes/win-x64/native'))

# 2. Collect all dynamic C/C++ libraries (PortAudio, libsndfile, WebView2Loader, ClrLoader, PythonNet)
binaries = []
for pkg in ['_sounddevice_data', '_soundfile_data', 'webview', 'clr_loader', 'pythonnet']:
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception as e:
        print(f"Notice: collect_dynamic_libs('{pkg}'): {e}")

# 3. Collect all hidden imports cleanly across all modules
hiddenimports = [
    'bottle',
    'webview',
    'webview.platforms',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr',
    'clr_loader',
    'pythonnet',
    'soundfile',
    '_soundfile',
    'sounddevice',
    '_sounddevice',
    'mutagen',
    'numpy',
    'syncedlyrics',
    'PIL',
    'PIL.Image',
    'PIL.ImageFilter',
    'sqlite3',
    'wsgiref',
    'wsgiref.simple_server',
    'socketserver',
    'http',
    'http.server',
    'email',
    'email.message',
    'email.parser',
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
]

for sub_pkg in ['backend', 'webview', 'mutagen', 'syncedlyrics', 'pythonnet', 'clr_loader']:
    try:
        hiddenimports += collect_submodules(sub_pkg)
    except Exception as e:
        print(f"Notice: collect_submodules('{sub_pkg}'): {e}")

# 4. PyInstaller Analysis
a = Analysis(
    ['backend/app.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'tcl', '_tkinter', 'matplotlib', 'scipy', 'pandas',
        'IPython', 'pydoc', 'doctest', 'unittest', 'test', 'tests'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 5. Pure Python Bytecode Archive
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Version info resource file if available
version_file = 'version_info.txt' if os.path.exists('version_info.txt') else None

# 6. Executable Binary Generation (upx=False for 100% WASAPI / PortAudio C-driver stability)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ZennyFLAC_Player',
    icon=os.path.abspath('app_icon.ico'),
    version=version_file,
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
