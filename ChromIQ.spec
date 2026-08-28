# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ChromIQ.

Build command:
    source .venv/bin/activate
    pyinstaller ChromIQ.spec

For a universal2 (ARM + Intel) build:
    PYINSTALLER_TARGET_ARCH=universal2 pyinstaller ChromIQ.spec

The result will be in dist/ChromIQ.app
"""

import os
import sys
import platform
import certifi
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs
certifi_where = certifi.where()
_target_arch = os.environ.get("PYINSTALLER_TARGET_ARCH") or None

# Read APP_VERSION from core/version.py so the macOS bundle's Info.plist
# stays in sync with the in-app masthead/About strings — hardcoding here
# silently shipped 3.5.0 in Finder Get Info for every release since 3.5.0.
_version_ns = {}
with open(os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'core', 'version.py'),
          'r', encoding='utf-8') as _vf:
    exec(_vf.read(), _version_ns)
_APP_VERSION = _version_ns['APP_VERSION']
# CFBundleShortVersionString must be a dotted *numeric* string — a pre-release
# suffix like "-beta.1" is rejected by codesign/notarisation. Keep the numeric
# core for the bundle plist; the full string still shows in the in-app About.
_CF_VERSION = _APP_VERSION.split('-')[0]

# Collect all imagecodecs binaries/data: its LZW and other codecs live in
# compiled C extensions that PyInstaller won't find via static analysis alone.
_ic_datas, _ic_binaries, _ic_hiddenimports = collect_all('imagecodecs')

_we_datas, _we_binaries, _we_hiddenimports = collect_all('PyQt6-WebEngine')

# freetype-py ships the native libfreetype it binds to; collect_all bundles that
# dylib + the module so the vector-PDF glyph outlining works in the frozen app.
_ft_datas, _ft_binaries, _ft_hiddenimports = collect_all('freetype')

# ...except on Windows/ARM, where freetype-py has no wheel with a bundled native
# lib (collect_all finds nothing to ship). Bundle our vendored ARM64 FreeType so
# the vector-PDF export works in the frozen ARM app too; core.freetype_bootstrap
# adds this dir to the DLL search path at startup (#72).
_ft_vendor_datas = []
if sys.platform == 'win32' and platform.machine().upper() in ('ARM64', 'AARCH64'):
    _ft_vp = os.path.join('vendor', 'freetype', 'win-arm64', 'freetype.dll')
    if os.path.exists(_ft_vp):
        _ft_vendor_datas = [(_ft_vp, 'vendor/freetype/win-arm64')]
    else:
        print(f"[ChromIQ.spec] {_ft_vp} missing — vector-PDF export will be "
              f"unavailable in this Windows/ARM bundle.")

# numpy 2.4+ links against a SciPy-built OpenBLAS (`libscipy_openblas64_.dylib`)
# that may live in any of three places depending on platform / wheel layout:
#   (a) inside numpy at `numpy/.dylibs/` (delocate-wheel macOS layout)
#   (b) sibling `numpy.libs/` (auditwheel Linux layout — sometimes seen on macOS too)
#   (c) external package `scipy_openblas64` (numpy as runtime dep)
# Neither hook-numpy.py nor a plain collect_dynamic_libs('numpy') picks it up
# reliably on the universal2 macOS build, leaving Contents/Frameworks/ missing
# the dylib and crashing the app at `import numpy` before any GUI code runs.
# Walk all three locations and bundle every .dylib found — destdir '.' lands
# them at the bundle root where numpy/_core/_multiarray_umath.so resolves them
# via `@rpath` (rpath = `@loader_path/../..`). See issue #11.
import numpy as _np_pkg
_np_binaries = list(collect_dynamic_libs('numpy'))
_np_dir = os.path.dirname(_np_pkg.__file__)
for _root, _dirs, _files in os.walk(_np_dir):
    for _f in _files:
        if _f.endswith('.dylib'):
            _np_binaries.append((os.path.join(_root, _f), '.'))
_np_libs_sibling = os.path.join(os.path.dirname(_np_dir), 'numpy.libs')
if os.path.isdir(_np_libs_sibling):
    for _f in os.listdir(_np_libs_sibling):
        if _f.endswith('.dylib'):
            _np_binaries.append((os.path.join(_np_libs_sibling, _f), '.'))
for _candidate_pkg in ('scipy_openblas64', 'scipy_openblas32'):
    try:
        _np_binaries.extend(collect_dynamic_libs(_candidate_pkg))
    except Exception:
        pass
print(f"[ChromIQ.spec] Bundling {len(_np_binaries)} numpy/openblas binary entries: "
      f"{sorted({os.path.basename(p) for p, _ in _np_binaries})}",
      file=sys.stderr)

# PyObjC (macOS native print dialog) — lazily-imported submodules need help.
if sys.platform == 'darwin':
    _oc_datas, _oc_binaries, _oc_hiddenimports = collect_all('objc')
    _ak_datas, _ak_binaries, _ak_hiddenimports = collect_all('AppKit')
else:
    _oc_datas = _oc_binaries = _oc_hiddenimports = []
    _ak_datas = _ak_binaries = _ak_hiddenimports = []

# Bit-exact gamut-mapping helper (native/chromiq-gammap[.exe]). Built by the
# CI CMake step before PyInstaller; bundled under native/ so resource_path()
# finds it at runtime. Absent in a plain local `pyinstaller` run (the app then
# just falls back to the fast Python mapper), so include it only when present.
_gm_name = 'chromiq-gammap.exe' if sys.platform == 'win32' else 'chromiq-gammap'
_gm_path = os.path.join('native', _gm_name)
_gammap_datas = [(_gm_path, 'native')] if os.path.exists(_gm_path) else []
if not _gammap_datas:
    print(f"[ChromIQ.spec] {_gm_path} not built — bit-exact gamut helper "
          f"will be unavailable in this bundle (fast mapper still works).")

# Chart-reading engine (native/chromiq-chartread[.exe], #126). Same pattern:
# present when CI built it, otherwise the app falls back to stock chartread.
_cr_name = 'chromiq-chartread.exe' if sys.platform == 'win32' else 'chromiq-chartread'
_cr_path = os.path.join('native', _cr_name)
_engine_datas = [(_cr_path, 'native')] if os.path.exists(_cr_path) else []
if not _engine_datas:
    print(f"[ChromIQ.spec] {_cr_path} not built — chart-reading engine "
          f"will be unavailable in this bundle (stock chartread still works).")

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[*_ic_binaries, *_we_binaries, *_oc_binaries, *_ak_binaries,
              *_np_binaries, *_ft_binaries],
    datas=[
        ('assets',           'assets'),
        ('data/parameters.yaml', 'data'),
        ('data/i18n',        'data/i18n'),
        ('data/scanner_targets', 'data/scanner_targets'),
        (certifi_where, 'certifi'),
        *_gammap_datas,
        *_engine_datas,
        *_ft_vendor_datas,
        *_ic_datas,
        *_we_datas,
        *_oc_datas,
        *_ak_datas,
        *_ft_datas,
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
        'PyQt6.QtWebChannel',
        'PIL.Image',
        'PIL.ImageFile',
        'PIL.ImageCms',
        'PIL.TiffImagePlugin',
        'yaml',
        'openpyxl',
        'cups',
        'tifffile',
        'numpy',
        'freetype',
        # CR30 instrument support (#159). ChromIQ reads a CR30 itself and feeds
        # the values to chartread with -x, so these are the ONLY way the
        # packaged app can reach the instrument. They are imported lazily
        # (workflow/cr30 degrades without them), which is exactly why PyInstaller
        # cannot find them on its own — and why their absence shows up as
        # "no USB device (No module named 'serial')" rather than a build error.
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'bleak',
        *_ic_hiddenimports,
        *_we_hiddenimports,
        *_oc_hiddenimports,
        *_ak_hiddenimports,
        *_ft_hiddenimports,
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=_target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ChromIQ',
)

app = BUNDLE(
    coll,
    name='ChromIQ.app',
    icon='assets/app_icon.icns',
    bundle_identifier='com.chromiq.app',
    info_plist={
        'CFBundleName':              'ChromIQ',
        'CFBundleDisplayName':       'ChromIQ',
        'CFBundleShortVersionString': _CF_VERSION,
        'CFBundleVersion':           _CF_VERSION,
        'NSHighResolutionCapable':   True,
        'NSPrincipalClass':          'NSApplication',
        'NSRequiresAquaSystemAppearance': False,
        'LSApplicationCategoryType': 'public.app-category.graphics-design',
        # Qt 6.11's frameworks declare minos 13.0 — on macOS 12 the app
        # launched and dyld killed it instantly (icon flash, no message).
        # Declaring the TRUE minimum makes older systems show Apple's clean
        # "requires macOS 13" dialog instead (forum report, Monterey).
        'LSMinimumSystemVersion':    '13.0',
        # Bluetooth permission for the CR30 (#159). ChromIQ reads that
        # instrument itself, over USB serial or Bluetooth LE, and bleak goes
        # through CoreBluetooth. macOS REFUSES CoreBluetooth to any app that
        # does not declare this, so without it the bundled app cannot see a
        # CR30 over Bluetooth at all -- while `python main.py` works, because a
        # dev run inherits Terminal's own permission and the .app is its own
        # responsible process. The string is what the user reads in the system
        # prompt, so it says what it is for in plain language.
        'NSBluetoothAlwaysUsageDescription':
            'ChromIQ uses Bluetooth to read measurements from a CR30 '
            'colour-measuring instrument. It is only used while you are '
            'measuring a chart, and never to connect to anything else.',
    },
)
