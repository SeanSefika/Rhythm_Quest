# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
app_dir = os.path.abspath('.')

a = Analysis(
    ['run_server.py'],
    pathex=[app_dir],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('forms.py', '.'),
    ],
    hiddenimports=[
        'flask',
        'flask_wtf',
        'flask_wtf.csrf',
        'wtforms',
        'wtforms.validators',
        'werkzeug',
        'werkzeug.security',
        'dotenv',
        'email_validator',
        'sqlite3',
        'jinja2',
        'markupsafe',
        'itsdangerous',
        'click',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['MySQLdb', 'mysql', 'pymysql', 'gunicorn'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='run_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='run_server',
)
