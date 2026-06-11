"""Shared development-environment helpers.

Use this from tools and tests that need stable UTF-8 output, headless pygame,
or a quick guard against mojibake accidentally entering text files.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".toml", ".txt", ".yml", ".yaml", ".ini", ".cfg",
}
SKIP_DIRS = {
    ".git", ".venv", ".uv-cache", ".pytest_cache", ".html", "__pycache__", "assets",
}
MOJIBAKE_MARKERS = tuple(chr(cp) for cp in (
    0x7E67, 0x90E2, 0x90B5, 0x96A8, 0x7B0F, 0x873F, 0x879F, 0x8B5B,
    0x7E3A, 0x9AEF, 0x9672, 0x86DF, 0x96B4, 0x9677, 0x2181,
))


def configure_utf8_stdio() -> None:
    """Prefer UTF-8 for Python tool output on Windows shells."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def configure_headless_pygame() -> None:
    """Make pygame imports safe in non-GUI checks."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def iter_project_text_files(root: Path = ROOT):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def text_integrity_issues(root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    for path in iter_project_text_files(root):
        rel = path.relative_to(root)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            issues.append(f"{rel}: not valid UTF-8 ({exc})")
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            marker = next((m for m in MOJIBAKE_MARKERS if m in line), None)
            if marker is not None:
                issues.append(f"{rel}:{lineno}: mojibake marker {marker!r}")
    return issues
