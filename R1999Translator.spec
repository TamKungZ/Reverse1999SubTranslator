# -*- mode: python ; coding: utf-8 -*-
import os


a = Analysis(
    ['ui/run_ui.py'],
    pathex=['ui'],
    binaries=[],
    datas=[('ui/r1999ui/assets', 'r1999ui/assets'), ('ui/r1999ui/locales', 'r1999ui/locales')]
    + ([('ui/r1999ui/fonts', 'r1999ui/fonts')] if os.path.isdir('ui/r1999ui/fonts') else []),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    icon=['ui/r1999ui/assets/icon.ico'],
    name='R1999Translator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='R1999Translator',
)
