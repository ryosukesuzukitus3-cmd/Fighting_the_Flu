"""自己完結 HTML を `media` ブランチへ上げ、描画リンク（htmlpreview）を出力する。

GitHub はリポジトリ上の HTML を text/plain で返す（ソース表示のみ）ため、
描画されたページを見せるには htmlpreview.github.io プロキシ経由の URL にする。
インライン CSS/SVG で外部依存のない自己完結 HTML（例: `.claude/hooks/md_to_html.py`
の fancy 出力）と相性が良い。アップロード処理は pr_media と共通。

使い方:
  python tools/pr_html.py report.html
  python tools/pr_html.py --subdir design .html/docs/design.html

出力（そのまま PR 本文に貼れる Markdown リンク）:
  [title](https://htmlpreview.github.io/?https://raw.githubusercontent.com/<o>/<r>/media/<path>)
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

# 同じ tools/ ディレクトリの共通処理を再利用（run.py は tools/ を起点に実行する）
from pr_media import _owner_repo, _ensure_branch, _upload, _slug, _DEFAULT_BRANCH_NAME


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("html", help="アップロードする HTML ファイル")
    p.add_argument("--label", default=None, help="リンク文言（既定: ファイル名）")
    p.add_argument("--subdir", default=None, help="media 内のサブフォルダ名（既定: 日時）")
    p.add_argument("--branch", default=_DEFAULT_BRANCH_NAME, help="ホスト用ブランチ（既定 media）")
    args = p.parse_args(argv)

    src = Path(args.html)
    if not src.is_file():
        raise SystemExit(f"ファイルが見つかりません: {src}")
    if src.suffix.lower() not in (".html", ".htm"):
        print(f"[pr-html] warning: {src.name} は HTML ではないかもしれません", file=sys.stderr)

    owner, repo = _owner_repo()
    _ensure_branch(owner, repo, args.branch)

    subdir = args.subdir or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = f"pr-html/{subdir}/{_slug(src.name)}"
    raw = _upload(owner, repo, args.branch, src, dest)
    preview = f"https://htmlpreview.github.io/?{raw}"
    label = args.label or src.stem
    print(f"[{label}]({preview})")     # 貼り付け用 Markdown リンク
    print(raw, file=sys.stderr)         # 参照用に raw URL も
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
