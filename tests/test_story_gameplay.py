"""Behavioral coverage for the final story's player actions and closing dialogue."""
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pygame
import pytest

from src.core.registries import stage_ids
from src.managers.input import InputManager
from src.scenes.game.config import POST_BOSS_FINAL_TIMEOUT
from src.scenes.game.final_battle import FinalBattleDirector
from src.scenes.game.post_boss_mixin import GameScenePostBossMixin
from src.story.script import BOSS_DEFEAT, FINAL_SEQ, PROLOGUE, _BRIEF_STAGE1


@pytest.fixture
def scene(monkeypatch):
    # Use real input edges and a non-default fire binding without a GUI/device.
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: defaultdict(bool))
    settings = SimpleNamespace(get_key=lambda action: {
        "fire": pygame.K_c, "ui_accept": pygame.K_RETURN,
    }[action])
    game = SimpleNamespace(
        input=InputManager(settings), settings=settings, sound=Mock(),
        playlog=Mock(), story=SimpleNamespace(), shared=SimpleNamespace(),
        change_scene=Mock(),
    )
    player = SimpleNamespace(
        hp=1, max_hp=5, _invincible_timer=0.0, weapon=Mock(),
        rect=pygame.Rect(100, 200, 32, 32),
    )
    result = GameScenePostBossMixin()
    result.game, result.player = game, player
    result._boss = Mock(sx=600, sy=250)
    result._companion = Mock(sx=80, sy=210)
    result.particles, result.camera = Mock(), Mock()
    result._spawn_popup = Mock()
    result.player_bullets = pygame.sprite.Group()
    result.enemy_bullets = pygame.sprite.Group()
    result.laser = SimpleNamespace(state="firing")
    result._stage_id = stage_ids()[-1]
    result._stage_elapsed = 10.0
    result._post_boss_timer = result._hint_blink = 0.0
    return result


def key_frame(scene, event_type=None, key=pygame.K_c):
    inp = scene.game.input
    inp.pre_update()
    if event_type is not None:
        inp.handle_event(pygame.event.Event(event_type, key=key))
    inp.update(1 / 60)


def test_return_waits_for_player_to_release_and_ask_for_help(scene):
    director = FinalBattleDirector(scene)
    director._karonaru_return_from = (40, 210)
    director._karonaru_return_to = (80, 210)
    key_frame(scene, pygame.KEYDOWN)
    director.update_return_join(2.0)
    assert director.input_gate_active
    assert scene.player.hp == 1
    scene._companion.set_max.assert_not_called()

    # Holding the combat key, or simply waiting, cannot ask for help.
    for _ in range(5):
        director.update_timers(60)
        director.update_input_gate()
    assert director.seq == "await_help"
    assert scene.player.hp == 1
    key_frame(scene, pygame.KEYUP)
    director.update_input_gate()
    key_frame(scene, pygame.KEYDOWN, pygame.K_RETURN)
    director.update_input_gate()
    assert director.input_gate_active  # dialogue advance is a separate action

    key_frame(scene, pygame.KEYDOWN)
    director.update_input_gate()
    assert not director.input_gate_active
    assert director.dialogue_active
    assert director.phase == 2
    assert scene.player.hp == scene.player.max_hp
    scene._companion.set_max.assert_called_once()
    assert director._final_dialogue_pages == FINAL_SEQ["act2_start"]

    for _ in FINAL_SEQ["act2_start"]:
        key_frame(scene, pygame.KEYUP, pygame.K_RETURN)
        key_frame(scene, pygame.KEYDOWN, pygame.K_RETURN)
        director.update_dialogue()
    assert not director.dialogue_active
    assert director.seq == ""
    assert not director.consume_final_shot_request()


def test_final_signal_clears_old_attacks_and_requires_a_fresh_player_shot(scene):
    director = FinalBattleDirector(scene)
    old_player, old_enemy = pygame.sprite.Sprite(), pygame.sprite.Sprite()
    scene.player_bullets.add(old_player)
    scene.enemy_bullets.add(old_enemy)
    key_frame(scene, pygame.KEYDOWN)
    director._play_final_dialogue(FINAL_SEQ["final_sengen"], director._arm_final_kill)
    for _ in FINAL_SEQ["final_sengen"]:
        key_frame(scene, pygame.KEYUP, pygame.K_RETURN)
        key_frame(scene, pygame.KEYDOWN, pygame.K_RETURN)
        director.update_dialogue()
    assert director.input_gate_active
    assert not director.final_strike_active
    assert not scene.player_bullets and not scene.enemy_bullets
    assert scene.laser.state == "ready"
    scene._boss.arm_final_kill.assert_not_called()
    director.update_input_gate()
    assert not director.consume_final_shot_request()

    key_frame(scene, pygame.KEYUP)
    director.update_input_gate()
    key_frame(scene, pygame.KEYDOWN)
    # A short tap may arrive as down/up within one frame after the release.
    scene.game.input.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_c))
    director.update_input_gate()
    assert director.final_strike_active
    scene._boss.arm_final_kill.assert_called_once()
    assert director.consume_final_shot_request()
    assert not director.consume_final_shot_request()
    assert not director.allows_final_hit(old_player)
    assert not director.allows_final_hit(SimpleNamespace())  # companion/bomb
    assert not director.allows_final_hit()  # existing laser path

    first, retry = SimpleNamespace(), SimpleNamespace()
    director.mark_final_shot([first])
    director.mark_final_shot([retry])
    assert director.allows_final_hit(first)
    assert director.allows_final_hit(retry)  # a missed shot cannot softlock


