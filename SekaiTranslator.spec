# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

project_root = Path('.').resolve()
ui_root = project_root / 'sekai-ui'
core_root = project_root / 'sekai-core' / 'py' / 'src'

datas = []
binaries = []
hiddenimports = []

tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

def collect_tree(src: Path, dest: str):
    items = []
    if src.exists():
        for p in src.rglob('*'):
            if p.is_file():
                items.append((str(p), str(Path(dest) / p.relative_to(src).parent)))
    return items

datas += collect_tree(ui_root / 'themes', 'themes')
datas += collect_tree(ui_root / 'assets', 'assets')

a = Analysis(
    [str(ui_root / 'main.py')],
    pathex=[str(ui_root), str(core_root)],
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
    [],
    exclude_binaries=True,
    name='SekaiTranslatorV',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ui_root / 'assets' / 'app_icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SekaiTranslatorV',
)