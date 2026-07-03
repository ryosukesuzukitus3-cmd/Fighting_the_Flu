from __future__ import annotations

from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from src.core.game import Game


_STAGE_KEYS = (
    pygame.K_1,
    pygame.K_2,
    pygame.K_3,
    pygame.K_4,
    pygame.K_5,
    pygame.K_6,
    pygame.K_7,
    pygame.K_8,
    pygame.K_9,
)


def _ctrl_pressed(game: Game) -> bool:
    inp = game.input
    return inp.is_pressed(pygame.K_LCTRL) or inp.is_pressed(pygame.K_RCTRL)


def requested_stage_warp(game: Game) -> int | None:
    """Return the stage selected by Ctrl+number debug input, if any."""
    if not _ctrl_pressed(game):
        return None

    from src.core.registries import stage_ids

    for stage_id, key in zip(stage_ids(), _STAGE_KEYS):
        if game.input.is_just_pressed(key):
            return stage_id
    return None


def warp_to_stage(game: Game, stage_id: int) -> None:
    from src.scenes.game_scene import GameScene

    print(f"[DEBUG] Warp to Stage {stage_id}")
    game.change_scene(GameScene(game, stage_id=stage_id))


def handle_global_debug_input(game: Game) -> bool:
    stage_id = requested_stage_warp(game)
    if stage_id is None:
        return False
    warp_to_stage(game, stage_id)
    return True
