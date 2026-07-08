# -*- mode: python ; coding: utf-8 -*-
# インフルとの死闘 — PyInstaller ビルド定義（onedir）
#
# onefile ではなく onedir を採用する理由:
#   - assets が約150MBあり、onefile は起動のたびに一時フォルダへ全展開して遅い
#   - onedir はウイルス対策ソフトの誤検知も相対的に少ない
# 配布時は dist/InfuruToNoShito/ を zip で固める（.github/workflows/release.yml が自動化）。
#
# アセット解決の前提:
#   src/ 以下は Path(__file__) からプロジェクトルート相対で assets/ と data/stages/ を
#   参照する。PyInstaller は凍結モジュールの __file__ を sys._MEIPASS 配下に設定するため、
#   datas で同じ相対位置に配置すればコード変更なしで解決される。
#   ユーザーデータ（ハイスコア等）は src/core/user_data.py が書き込み先を実行時に判定する。

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("assets", "assets"),
        ("data/stages", "data/stages"),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="InfuruToNoShito",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="InfuruToNoShito",
)
