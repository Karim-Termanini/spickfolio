# PyInstaller spec — single-file bundle for Windows (.exe) and Linux (AppImage/.deb).
# Build: installer/build-windows-installer.ps1  or  installer/build-linux-installer.sh

from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

datas = [
    (str(root / 'index.html'), '.'),
    (str(root / 'styles.css'), '.'),
    (str(root / 'cheat-sheet-data.json'), '.'),
    (str(root / 'de.json'), '.'),
    (str(root / 'en.json'), '.'),
    (str(root / 'ar.json'), '.'),
    (str(root / 'js'), 'js'),
    (str(root / 'assets'), 'assets'),
]

hiddenimports = [
    'spick_folio.main',
    'spick_folio.handler',
    'spick_folio.config',
    'spick_folio.static_files',
    'spick_folio.data_helpers',
    'spick_folio.download_service',
    'spick_folio.download_jobs',
    'spick_folio.rdatasets_loader',
    'spick_folio.kaggle_helpers',
    'spick_folio.hf_cache',
    'spick_folio.capabilities',
    'spick_folio.desktop_actions',
    'spick_folio.security',
    'spick_folio.rate_limit',
    'http.server',
    'socketserver',
    'email.mime.multipart',
    'email.mime.text',
    'email.mime.base',
]

a = Analysis(
    ['spick_folio/launcher.py'],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='spickFolio',
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
)
