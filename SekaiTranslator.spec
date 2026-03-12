# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, Tree

datas = []
binaries = []
hiddenimports = []

tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Recursos do app
datas += Tree('sekai-ui\\themes', prefix='themes')
datas += Tree('sekai-ui\\assets', prefix='assets')

a = Analysis(
    ['sekai-ui\\main.py'],
    pathex=['.\\sekai-ui', '.\\sekai-core\\py\\src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='SekaiTranslator',
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
    icon=['sekai-ui\\assets\\app_icon.ico'],
)