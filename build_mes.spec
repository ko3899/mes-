# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['start_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('backend', 'backend'),
        ('frontend', 'frontend'),
        ('admin', 'admin'),
        ('database', 'database'),
        ('version.json', '.'),
    ],
    hiddenimports=['flask', 'openpyxl', 'psutil', 'waitress', 'sqlite3'],
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
    name='MES工厂管家',
    debug=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=True,
    icon=None,
)
