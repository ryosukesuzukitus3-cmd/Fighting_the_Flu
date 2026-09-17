"""A diagnostic policy must keep progressing when extra stock has no use."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from tools.agent_campaign import Campaign, _escape_distance, _swept_intersects
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


@pytest.mark.parametrize("hit,bullet,end,bullet_end,expected", [
    ((1, 384, 21, 28), (30, 384, 10, 10), (14, 397), (20, 384), True),
    ((79, 387, 21, 28), (190, 396, 10, 10), (157, 387), (144, 396), True),
    # Co-moving rectangles and mere edge contact must stay non-colliding.
    ((0, 0, 10, 10), (10, 0, 10, 10), (20, 0), (30, 0), False),
    ((0, 0, 10, 10), (5, 0, 10, 10), (20, 0), (25, 0), True),
    ((0, 0, 10, 10), (20, 0, 10, 10), (10, 0), (20, 0), False),
])
def test_swept_relative_motion_catches_between_sample_crossings(
    hit, bullet, end, bullet_end, expected,
):
    import pygame

    start = pygame.Rect(hit)
    other = pygame.Rect(bullet)
    finish = start.copy()
    finish.topleft = end
    other_finish = other.copy()
    other_finish.topleft = bullet_end
    assert _swept_intersects(start, finish, other, other_finish) is expected


def _movement_fixture(bullet, *, bounced=False, terrain=()):
    import pygame
    from types import SimpleNamespace

    class FixturePlayer:
        rect = pygame.Rect(0, 383, 23, 31)
        hp = 100
        weapon = SimpleNamespace(speed_multiplier=1.4)

        @property
        def hit_rect(self):
            return self.rect.inflate(-2, -3)

    attack = SimpleNamespace(rect=pygame.Rect(bullet), vx=-215, vy=0,
                             warning_only=False, _terrain_bounced=bounced)
    scene = SimpleNamespace(player=FixturePlayer(), camera=SimpleNamespace(scroll_speed=0),
                            enemies=[], items=[], terrain=terrain, enemy_bullets=[attack])
    bot = Campaign.__new__(Campaign)
    bot.session = SimpleNamespace(frame=0)
    bot.interval = 12
    bot._previous_position = {}
    bot._last_plan_frame = None
    return bot, scene, attack


def test_movement_avoids_the_actual_second_frame_bullet_crossing():
    import math
    import pygame

    bot, scene, attack = _movement_fixture((30, 384, 10, 10))
    actions, _ = bot.movement(scene)
    # Check the selected input against actual 60 FPS movement, including the
    # game's diagonal wall correction; this used to select right + down and hit.
    sx, sy = 0.0, 383.0
    dx = int("move_right" in actions) - int("move_left" in actions)
    dy = int("move_down" in actions) - int("move_up" in actions)
    for frame in range(1, 13):
        ax, ay = dx, dy
        if ax and ay:
            ax *= math.sqrt(0.5)
            ay *= math.sqrt(0.5)
        nx = max(0, min(777, sx + ax * 392 / 60))
        ny = max(0, min(569, sy + ay * 392 / 60))
        if ax and ay:
            if nx == sx:
                ny = max(0, min(569, sy + math.copysign(392 / 60, ay)))
            elif ny == sy:
                nx = max(0, min(777, sx + math.copysign(392 / 60, ax)))
        sx, sy = nx, ny
        hit = pygame.Rect(int(sx), int(sy), 23, 31).inflate(-2, -3)
        bullet = attack.rect.move(int(attack.vx * frame / 60), 0)
        assert not hit.colliderect(bullet), (actions, frame)
    assert "move_down" in actions


def test_reflected_harmless_bullet_is_not_an_avoidance_target():
    bot, scene, attack = _movement_fixture((30, 384, 10, 10), bounced=True)
    actions, attacks = bot.movement(scene)
    scene.enemy_bullets = []
    empty_bot, _, _ = _movement_fixture((30, 384, 10, 10))
    assert attacks == []
    assert actions == empty_bot.movement(scene)[0]


def test_movement_does_not_cross_solid_floor_to_escape_a_beam():
    import pygame
    from types import SimpleNamespace

    floor = SimpleNamespace(rect=pygame.Rect(0, 530, 800, 70))
    bot, scene, attack = _movement_fixture((0, 290, 800, 286), terrain=[floor])
    scene.player.rect.topleft = (189, 474)
    attack.vx = 0
    attack.warning_only = True
    actions, _ = bot.movement(scene)
    assert "move_down" not in actions
    assert "move_up" in actions



def test_damage_evidence_keeps_previous_positions_after_bullet_disappears(tmp_path):
    from src.entities.bullets.enemy_bullet import EnemyBullet

    session = Session(tmp_path / "damage-evidence", seed=7, diagnostic=True)
    bot = None
    try:
        session.game.start_new_run()
        scene = GameScene(session.game, stage_id=1)
        session.game.change_scene(scene)
        session.command({"step": 1, "actions": []})
        attack = EnemyBullet(600, 300, -215, 0)
        attack._terrain_bounced = True
        scene.enemy_bullets.add(attack)
        bot = Campaign(session)
        before = session.command({"step": 1, "actions": []})
        bot.note(before)
        previous_rect = list(attack.rect)
        previous_player = list(scene.player.rect)
        # Test-only damage fixture: the collision would consume the source
        # bullet before the next observation can record it.
        attack.kill()
        attack.rect.move_ip(500, 500)
        scene.player.take_damage(10)
        bot.note(session.command({"step": 1, "actions": []}))
        event = bot.damage[-1]
        assert event["previous_frame"] == before["frame"]
        assert event["previous_player_rect"] == previous_player
        assert event["previous_attacks"] == [{
            "kind": "EnemyBullet", "rect": previous_rect, "vx": -215, "vy": 0,
            "damage": 10, "warning": False, "terrain_bounced": True,
        }]
        assert event["nearby_attacks"] == []
        bot.note(session.command({"step": 1, "actions": []}))
        assert event["previous_attacks"][0]["rect"] == previous_rect
    finally:
        if bot is not None:
            bot._trace.close()
        session.close()
