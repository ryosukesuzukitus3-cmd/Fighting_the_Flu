"""Project command runner that prefers the local .venv and UTF-8 output.

Examples:
  python tools/run.py check
  python tools/run.py test
  python tools/run.py game
  python tools/run.py capture --stage 4 --boss --form 3
  python tools/run.py preview-boss --stage 4 --pattern all
  python tools/run.py stage3-rect-preview
  python tools/run.py stage3-rect-editor
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _project_python() -> Path:
    if os.name == "nt":
        candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def _env(headless: bool) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if headless:
        env.setdefault("SDL_VIDEODRIVER", "dummy")
        env.setdefault("SDL_AUDIODRIVER", "dummy")
    return env


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print(
            "usage: python tools/run.py "
            "{check|test|docs|docs-check|balance|game|capture|preview-boss|stage3-rect-preview|stage3-rect-editor|boss-concepts|dialogues|dummies|pr-media|pr-html|pr-report|pycompile} "
            "[args...]"
        )
        return 0

    py = str(_project_python())
    cmd = argv.pop(0)
    commands = {
        "check":      ([py, "tools/check_consistency.py", *argv], True),
        "test":       ([py, "-m", "pytest", *argv], True),
        "docs":       ([py, "tools/gen_docs.py", *argv], True),
        "docs-check": ([py, "tools/gen_docs.py", "--check", *argv], True),
        "balance":    ([py, "tools/balance_sheet.py", *argv], True),
        "game":       ([py, "main.py", *argv], False),
        "capture":    ([py, "tools/capture.py", *argv], True),
        "preview-boss": ([py, "tools/preview_boss.py", *argv], False),
        "stage3-rect-preview": ([py, "tools/stage3_rect_preview.py", *argv], True),
        "stage3-rect-editor": ([py, "tools/stage3_rect_editor.py", *argv], False),
        "boss-concepts": ([py, "tools/capture_boss_concepts.py", *argv], True),
        "dialogues":  ([py, "tools/capture_dialogues.py", *argv], True),
        "dummies":    ([py, "tools/gen_dummy_portraits.py", *argv], True),
        "pr-media":   ([py, "tools/pr_media.py", *argv], True),
        "pr-html":    ([py, "tools/pr_html.py", *argv], True),
        "pr-report":  ([py, "tools/pr_report.py", *argv], True),
        "pycompile":  ([py, "-m", "compileall", "-q", "src", "tools", "tests", *argv], True),
    }
    if cmd not in commands:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 2

    args, headless = commands[cmd]
    return subprocess.call(args, cwd=ROOT, env=_env(headless))


if __name__ == "__main__":
    raise SystemExit(main())
