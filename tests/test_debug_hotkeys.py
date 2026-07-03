from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
pygame.init()

from src.core.debug import requested_stage_warp  # noqa: E402
from src.entities.weapon import Weapon  # noqa: E402
from src.managers.input import InputManager  # noqa: E402
from src.scenes.game.debug_mixin import DEBUG_FAST_FORWARD_SCALE, GameSceneDebugMixin  # noqa: E402


class _DebugHarness(GameSceneDebugMixin):
    pass


def _input_with(*, pressed=(), just_pressed=()) -> InputManager:
    inp = InputManager()
    inp._pressed.update(pressed)
    inp._just_pressed.update(just_pressed)
    return inp


def test_ctrl_number_requests_stage_warp() -> None:
    game = SimpleNamespace(input=_input_with(
        pressed=(pygame.K_LCTRL,),
        just_pressed=(pygame.K_2,),
    ))

    assert requested_stage_warp(game) == 2


def test_stage_warp_requires_ctrl() -> None:
    game = SimpleNamespace(input=_input_with(just_pressed=(pygame.K_2,)))

    assert requested_stage_warp(game) is None


def test_debug_fast_forward_scales_delta_time() -> None:
    obj = _DebugHarness()
    obj.game = SimpleNamespace(input=_input_with(pressed=(pygame.K_F4,)))

    assert obj._debug_apply_time_scale(0.5) == 0.5 * DEBUG_FAST_FORWARD_SCALE
    assert obj._debug_time_scale == DEBUG_FAST_FORWARD_SCALE


def test_debug_handle_input_maxes_weapon_on_f7() -> None:
    obj = _DebugHarness()
    obj.game = SimpleNamespace(input=_input_with(just_pressed=(pygame.K_F7,)))
    obj.player = SimpleNamespace(weapon=Weapon())

    assert obj._debug_handle_input() is False

    w = obj.player.weapon
    assert w.main_at_max
    assert w.speed_at_max
    assert w.laser_level == 6
    assert w.homing_level == 7
    assert w.magnet_level == 3
    assert w.has_barrier
