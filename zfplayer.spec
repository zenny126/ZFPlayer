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
    excludes=[
        'tkinter', 'tcl', '_tkinter', 'matplotlib', 'scipy', 'pandas',
        'IPython', 'pydoc', 'doctest', 'unittest', 'xmlrpc', 'curses',
        'test', 'tests',
        'setuptools', 'distutils', 'pip',
        'numpy.testing', 'numpy.f2py', 'numpy.distutils', 'numpy.random._examples',
        'PIL.SpiderImagePlugin', 'PIL.EpsImagePlugin', 'PIL.PdfImagePlugin',
        'PIL.FpxImagePlugin', 'PIL.MicImagePlugin', 'PIL.MpoImagePlugin',
        'PIL.PcdImagePlugin', 'PIL.PcxImagePlugin', 'PIL.PixarImagePlugin',
        'PIL.PpmImagePlugin', 'PIL.PsdImagePlugin', 'PIL.SgiImagePlugin',
        'PIL.SunImagePlugin', 'PIL.TgaImagePlugin', 'PIL.XbmImagePlugin',
        'PIL.XpmImagePlugin', 'PIL.CurImagePlugin', 'PIL.DcxImagePlugin',
        'PIL.FliImagePlugin', 'PIL.GbrImagePlugin', 'PIL.GdImagePlugin',
        'PIL.ImImagePlugin', 'PIL.ImtImagePlugin', 'PIL.IptcImagePlugin',
        'PIL.McIdasImagePlugin', 'PIL.PalmImagePlugin', 'PIL.WmfImagePlugin',
        'PIL.XpmImagePlugin'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Strip heavy unused C-extensions from bundle to optimize binary size
excluded_binaries = {
    '_avif.cp311-win_amd64.pyd',
    '_imagingft.cp311-win_amd64.pyd',
    '_imagingtk.cp311-win_amd64.pyd',
}
a.binaries = [b for b in a.binaries if not any(b[0].lower().endswith(ex.lower()) for ex in excluded_binaries)]

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
    upx_dir=os.path.abspath('.'),
    upx_exclude=['vcruntime140.dll', 'msvcp140.dll', 'python311.dll'],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
