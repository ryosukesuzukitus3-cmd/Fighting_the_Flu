"""Opt-in GUI input assistance over stdin JSONL; the ordinary Game.run owns play.

Status is sampled before this frame's input events and update; captures contain
the last rendered frame. These can differ at a scene transition or key release.
This tool supplies explicit key presses only: it does not skip scenes or dialogue,
change game time, grant invincibility, or provide automated gameplay.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
from pathlib import Path
import queue
import re
import sys
import threading
import time
from collections.abc import Callable

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402
from src.managers.input import InputManager  # noqa: E402


class Controller:
    """Validate queued commands and inject key events on the game's main thread."""

    def __init__(self, *, emit: Callable[[dict], None], post_event=None,
                 get_status=None, capture=None) -> None:
        self._emit = emit
        self._post_event = post_event or pygame.event.post
        self._get_status = get_status or (lambda: {})
        self._capture = capture
        self._commands: queue.Queue[str | None] = queue.Queue()
        self._deadlines: dict[int, float] = {}
        self.closed = False

    def submit(self, line: str | None) -> None:
        """Thread-safe input; None means EOF and requests release followed by quit."""
        self._commands.put(line)

    def held_keys(self) -> list[str]:
        return sorted(pygame.key.name(key) for key in self._deadlines)

    @staticmethod
    def _keys(value) -> list[int]:
        if not isinstance(value, list) or not value:
            raise ValueError("keys must be a nonempty array of key names")
        keys = []
        for name in value:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("each key must be a nonempty string")
            name = name.strip().lower()
            code = pygame.key.key_code("return" if name == "enter" else name)
            if code == pygame.K_UNKNOWN:
                raise ValueError(f"unknown key: {name}")
            if code not in keys:
                keys.append(code)
        return keys

    @classmethod
    def _validate(cls, line: str) -> tuple[str, object]:
        command = json.loads(line)
        if not isinstance(command, dict):
            raise ValueError("command must be a JSON object")
        fields = set(command)
        if fields == {"press", "seconds"}:
            seconds = command["seconds"]
            if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                    or not math.isfinite(seconds) or not 0.05 <= seconds <= 5):
                raise ValueError("seconds must be finite and between 0.05 and 5")
            return "press", (cls._keys(command["press"]), float(seconds))
        if fields == {"release"}:
            return "release", cls._keys(command["release"])
        for name in ("release_all", "status", "quit"):
            if fields == {name} and command[name] is True:
                return name, None
        if fields == {"capture"}:
            label = command["capture"]
            if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", label):
                raise ValueError("capture must be an ASCII filename stem (1-64 letters, digits, _ or -)")
            if label.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}:
                raise ValueError("capture cannot use a reserved Windows filename")
            return "capture", label
        raise ValueError("use exactly one supported command; press also requires seconds")

    def _key_event(self, event_type: int, key: int) -> None:
        self._post_event(pygame.event.Event(event_type, key=key, mod=0, unicode=""))

    def _release(self, keys) -> None:
        for key in keys:
            if key in self._deadlines:
                self._key_event(pygame.KEYUP, key)
                del self._deadlines[key]

    def _quit(self) -> None:
        self._release(list(self._deadlines))
        self._post_event(pygame.event.Event(pygame.QUIT))
        self.closed = True

    def tick(self, now: float) -> None:
        """Expire held keys, then process at most one command per game frame.

        Keeping queued press/release commands in separate frames preserves taps.
        The reader thread never touches pygame or game state.
        """
        if self.closed:
            return
        self._release([key for key, deadline in self._deadlines.items() if now >= deadline])
        try:
            line = self._commands.get_nowait()
        except queue.Empty:
            return
        try:
            if line is None:
                self._quit()
                self._emit({"type": "ack", "command": "eof"})
                return
            name, value = self._validate(line)
            if name == "press":
                keys, seconds = value
                for key in keys:
                    if key not in self._deadlines:
                        self._key_event(pygame.KEYDOWN, key)
                    self._deadlines[key] = max(self._deadlines.get(key, now), now + seconds)
            elif name == "release":
                self._release(value)
            elif name == "release_all":
                self._release(list(self._deadlines))
            elif name == "quit":
                self._quit()
            elif name == "status":
                self._emit({"type": "status", **self._get_status(),
                            "held_keys": self.held_keys(), "observation": "before_input_events"})
                return
            elif name == "capture":
                if self._capture is None:
                    raise ValueError("capture is unavailable")
                path = self._capture(value)
                self._emit({"type": "ack", "command": name, "path": str(path),
                            "observation": "last_rendered_frame"})
                return
            self._emit({"type": "ack", "command": name, "held_keys": self.held_keys()})
        except (ValueError, TypeError, OverflowError, OSError, pygame.error) as exc:
            self._emit({"type": "error", "message": str(exc)})


class PlaytestInputManager(InputManager):
    def __init__(self, settings, controller: Controller) -> None:
        super().__init__(settings)
        self._controller = controller

    def pre_update(self) -> None:
        super().pre_update()
        self._controller.tick(time.monotonic())


def _read_commands(controller: Controller) -> None:
    try:
        for line in sys.stdin:
            controller.submit(line)
    finally:
        controller.submit(None)


def _status(game) -> dict:
    scene = game._scene
    result = {"scene": type(scene).__name__ if scene is not None else None,
              "focused": bool(pygame.key.get_focused())}
    player = getattr(scene, "player", None)
    if player is not None:
        result["player"] = {"x": player.sx, "y": player.sy, "hp": player.hp,
                            "fire_held": player.fire_held,
                            "laser_fire_held": player.laser_fire_held}
    for name in ("player_bullets", "enemy_bullets", "enemies"):
        group = getattr(scene, name, None)
        if group is not None:
            result[name] = len(group)
    return result


def main() -> None:
    # All protocol replies use the original stdout; ordinary game diagnostics go
    # to stderr so asset-loading messages cannot corrupt the JSONL response stream.
    output = sys.stdout

    def emit(message: dict) -> None:
        print(json.dumps(message, ensure_ascii=True, allow_nan=False), file=output, flush=True)

    with contextlib.redirect_stdout(sys.stderr):
        from src.core.game import Game

        game = Game()
        capture_dir = ROOT / "captures" / "playtest"

        def capture(label: str) -> Path:
            capture_dir.mkdir(parents=True, exist_ok=True)
            path = capture_dir / f"{label}.png"
            pygame.image.save(game.screen, str(path))
            return path

        controller = Controller(emit=emit, get_status=lambda: _status(game), capture=capture)
        game.input = PlaytestInputManager(game.settings, controller)
        threading.Thread(target=_read_commands, args=(controller,), daemon=True).start()
        emit({"type": "ready", "mode": "assisted_gui", "capture_dir": str(capture_dir),
              "observation": "status: before input events; capture: last rendered frame"})
        game.run()


if __name__ == "__main__":
    main()
