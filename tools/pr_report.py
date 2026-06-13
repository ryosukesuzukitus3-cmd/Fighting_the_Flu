"""Markdown から自己完結 HTML レポートを生成し、media ブランチへ上げて
htmlpreview の描画リンクを出力する。

plain モードは API/トークン不要・ユーザー操作不要で完全自律（対話フックや
ブラウザ起動を伴わない）。fancy モードは Claude API を呼ぶ（トークン消費）ので
明示オプトイン時のみ。描画は `.claude/hooks/md_to_html.py` の関数を直接利用する
（CLI を叩かないのでブラウザは開かない）。

使い方:
  python tools/pr_report.py docs/design.md
  python tools/pr_report.py --fancy docs/design.md
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))

from pr_media import _owner_repo, _ensure_branch, _upload, _slug, _DEFAULT_BRANCH_NAME  # noqa: E402

_HTML_STAGE = ROOT / ".html" / "pr"   # 生成HTMLの一時置き場（.html は gitignore 済み）


def _render_html(src: Path, fancy: bool) -> Path:
    try:
        import md_to_html as mdh
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"md_to_html を読み込めません（.claude/hooks/md_to_html.py）: {e}")

    md = src.read_text(encoding="utf-8")
    if fancy:
        try:
            html = mdh.render_fancy(md, src)
        except Exception as e:  # noqa: BLE001  APIキー無し等は plain にフォールバック
            print(f"[pr-report] fancy 生成に失敗→plain にフォールバック: {e}", file=sys.stderr)
            html = mdh.render_plain(mdh.convert_markdown(md), md, src)
    else:
        html = mdh.render_plain(mdh.convert_markdown(md), md, src)

    _HTML_STAGE.mkdir(parents=True, exist_ok=True)
    out = _HTML_STAGE / (src.stem + ".html")
    out.write_text(html, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("markdown", help="変換する Markdown ファイル")
    p.add_argument("--fancy", action="store_true",
                   help="Claude API で SVG 強化 HTML を生成（トークン消費・要オプトイン）")
    p.add_argument("--label", default=None, help="リンク文言（既定: ファイル名）")
    p.add_argument("--subdir", default=None, help="media 内サブフォルダ名（既定: 日時）")
    p.add_argument("--branch", default=_DEFAULT_BRANCH_NAME, help="ホスト用ブランチ（既定 media）")
    args = p.parse_args(argv)

    src = Path(args.markdown)
    if not src.is_file():
        raise SystemExit(f"ファイルが見つかりません: {src}")

    html_path = _render_html(src.resolve(), args.fancy)

    owner, repo = _owner_repo()
    _ensure_branch(owner, repo, args.branch)
    subdir = args.subdir or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = f"pr-html/{subdir}/{_slug(html_path.name)}"
    raw = _upload(owner, repo, args.branch, html_path, dest)
    preview = f"https://htmlpreview.github.io/?{raw}"
    label = args.label or src.stem
    mode = "fancy" if args.fancy else "plain"
    print(f"[{label}（{mode}）]({preview})")   # 貼り付け用 Markdown リンク
    print(raw, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
