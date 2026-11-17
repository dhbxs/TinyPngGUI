# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: portable Windows GUI (no install)."""

from PyInstaller.utils.hooks import collect_all

block_cipher = None

ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")
dnd_datas, dnd_binaries, dnd_hidden = collect_all("tkinterdnd2")
cert_datas, cert_binaries, cert_hidden = collect_all("certifi")
tinify_datas, tinify_binaries, tinify_hidden = collect_all("tinify")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=ctk_binaries + dnd_binaries + cert_binaries + tinify_binaries,
    datas=ctk_datas + dnd_datas + cert_datas + tinify_datas,
    hiddenimports=ctk_hidden + dnd_hidden + cert_hidden + tinify_hidden + [
        "certifi",
        "tinify",
        "tinify_app",
        "tinify_app.gui",
        "tinify_app.config",
        "tinify_app.compressor",
    ],
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
    name="TinifyCompress",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
