# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all
from pathlib import Path

project_root = Path(SPECPATH)
datas = [
    (str(project_root / 'mediaforge/ui/assets/square-letter-m.svg'), 'mediaforge/ui/assets'),
    (str(project_root / 'LICENSE'), '.'),
    (str(project_root / 'THIRD_PARTY_NOTICES.md'), '.'),
    (str(project_root / 'docs/LICENCIAMENTO_QT.md'), 'docs'),
    (str(project_root / 'docs/qt-source-manifest.md'), 'docs'),
]
license_root = project_root / 'LICENSES'
datas += [
    (str(path), str(Path('LICENSES') / path.relative_to(license_root).parent))
    for path in license_root.rglob('*')
    if path.is_file()
]
binaries = []
hiddenimports = []
hiddenimports += collect_submodules('mediaforge')
hiddenimports += collect_submodules('yt_dlp')
tmp_ret = collect_all('yt_dlp_ejs')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    [str(project_root / 'mediaforge/app.py')],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['mutagen'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MediaForgeLocal',
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
    name='MediaForgeLocal',
)
