"""PR 本文に貼るための画像を `media` ブランチへアップして raw URL を出力する。

GitHub の PR 本文は Markdown のみ描画され HTML/CSS は無効化されるため、
スクショは「URLで参照できる画像」にする必要がある。本ツールは画像を main に
混ぜず、専用の `media` ブランチ（main へはマージしない）へ GitHub API 経由で
アップロードし、貼り付け用の Markdown 画像行を出力する。作業ツリーも汚さない。

使い方:
  python tools/pr_media.py before.png after.png
  python tools/pr_media.py --label "Stage3 弾" shot.png
  python tools/pr_media.py --subdir bullets before.png after.png

出力（1ファイル1行、そのまま PR 本文に貼れる）:
  ![label](https://raw.githubusercontent.com/<owner>/<repo>/media/<path>)

要件: gh（認証済み）。
"""
from __future__ import annotations

import argparse
import base64
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# gh が PATH に無い環境（インストール直後）向けのフォールバック
_GH_FALLBACK = r"C:\Program Files\GitHub CLI\gh.exe"
_DEFAULT_BRANCH_NAME = "media"


def _gh_exe() -> str:
    found = shutil.which("gh")
    if found:
        return found
    if Path(_GH_FALLBACK).exists():
        return _GH_FALLBACK
    raise SystemExit("gh CLI が見つかりません（PATH か C:\\Program Files\\GitHub CLI\\gh.exe）")


def _gh(args: list[str], *, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_gh_exe(), *args],
        input=stdin, capture_output=True, text=True, encoding="utf-8",
    )


def _owner_repo() -> tuple[str, str]:
    """origin の URL から owner/repo を取り出す。"""
    r = subprocess.run(["git", "remote", "get-url", "origin"],
                       capture_output=True, text=True)
    url = r.stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+)/(.+?)(?:\.git)?$", url)
    if not m:
        raise SystemExit(f"origin の GitHub URL を解釈できません: {url!r}")
    return m.group(1), m.group(2)


def _ensure_branch(owner: str, repo: str, branch: str) -> None:
    """media ブランチが無ければデフォルトブランチの先頭から作成する。"""
    check = _gh(["api", f"repos/{owner}/{repo}/branches/{branch}"])
    if check.returncode == 0:
        return
    # デフォルトブランチの SHA を取得して ref を作る
    default = _gh(["api", f"repos/{owner}/{repo}", "-q", ".default_branch"]).stdout.strip() or "main"
    sha = _gh(["api", f"repos/{owner}/{repo}/git/ref/heads/{default}", "-q", ".object.sha"]).stdout.strip()
    if not sha:
        raise SystemExit(f"デフォルトブランチ {default} の SHA を取得できませんでした")
    create = _gh(["api", "--method", "POST", f"repos/{owner}/{repo}/git/refs",
                  "-f", f"ref=refs/heads/{branch}", "-f", f"sha={sha}"])
    if create.returncode != 0:
        raise SystemExit(f"{branch} ブランチ作成に失敗:\n{create.stderr.strip()}")
    print(f"[pr-media] created branch '{branch}'", file=sys.stderr)


def _slug(name: str) -> str:
    stem = Path(name).stem
    slug = re.sub(r"[^0-9A-Za-z._-]+", "-", stem).strip("-") or "img"
    return slug + Path(name).suffix.lower()


def _upload(owner: str, repo: str, branch: str, img: Path, dest_path: str) -> str:
    data = img.read_bytes()
    body = json.dumps({
        "message": f"media: add {dest_path}",
        "branch": branch,
        "content": base64.b64encode(data).decode("ascii"),
    })
    r = _gh(["api", "--method", "PUT", f"repos/{owner}/{repo}/contents/{dest_path}",
             "--input", "-"], stdin=body)
    if r.returncode != 0:
        raise SystemExit(f"アップロード失敗 ({img.name}):\n{r.stderr.strip()}")
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{dest_path}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("images", nargs="+", help="アップロードする画像ファイル")
    p.add_argument("--label", default=None, help="alt テキスト（既定: ファイル名）")
    p.add_argument("--subdir", default=None, help="media 内のサブフォルダ名（既定: 日時）")
    p.add_argument("--branch", default=_DEFAULT_BRANCH_NAME, help="ホスト用ブランチ（既定 media）")
    args = p.parse_args(argv)

    paths = [Path(s) for s in args.images]
    missing = [str(x) for x in paths if not x.is_file()]
    if missing:
        raise SystemExit(f"ファイルが見つかりません: {missing}")

    owner, repo = _owner_repo()
    _ensure_branch(owner, repo, args.branch)

    subdir = args.subdir or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for img in paths:
        dest = f"pr-media/{subdir}/{_slug(img.name)}"
        url = _upload(owner, repo, args.branch, img, dest)
        label = args.label or img.stem
        print(f"![{label}]({url})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
