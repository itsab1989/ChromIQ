# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ChromIQ — Linux (x86_64 / aarch64).

Build command (run from the repo root with venv active):
    pyinstaller ChromIQLinux.spec

Result: dist/ChromIQ/ChromIQ  (one-dir bundle)

Notes:
- No ``BUNDLE()`` — that construct is macOS-only.
- ``pyobjc`` is excluded via requirements.txt's ``sys_platform == "darwin"``
  marker, so we do not even attempt to collect it here.
- ``pycups`` is the standard Linux CUPS binding; keep it as a hidden import.
- The runtime ``QIcon`` loads ``assets/app_icon.png``; PyInstaller's Linux
  EXE does not embed an icon (Linux desktop integration uses ``.desktop``
  files separately), so we pass no ``icon=`` to ``EXE``.
"""

import os
import sys
import certifi
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

certifi_where = certifi.where()


def _find_system_lib(name):
    """Locate a system shared library on the build host.

    Returns the absolute path of the first match found in the standard
    multi-arch / lib64 / lib search dirs, or ``None`` if not present.
    """
    for d in (
        '/usr/lib/x86_64-linux-gnu',
        '/usr/lib/aarch64-linux-gnu',
        '/lib/x86_64-linux-gnu',
        '/lib/aarch64-linux-gnu',
        '/usr/lib64',
        '/lib64',
        '/usr/lib',
        '/lib',
    ):
        p = os.path.join(d, name)
        if os.path.exists(p):
            # Return the SONAME-style path (libxcb-cursor.so.0) — NOT the
            # realpath — because PyInstaller uses the basename of the source
            # path when bundling, and the Qt xcb plugin is linked against
            # the SONAME, not the full version triple.
            return p
    return None


# Qt 6.5+ requires libxcb-cursor.so.0 (and a handful of other xcb-* libs)
# at runtime to load the xcb platform plugin.  PyInstaller's Qt hook ships
# the plugin .so itself but never bundles these system deps, so on minimal
# distros (or distros that just don't have libxcb-cursor0 installed) the
# binary aborts with "qt.qpa.plugin: From 6.5.0, xcb-cursor0 or
# libxcb-cursor0 is needed to load the Qt xcb platform plugin".
# Bundle them from the build host so the tarball is self-contained.
_xcb_runtime_libs = [
    'libxcb-cursor.so.0',
    'libxcb-icccm.so.4',
    'libxcb-image.so.0',
    'libxcb-keysyms.so.1',
    'libxcb-randr.so.0',
    'libxcb-render-util.so.0',
    'libxcb-shape.so.0',
    'libxcb-xkb.so.1',
    'libxkbcommon-x11.so.0',
]
_xcb_binaries = []
for _lib in _xcb_runtime_libs:
    _path = _find_system_lib(_lib)
    if _path:
        # Land the lib in the bundle root next to the binary; PyInstaller's
        # default RUNPATH ($ORIGIN) makes it discoverable to the Qt plugin
        # that needs it.
        _xcb_binaries.append((_path, '.'))
        print(f"[ChromIQLinux.spec] Bundling {_lib} from {_path}", file=sys.stderr)
    else:
        print(
            f"[ChromIQLinux.spec] WARNING: {_lib} not found on build host — "
            "runtime may fail on distros without it pre-installed.",
            file=sys.stderr,
        )

# imagecodecs's LZW/JPEG codecs live in compiled C extensions PyInstaller
# can't find via static analysis alone — collect everything explicitly.
_ic_datas, _ic_binaries, _ic_hiddenimports = collect_all('imagecodecs')

# PyQt6-WebEngine ships extra runtime data (locales, resources) that the
# default hook on Linux sometimes misses.
_we_datas, _we_binaries, _we_hiddenimports = collect_all('PyQt6-WebEngine')

# numpy 2.4+ links against a SciPy-built OpenBLAS that auditwheel places at
# ``numpy.libs/`` (a sibling of the numpy package).  Bundle every .so we
# find so ``import numpy`` doesn't fail at runtime.
import numpy as _np_pkg
_np_binaries = list(collect_dynamic_libs('numpy'))
_np_dir = os.path.dirname(_np_pkg.__file__)
for _root, _dirs, _files in os.walk(_np_dir):
    for _f in _files:
        if _f.endswith('.so'):
            _np_binaries.append((os.path.join(_root, _f), '.'))
_np_libs_sibling = os.path.join(os.path.dirname(_np_dir), 'numpy.libs')
if os.path.isdir(_np_libs_sibling):
    for _f in os.listdir(_np_libs_sibling):
        if _f.endswith('.so') or '.so.' in _f:
            _np_binaries.append((os.path.join(_np_libs_sibling, _f), '.'))
for _candidate_pkg in ('scipy_openblas64', 'scipy_openblas32'):
    try:
        _np_binaries.extend(collect_dynamic_libs(_candidate_pkg))
    except Exception:
        pass
print(
    f"[ChromIQLinux.spec] Bundling {len(_np_binaries)} numpy/openblas entries: "
    f"{sorted({os.path.basename(p) for p, _ in _np_binaries})}",
    file=sys.stderr,
)

# Bit-exact gamut-mapping helper (native/chromiq-gammap). Built by the CI CMake
# step before PyInstaller; bundled under native/ so resource_path() finds it at
# runtime. Absent in a plain local run (the app then falls back to the fast
# Python mapper), so include it only when present.
_gm_path = os.path.join('native', 'chromiq-gammap')
_gammap_datas = [(_gm_path, 'native')] if os.path.exists(_gm_path) else []
if not _gammap_datas:
    print(f"[ChromIQLinux.spec] {_gm_path} not built — bit-exact gamut helper "
          f"unavailable in this bundle (fast mapper still works).")

# Chart-reading engine (native/chromiq-chartread, #126). Bundled when CI built
# it; otherwise the app falls back to stock chartread.
_cr_path = os.path.join('native', 'chromiq-chartread')
_engine_datas = [(_cr_path, 'native')] if os.path.exists(_cr_path) else []
if not _engine_datas:
    print(f"[ChromIQLinux.spec] {_cr_path} not built — chart-reading engine "
          f"unavailable in this bundle (stock chartread still works).")

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[*_ic_binaries, *_we_binaries, *_np_binaries, *_xcb_binaries],
    datas=[
        ('assets',               'assets'),
        ('data/parameters.yaml', 'data'),
        (certifi_where,          'certifi'),
        *_gammap_datas,
        *_engine_datas,
        *_ic_datas,
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
        'PyQt6.QtWebChannel',
        'PIL.Image',
        'PIL.ImageFile',
        'PIL.ImageCms',
        'PIL.TiffImagePlugin',
        'yaml',
        'cups',
        'tifffile',
        'numpy',
        *_ic_hiddenimports,
        *_we_hiddenimports,
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
