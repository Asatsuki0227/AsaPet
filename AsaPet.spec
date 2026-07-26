# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

# 收集 live2d-py 的所有子模块 + 二进制（Cubism Core DLL）+ 数据文件
live2d_datas, live2d_binaries, live2d_hiddenimports = collect_all('live2d')

a = Analysis(
    ['desktop_pet.py'],
    pathex=[],
    binaries=live2d_binaries,
    datas=[('1.png', '.'), ('app.ico', '.')] + live2d_datas,
    hiddenimports=[
        'PySide6.QtWebSockets',
        'PySide6.QtNetwork',
        'PySide6.QtOpenGLWidgets',
    ] + live2d_hiddenimports,
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
    name='AsaPet',
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
    icon=['app.ico'],
)
