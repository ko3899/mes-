# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['mes_collector_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('backend', 'backend'),
        ('frontend', 'frontend'),
        ('admin', 'admin'),
        ('database', 'database'),
    ],
    hiddenimports=['flask', 'openpyxl', 'psutil', 'waitress', 'sqlite3', 'webview', 'clr_loader'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MES采集端',
    debug=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    icon=None,
)
