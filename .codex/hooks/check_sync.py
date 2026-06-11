"""Stopフック: src/data/tools/docs のいずれかが変更されていたら
gen_docs + check_consistency を自動実行する。

不整合または docs ドリフトがあれば exit 2 + stderr にレポートを出力し、
Claude にそのターンでの修正を促す。

settings.json での登録:
  "Stop": [{"hooks": [{"type": "command", "command": ".venv/Scripts/python .codex/hooks/check_sync.py"}]}]
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).parent.parent.parent))
PYTHON      = str(PROJECT_DIR / ".venv" / "Scripts" / "python.exe")

_WATCH_DIRS = ["src", "data", "tools", "docs"]


def _has_changes() -> bool:
    """git status で監視ディレクトリに変更があるか確認する。"""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", *_WATCH_DIRS],
        capture_output=True, text=True, cwd=str(PROJECT_DIR)
    )
    return bool(result.stdout.strip())


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_DIR))


def main() -> None:
    if not _has_changes():
        sys.exit(0)  # 変更なし → スキップ（高速）

    errors: list[str] = []

    # 1. gen_docs で docs を自動再生成
    r = _run([PYTHON, str(PROJECT_DIR / "tools" / "run.py"), "docs"])
    if r.returncode != 0:
        errors.append(f"gen_docs.py failed:\n{r.stderr.strip()}")
    elif r.stdout.strip() and "no changes" not in r.stdout:
        # docs が更新された場合は警告として stderr に出す（エラーではない）
        print(r.stdout.strip(), file=sys.stderr)

    # 2. 整合性チェック
    r2 = _run([PYTHON, str(PROJECT_DIR / "tools" / "run.py"), "check"])
    if r2.returncode != 0:
        errors.append(f"check_consistency.py failed:\n{r2.stderr.strip()}")

    if errors:
        print("\n[check_sync] 整合性エラー: 次の問題を修正してください", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
