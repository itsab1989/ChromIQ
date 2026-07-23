# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ChromIQ — Windows x64.

Build command (run from the repo root with venv active):
    pyinstaller ChromIQWin.spec

Result: dist/ChromIQ/ChromIQ.exe  (one-dir bundle)
"""

import os
import platform

import certifi
from PyInstaller.utils.hooks import collect_all

certifi_where = certifi.where()

# Read APP_VERSION from core/version.py (same approach as the macOS spec) and
# emit a Windows VERSIONINFO resource. An unsigned PyInstaller EXE with no
# version/publisher metadata reads as throwaway malware to Defender/SmartScreen
# heuristics; populating it sharply lowers the false-positive score.
_version_ns = {}
with open(os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'core', 'version.py'),
          'r', encoding='utf-8') as _vf:
    exec(_vf.read(), _version_ns)
_APP_VERSION = _version_ns['APP_VERSION']

_nums = _APP_VERSION.split('-')[0].split('.')
_vtuple = tuple(int(n) for n in (_nums + ['0', '0', '0', '0'])[:4])

_version_txt = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={_vtuple},
    prodvers={_vtuple},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Sebastian Reiprich'),
      StringStruct('FileDescription', 'ChromIQ - RGB printer ICC profiling'),
      StringStruct('FileVersion', '{_APP_VERSION}'),
      StringStruct('InternalName', 'ChromIQ'),
      StringStruct('LegalCopyright', 'Copyright (c) Sebastian Reiprich'),
      StringStruct('OriginalFilename', 'ChromIQ.exe'),
      StringStruct('ProductName', 'ChromIQ'),
      StringStruct('ProductVersion', '{_APP_VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
_version_path = os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'build', 'win_version_info.txt')
os.makedirs(os.path.dirname(_version_path), exist_ok=True)
with open(_version_path, 'w', encoding='utf-8') as _f:
    _f.write(_version_txt)

_ic_datas, _ic_binaries, _ic_hiddenimports = collect_all('imagecodecs')
_winpty_datas, _winpty_binaries, _winpty_hiddenimports = collect_all('winpty')

_we_datas, _we_binaries, _we_hiddenimports = collect_all('PyQt6-WebEngine')

# Bit-exact gamut-mapping helper (native/chromiq-gammap.exe). Built by the CI
# CMake+mingw step before PyInstaller; bundled under native/ so resource_path()
# finds it at runtime. Absent in a plain local run or on Windows-arm64 (where
# the app falls back to the fast Python mapper), so include it only when present.
_gm_path = os.path.join('native', 'chromiq-gammap.exe')
_gammap_datas = [(_gm_path, 'native')] if os.path.exists(_gm_path) else []
if not _gammap_datas:
    print(f"[ChromIQWin.spec] {_gm_path} not built — bit-exact gamut helper "
          f"unavailable in this bundle (fast mapper still works).")

# Chart-reading engine (native/chromiq-chartread.exe, #126). Bundled when CI
# built it; otherwise the app falls back to stock chartread.
_cr_path = os.path.join('native', 'chromiq-chartread.exe')
_engine_datas = [(_cr_path, 'native')] if os.path.exists(_cr_path) else []
if not _engine_datas:
    print(f"[ChromIQWin.spec] {_cr_path} not built — chart-reading engine "
          f"unavailable in this bundle (stock chartread still works).")

# Vector-PDF export (#72) needs libfreetype for glyph outlining. On Windows x64
# freetype-py's own PyInstaller hook (collect_dynamic_libs) bundles the wheel's
# libfreetype.dll automatically. On Windows/ARM there is no wheel with a native
# lib, so bundle our vendored ARM64 FreeType; core.freetype_bootstrap adds it to
# the DLL search path at startup so the export works there too. Without this,
# PDF export is silently unavailable on arm64 (it's imported lazily).
_ft_vendor_datas = []
if platform.machine().upper() in ('ARM64', 'AARCH64'):
    _ft_vp = os.path.join('vendor', 'freetype', 'win-arm64', 'freetype.dll')
    if os.path.exists(_ft_vp):
        _ft_vendor_datas = [(_ft_vp, 'vendor/freetype/win-arm64')]
    else:
        print(f"[ChromIQWin.spec] {_ft_vp} missing — vector-PDF export will be "
              f"unavailable in this Windows/ARM bundle.")

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[*_ic_binaries, *_winpty_binaries, *_we_binaries],
    datas=[
        ('assets',               'assets'),
        ('data/parameters.yaml', 'data'),
        ('data/i18n',            'data/i18n'),
        (certifi_where,          'certifi'),
        *_gammap_datas,
        *_engine_datas,
        *_ft_vendor_datas,
        *_ic_datas,
        *_winpty_datas,
        *_we_datas,
    ],
    hiddenimports=[
        'PyQt6.sip',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtPrintSupport',
        'PyQt6.QtMultimedia',   # measurement sounds (#131) — imported lazily in core.sound
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'PIL.Image',
        'PIL.ImageFile',
        'PIL.ImageCms',
        'PIL.TiffImagePlugin',
        'yaml',
        'openpyxl',  # lazily imported in workflow/i18n_roundtrip.py — PyInstaller misses it
        'tifffile',
        'numpy',
        *_ic_hiddenimports,
        *_winpty_hiddenimports,
        *_we_hiddenimports,
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['cups'],          # pycups is macOS/Linux-only
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ChromIQ',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon='assets/app_icon.ico',  # generated by CI from app_icon.png
    version=_version_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ChromIQ',
)
