"""
BGM ダウンロードスクリプト
使い方:
    # TRACKS リストの全曲をダウンロード
    python tools/download_bgm.py

    # URL を直接指定（タイトルで自動命名）
    python tools/download_bgm.py https://www.youtube.com/watch?v=XXXXX

    # 複数 URL を一括ダウンロード
    python tools/download_bgm.py URL1 URL2 URL3

    # 出力ファイル名を指定（URL 1 つのとき）
    python tools/download_bgm.py URL --name my_song.mp3

    # 出力先ディレクトリを変更
    python tools/download_bgm.py URL --out-dir ./music
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_OUT_DIR = Path(__file__).parent.parent / "assets" / "music" / "bgm"

_FFMPEG_CANDIDATES = [
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\TuneFab All-in-one Music Converter\ffmpeg.exe",
    r"C:\Users\{}\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-7.1-full_build\bin\ffmpeg.exe".format(
        __import__("os").environ.get("USERNAME", "")
    ),
]

TRACKS = [
    ("il_vento_d'oro.mp3",          "https://www.youtube.com/watch?v=U0TXIXTzJEY"),
    ("The_world_of_spirit.mp3",     "https://www.youtube.com/watch?v=IpLxcJBSCDs"),
    ("Rebirth_the_edge.mp3",        "https://www.youtube.com/watch?v=gLW78ZV2RSY"),
    ("シズメシズメ.mp3",              "https://www.youtube.com/watch?v=lYq5HNcd8Gg"),
    ("Death_by_Glamour.mp3",        "https://www.youtube.com/watch?v=qeDIZCc6Cyo"),
    ("決戦_FF10.mp3",                "https://www.youtube.com/watch?v=9FgemvjlHw8"),
    ("GREEN_HILL_ZONE.mp3",         "https://www.youtube.com/watch?v=G-i8HYi1QH0"),
    ("ビッグブリッヂの死闘.mp3",      "https://www.youtube.com/watch?v=1a8OirsKVbc"),
    ("決戦！N.mp3",                  "https://www.youtube.com/watch?v=MFjRj0iQkPc"),
]


def _find_ffmpeg() -> str | None:
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")
    for p in _FFMPEG_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _build_cmd(url: str, out_path: str, ffmpeg: str | None) -> list[str]:
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", out_path,
    ]
    if ffmpeg:
        cmd += ["--ffmpeg-location", str(Path(ffmpeg).parent)]
    cmd.append(url)
    return cmd


def _download(url: str, out_path: Path | None, out_dir: Path, ffmpeg: str | None) -> bool:
    """1 URL をダウンロードする。成功で True を返す。"""
    if out_path is not None:
        # 出力ファイル名が確定している場合
        if out_path.exists():
            print(f"[SKIP] {out_path.name} (既存)")
            return True
        print(f"[DL]   {out_path.name} ...")
        template = str(out_path)
    else:
        # タイトルから自動命名
        template = str(out_dir / "%(title)s.%(ext)s")
        print(f"[DL]   {url} ...")

    cmd = _build_cmd(url, template, ffmpeg)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("       → OK")
        return True
    else:
        print("       → FAILED")
        print(result.stderr[-600:] if result.stderr else "(no stderr)")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube → MP3 ダウンローダー")
    parser.add_argument("urls", nargs="*", metavar="URL", help="ダウンロードする YouTube URL（省略時は TRACKS リスト全件）")
    parser.add_argument("--name", metavar="FILENAME", help="出力ファイル名（URL が 1 つのときのみ有効）")
    parser.add_argument("--out-dir", metavar="DIR", default=None, help=f"出力ディレクトリ（デフォルト: {DEFAULT_OUT_DIR}）")
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg = _find_ffmpeg()
    if ffmpeg:
        print(f"[ffmpeg] {ffmpeg}")
    else:
        print("[WARNING] ffmpeg が見つかりません。mp3 変換ができない場合があります。")
        print("          winget install Gyan.FFmpeg  または  choco install ffmpeg  でインストール後、")
        print("          ターミナルを再起動して再実行してください。\n")

    if args.urls:
        if args.name and len(args.urls) > 1:
            parser.error("--name は URL が 1 つのときのみ指定できます。")

        ok = fail = 0
        for url in args.urls:
            out_path = (out_dir / args.name) if (args.name and len(args.urls) == 1) else None
            if _download(url, out_path, out_dir, ffmpeg):
                ok += 1
            else:
                fail += 1
        print(f"\n完了: {ok} 件成功 / {fail} 件失敗")
    else:
        # 引数なし → TRACKS リスト全件
        ok = skip = fail = 0
        for filename, url in TRACKS:
            out_path = out_dir / filename
            if out_path.exists():
                print(f"[SKIP] {filename} (既存)")
                skip += 1
                continue
            if _download(url, out_path, out_dir, ffmpeg):
                ok += 1
            else:
                fail += 1
        print(f"\n完了: {ok} 件成功 / {skip} 件スキップ / {fail} 件失敗")


if __name__ == "__main__":
    main()
