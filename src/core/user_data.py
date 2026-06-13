r"""
ユーザーデータの書き込みパスを一元管理する。

- 開発時（プロジェクト直下から実行）: data/ ディレクトリを使用
- インストール版 / パッケージ実行時: %APPDATA%\InfuruToNoShito\ (Windows) を使用

判定ロジック:
  プロジェクトルートの data/ が書き込み可能なら開発モード扱い。
  それ以外は OS の標準ユーザーデータディレクトリを使用する。
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

_APP_NAME = "InfuruToNoShito"

# プロジェクトルート直下の data/ （開発時・gitリポジトリ内）
_DEV_DATA_DIR = Path(__file__).parent.parent.parent / "data"

_cached_dir: Path | None = None


def user_data_dir() -> Path:
    """
    ユーザーデータの書き込み先ディレクトリを返す。
    ディレクトリは存在しない場合自動作成する。
    """
    global _cached_dir
    if _cached_dir is not None:
        return _cached_dir

    # 開発時: プロジェクトの data/ が使用可能であればそちらを使う
    try:
        _DEV_DATA_DIR.mkdir(parents=True, exist_ok=True)
        # 書き込みテスト
        test_file = _DEV_DATA_DIR / ".write_test"
        test_file.touch()
        test_file.unlink()
        _cached_dir = _DEV_DATA_DIR
        return _cached_dir
    except OSError:
        pass

    # インストール環境: OS 標準のユーザーデータディレクトリ
    base: Path
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    app_dir = base / _APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    _cached_dir = app_dir
    return _cached_dir