def test_final_defeat_plays_every_line_before_entering_epilogue(scene, monkeypatch):
    from src.scenes import epilogue_scene

    epilogue = object()
    monkeypatch.setattr(epilogue_scene, "EpilogueScene", lambda game: epilogue)
    scene._on_boss_killed()
    assert scene._defeat_dialogue_pages == BOSS_DEFEAT[scene._stage_id]
    assert not scene._defeat_dialogue_active
    scene._update_post_boss_phase(0.6)
    scene.game.change_scene.assert_not_called()
    scene._update_post_boss_phase(0.7)
    assert scene._defeat_dialogue_active

    heard = []
    for line in BOSS_DEFEAT[scene._stage_id]:
        key_frame(scene, pygame.KEYUP, pygame.K_RETURN)
        scene._update_post_boss_phase(120)
        assert scene._defeat_dialogue_active
        assert scene._defeat_dialogue_pages[scene._defeat_dialogue_index] == line
        heard.append(line)
        scene.game.change_scene.assert_not_called()
        key_frame(scene, pygame.KEYDOWN, pygame.K_RETURN)
        scene._update_post_boss_phase(1 / 60)

    assert not scene._defeat_dialogue_active
    assert sum("すぐ変われないことと、聞かないことは、別だ。" in line.lines
               for line in heard) == 1
    assert scene._post_boss_timer == 0
    scene.game.change_scene.assert_not_called()
    scene._update_post_boss_phase(POST_BOSS_FINAL_TIMEOUT)
    scene.game.change_scene.assert_called_once_with(epilogue)


def test_edited_story_sections_remain_verbatim_in_the_canonical_script():
    document = (Path(__file__).resolve().parents[1] / "docs" / "story.md").read_text("utf-8")
    for page in [*PROLOGUE, *_BRIEF_STAGE1, *(line for seq in FINAL_SEQ.values() for line in seq)]:
        for text in page.lines:
            assert text in document


def test_game_scene_final_shot_bypasses_heat_and_rejects_companion_hits(monkeypatch):
    from tools.headless import build_game_scene
    from src.entities.companion import Karonaru
    from src.entities.enemies.boss import Boss
    from src.entities.bullets.player_bullet import KaronaruMaxBullet, NormalBullet

    game, actual = build_game_scene(stage_ids()[-1])
    try:
        monkeypatch.setattr(pygame.key, "get_pressed", lambda: defaultdict(bool))
        game.settings._data["key_bindings"]["fire"] = "K_c"
        game.input = InputManager(game.settings)
        actual.terrain.empty()
        actual.items.empty()
        actual.enemies.empty()
        actual.camera.scroll_speed = 0
        actual._stage_banner_timer = actual._bgm_delay = 0
        actual.player._entering = False
        actual.player.sx = 120
        actual.player.rect.topleft = (int(actual.player.sx), int(actual.player.sy))
        actual._companion = Karonaru(game)
        actual._companion.set_max()
        boss = actual._boss = Boss(game, stage_id=actual._stage_id)
        boss._transform_form2()
        boss._transform_form3()
        boss.begin_act2(240)
        boss._state = "fight"
        boss.sx, boss.sy = 650, 250
        boss.rect.center = (650, 250)
        actual._boss_intro_state = "fighting"
        actual._final._final_phase = 2
        actual._final._arm_final_kill()
        actual._heat.add(10000)
        actual.player._cooldown = 10

        key_frame(actual)
        actual.update(1 / 60)
        key_frame(actual, pygame.KEYDOWN)
        actual.update(1 / 60)
        assert actual._final.final_strike_active
        key_frame(actual, pygame.KEYUP)  # the intent persists after a brief press
        actual.update(1 / 60)
        assert actual._heat.overheated
        assert actual.player_bullets
        assert all(actual._final.allows_final_hit(b) for b in actual.player_bullets)
        assert actual.laser.state == "ready"

        # Miss the initial shot, then retry while heat is still locked.
        actual.player_bullets.empty()
        actual.player._cooldown = 0
        key_frame(actual, pygame.KEYDOWN)
        actual.update(1 / 60)
        retry = next(iter(actual.player_bullets))
        assert actual._final.allows_final_hit(retry)
        actual.player_bullets.empty()
        companion = KaronaruMaxBullet(*boss.rect.center)
        stale = NormalBullet(*boss.rect.center)
        actual.player_bullets.add(companion, stale)
        actual._process_collisions()
        assert actual._boss is boss and boss.hp == 1
        assert not actual._post_boss

        retry.rect.center = boss.rect.center
        actual.player_bullets.add(retry)
        actual._process_collisions()
        assert actual._post_boss
        assert actual._defeat_dialogue_pages == BOSS_DEFEAT[actual._stage_id]
    finally:
        pygame.quit()
