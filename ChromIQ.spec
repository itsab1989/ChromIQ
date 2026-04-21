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
_target_arch = os.environ.get("PYINSTALLER_TARGET_ARCH") or None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets',           'assets'),
        ('data/parameters.yaml', 'data'),
    ],
    hiddenimports=[
        'PyQt6.sip',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtPrintSupport',
        'PIL.Image',
        'PIL.ImageFile',
        'PIL.TiffImagePlugin',
        'yaml',
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
        'CFBundleShortVersionString': '1.3.1',
        'CFBundleVersion':           '1.3.1',
        'NSHighResolutionCapable':   True,
        'NSPrincipalClass':          'NSApplication',
        'NSRequiresAquaSystemAppearance': False,
        'LSApplicationCategoryType': 'public.app-category.graphics-design',
        'LSMinimumSystemVersion':    '12.0',
    },
)
