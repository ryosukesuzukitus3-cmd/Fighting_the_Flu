"""A diagnostic policy must keep progressing when extra stock has no use."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from tools.agent_campaign import Campaign, _escape_distance
from tools.agent_playtest import Session
from src.scenes.game_scene import GameScene


@pytest.mark.parametrize("unused_player_stock", [0, 2])
def test_fully_upgraded_companion_stock_does_not_reopen_empty_upgrade_menu(
    tmp_path, unused_player_stock,
):
    session = Session(tmp_path / "campaign", seed=7, diagnostic=True)
    bot = None
    try:
        session.game.start_new_run()
        scene = GameScene(session.game, stage_id=1)
        session.game.change_scene(scene)
        session.command({"step": 1, "actions": []})
        # Test fixture only: reproduce both trees' caps and unused natural stock.
        weapon = scene.player.weapon
        weapon.main_level = 4
        weapon.speed_level = 5
        weapon.laser_level = 6
        weapon.homing_level = 7
        weapon.weapon_stock = unused_player_stock
        companion = scene._companion
        assert companion is not None
        companion.lv_hp = companion.lv_shot = companion.lv_supply = companion.lv_magnet = 3
        companion.stock = 3
        assert scene._top_available_indices() == scene._bottom_available_indices() == []

        bot = Campaign(session)
        before = scene._stage_elapsed
        for _ in range(3):
            actions = bot.decide()
            assert "weapon_select" not in actions
            bot.advance(actions)
            assert session.game._scene is scene and not scene._upgrading
        assert scene._stage_elapsed >= before + 0.5
        assert weapon.weapon_stock == unused_player_stock
        assert companion.stock == 3
    finally:
        if bot is not None:
            bot._trace.close()
        session.close()


def test_return_to_title_on_last_budgeted_batch_counts_as_complete(tmp_path, monkeypatch):
    from src.scenes.title import TitleScene

    session = Session(tmp_path / "final-return", seed=7, diagnostic=True)
    try:
        bot = Campaign(session, interval=12, max_frames=session.frame + 12)
        # A diagnostic fixture models the credits callback returning to title.
        bot.victory_reached = True
        session.game.change_scene(TitleScene(session.game))
        monkeypatch.setattr(bot, "decide", lambda: [])
        result = bot.run()
        assert result["frame"] == bot.max_frames
        assert result["victory_reached"] and result["completed"]
        assert result["reason"] == "completed campaign and returned to title"
    finally:
        session.close()


@pytest.mark.parametrize("danger,center,obstacles", [
    ((0, 310, 800, 286), (190, 540), ()),
    # Down would fit on screen but requires crossing the floor.
    ((0, 200, 800, 290), (190, 460), ((0, 505, 800, 95),)),
])
def test_broad_lower_beam_prefers_reachable_upper_exit(danger, center, obstacles):
    import pygame

    bounds = pygame.Rect(0, 0, 800, 600)
    hit = pygame.Rect(0, 0, 22, 28)
    hit.center = center
    beam = pygame.Rect(danger)
    walls = [pygame.Rect(rect) for rect in obstacles]
    costs = {direction: _escape_distance(hit.move(dx, dy), beam, bounds, walls)
             for direction, dx, dy in (("up", 0, -30), ("down", 0, 30),
                                       ("left", -30, 0), ("right", 30, 0))}
    assert min(costs, key=costs.get) == "up"


def test_beam_reaching_left_edge_cannot_be_escaped_through_screen_border():
    import pygame

    bounds = pygame.Rect(0, 0, 800, 600)
    beam = pygame.Rect(0, 200, 700, 160)
    hit = pygame.Rect(2, 266, 22, 28)
    stay = _escape_distance(hit, beam, bounds)
    up = _escape_distance(hit.move(0, -30), beam, bounds)
    down = _escape_distance(hit.move(0, 30), beam, bounds)
    # The two-pixel gap to the screen edge must not win over either exit.
    assert up == down < stay
    assert stay > hit.right


def test_small_bullet_still_allows_nearest_clear_exit_without_mutating_inputs():
    import pygame

    bounds = pygame.Rect(0, 0, 800, 600)
    hit = pygame.Rect(190, 250, 22, 28)
    bullet = pygame.Rect(206, 256, 12, 12)
    originals = (hit.copy(), bullet.copy(), bounds.copy())
    assert _escape_distance(hit.move(-12, 0), bullet, bounds) == 0
    assert 0 < _escape_distance(hit, bullet, bounds) < _escape_distance(hit.move(4, 0), bullet, bounds)
    assert (hit, bullet, bounds) == originals
