from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.scenes.credits_roll import CreditsRollScene, _FAST_MULT, _SCROLL_SPEED
from src.scenes.cutscene_scene import CutsceneScene
from src.scenes.disclaimer_scene import DisclaimerScene
from src.story.lines import page


class _ActionInput:
    def __init__(self, *, pressed: set[str] | None = None) -> None:
        self.pressed = pressed or set()

    def is_action_pressed(self, action: str) -> bool:
        return action in self.pressed

    def is_action_just_pressed(self, action: str) -> bool:
        return action in self.pressed

    def is_action_held_with_repeat(self, action: str, **_kwargs) -> bool:
        return action in self.pressed

    def is_just_pressed(self, _key: int) -> bool:
        return False


class _Sound:
    def play_se_alias(self, *_args, **_kwargs) -> None:
        pass


@pytest.mark.parametrize("action", ["ui_accept", "ui_back"])
def test_disclaimer_can_be_skipped_by_configurable_ui_action(action: str) -> None:
    game = SimpleNamespace(input=_ActionInput(pressed={action}))
    scene = DisclaimerScene(game)
    scene._timer = 0.0
    scene._leave_t = -1.0

    scene.update(0.01)

    assert scene._leave_t >= 0.0


def test_cutscene_advance_uses_ui_accept_action() -> None:
    game = SimpleNamespace(
        input=_ActionInput(pressed={"ui_accept"}),
        sound=_Sound(),
    )
    scene = CutsceneScene(game, [page("narration", "test")], lambda: None)
    scene._page = 0
    scene._chars = 0.0
    scene._blink = 0.0
    scene._fx_time = 0.0
    scene._shake_t = 0.0
    scene._flash_t = 0.0
    scene._glitch_t = 0.0
    scene._fade_in_t = 0.0
    scene._fade_out_active = False
    scene._fade_out_t = 0.0
    scene._finished = False
    scene._type_se_cooldown = 0.0

    scene.update(0.01)

    assert scene._is_complete()


def test_credits_fast_forward_uses_ui_accept_action() -> None:
    game = SimpleNamespace(input=_ActionInput(pressed={"ui_accept"}))
    scene = CreditsRollScene(game, [], lambda: None)
    scene._timer = 0.0
    scene._finished = False
    scene._completed = False
    scene._scroll_y = 100.0
    scene._final_prefix_h = 0.0
    scene._hold_timer = 0.0

    scene.update(1.0)

    assert scene._scroll_y == pytest.approx(100.0 - _SCROLL_SPEED * _FAST_MULT)
