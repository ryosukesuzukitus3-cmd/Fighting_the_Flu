"""Optional local consistency check; no automatic hook registration is required.

Run from any directory using this worktree's script path. The default only
checks generated documentation. Use --write to regenerate it explicitly, or
--changed-only to skip checks when no watched working-tree paths changed.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

PROJECT_DIR = Path(__file__).resolve().parents[2]
_WATCH_PATHS = [
    "src", "data", "assets", "tools", "docs", "tests", ".github",
    ".codex", ".claude", "AGENTS.md", "CLAUDE.md", "main.py",
    "game.spec", "pyproject.toml",
]


def _project_python() -> str:
    relative = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    candidate = PROJECT_DIR / ".venv" / Path(*relative)
    return str(candidate) if candidate.is_file() else sys.executable


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("SDL_VIDEODRIVER", "dummy")
    env.setdefault("SDL_AUDIODRIVER", "dummy")
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=PROJECT_DIR, env=env,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())


def _has_changes() -> bool:
    result = _run(["git", "status", "--porcelain", "--", *_WATCH_PATHS])
    if result.returncode != 0:
        raise RuntimeError(f"git status failed ({result.returncode}):\n{_output(result)}")
    return bool(result.stdout.strip())


def _commands(write: bool) -> list[tuple[str, list[str]]]:
    py = _project_python()
    runner = str(PROJECT_DIR / "tools" / "run.py")
    return [
        ("docs", [py, runner, "docs" if write else "docs-check"]),
        ("consistency", [py, runner, "check"]),
    ]


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Regenerate docs before checking")
    parser.add_argument("--changed-only", action="store_true", help="Skip an unchanged working tree")
    args = parser.parse_args(argv)
    try:
        changed = _has_changes()
        if args.changed_only and not changed:
            return 0
        errors = []
        for label, cmd in _commands(args.write):
            result = _run(cmd)
            if result.returncode != 0:
                errors.append(f"{label} failed ({result.returncode}):\n{_output(result)}")
            elif result.stdout.strip():
                print(result.stdout.strip())
        if errors:
            raise RuntimeError("\n".join(errors))
    except (OSError, RuntimeError) as exc:
        print(f"[check_sync] {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
