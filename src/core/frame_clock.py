"""Frame-owned visual time; direct preview draws retain pygame's clock."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator

import pygame

_frame_seconds: ContextVar[float | None] = ContextVar("frame_seconds", default=None)


@contextmanager
def frame_time(seconds: float) -> Iterator[None]:
    token = _frame_seconds.set(seconds)
    try:
        yield
    finally:
        _frame_seconds.reset(token)


def ticks_ms() -> int:
    seconds = _frame_seconds.get()
    return pygame.time.get_ticks() if seconds is None else int(seconds * 1000)
