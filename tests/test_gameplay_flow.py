"""Regression tests for run boundaries, stopped combat and the first upgrade."""
import pygame
import pytest

from tools.headless import build_game_scene
from src.scenes.game_scene import GameScene
from src.scenes.gameover import GameOverScene
from src.scenes.game.config import UPGRADE_SLOTS, COMPANION_SLOTS
from src.story.script import BOSS_MID


@pytest.fixture(scope="module")
def game():
    game, _ = build_game_scene(1)
    yield game
    pygame.quit()


@pytest.fixture
def scene(game):
    game.start_new_run()
    game.input._pressed.clear()
    game.input.pre_update()
    game._next_scene = None
    scene = GameScene(game, stage_id=1)
    scene.on_enter()
    game._scene = scene
    return scene


def continue_run(game, stage):
    over = GameOverScene(game)
    over._stage = stage
    over._do_continue()
    scene = game._next_scene
    game._next_scene = None
    if scene is not None:
        scene.on_enter()
        game._scene = scene
    return scene


def test_stage_one_continue_consumes_lives_and_restores_stage_loadout(scene):
    game = scene.game
    game.shared.score, game.shared.kill_count = 1234, 12
    game.shared.stage_start_weapon["main_level"] = 2
    game.shared.stage_start_companion["lv_shot"] = 1
    for remaining in (2, 1, 0):
        resumed = continue_run(game, 1)
        assert game.shared.lives == remaining
        assert game.shared.score == 1234 and game.shared.kill_count == 12
        assert resumed.player.hp == resumed.player.max_hp
        assert resumed.player.weapon.main_level == 2
        assert resumed._companion.lv_shot == 1
    assert continue_run(game, 1) is None
    assert game.shared.lives == 0


def test_continue_rewinds_final_chapter_story_but_retry_starts_a_new_journey(scene):
    game = scene.game
    game.story.karonaru_available = False
    game.story.karonaru_lost = True
    game.story.blackhole_event_done = True
    final = GameScene(game, stage_id=4)
    final.on_enter()
    assert final._companion is None
    # The return event changes these flags midway through the final battle.
    game.story.karonaru_available = True
    game.story.karonaru_lost = False
    game.story.karonaru_max = True
    game.story.final_self_distanced = True
    resumed = continue_run(game, 4)
    assert resumed._companion is None
    assert game.story.karonaru_lost and not game.story.karonaru_max
    assert not game.story.final_self_distanced
    over = GameOverScene(game)
    over._do_retry()
    game._next_scene.on_enter()
    assert game.shared.lives == 3 and game.shared.score == 0
    assert game.story.karonaru_available and not game.story.karonaru_lost
    assert not game.story.blackhole_event_done
    assert game._next_scene._companion is not None


@pytest.mark.parametrize("suspension", ["pause", "upgrade", "cutin", "boss_intro", "final_gate"])
def test_suspended_combat_preserves_combo_heat_camera_and_pieces(scene, suspension):
    scene._combo_count, scene._combo_timer = 8, 0.1
    scene._pieces = ["歩"]
    scene._heat.heat = 60
    if suspension == "pause":
        scene._paused = True
    elif suspension == "upgrade":
        scene.player.weapon.weapon_stock = 1
        scene._open_upgrade_ui()
    elif suspension == "cutin":
        scene._start_combat_cutin(next(iter(BOSS_MID.values())))
    elif suspension == "boss_intro":
        scene._boss_intro_state = "boss_dialogue"
        scene._boss_intro_pages = list(next(iter(BOSS_MID.values())))
    else:
        scene._final._begin_input_gate("await_help")
    scene.game.input._just_pressed.add(scene.game.settings.get_key("bomb"))
    before = (scene.camera.x, scene._stage_elapsed)
    scene.update(0.2)
    assert scene._pieces == ["歩"]
    assert (scene._combo_count, scene._combo_timer) == (8, 0.1)
    assert scene._heat.heat == 60
    assert (scene.camera.x, scene._stage_elapsed) == before
    assert not scene._accepts_combat_input


def test_opening_pause_freezes_the_same_frame(scene):
    scene._combo_count, scene._combo_timer = 8, 0.1
    scene.game.input._just_pressed.add(scene.game.settings.get_key("pause"))
    scene.update(1.0)
    assert scene._paused and scene._combo_timer == 0.1


def test_first_authored_gate_teaches_both_upgrade_trees(scene):
    gate = min((e for e in scene.stage.world_events if e["type"] == "weapon_gate"),
               key=lambda e: e["x"])
    assert gate["x"] < 2000 and gate["hp"] <= 12
    scene.spawner.spawn_terrain_events([gate], scene.camera)
    terrain = next(t for t in scene.terrain if getattr(t, "fixed_drop", None) == "WeaponItem")
    scene._strike_terrain(terrain, gate["hp"], *terrain.rect.center, allow_damage=True)
    item = next(iter(scene.items))
    assert type(item).__name__ == "WeaponItem"
    scene._pickup_weapon_item()
    assert scene._upgrading
    assert scene.player.weapon.weapon_stock == scene._companion.stock == 1
    scene._upg_top_cursor = next(i for i, s in enumerate(UPGRADE_SLOTS) if s[0] == "weapon_main")
    scene._upg_bottom_cursor = next(i for i, s in enumerate(COMPANION_SLOTS) if s[0] == "kt_shot")
    for _ in range(3):
        scene._confirm_zone(scene._top_available_indices(), scene._bottom_available_indices())
    assert not scene._upgrading
    assert scene.player.weapon.main_level == 1 and scene._companion.lv_shot == 1
    assert scene.player.weapon.weapon_stock == scene._companion.stock == 0
    scene._pickup_weapon_item()
    assert not scene._upgrading  # Further pickups leave the choice to the player.


def test_popups_expire_instead_of_accumulating_invisibly(scene):
    scene._spawn_popup("expired", -20, -20, life=0.1)
    scene._spawn_popup("visible", 400, 300, life=1)
    scene._update_popups(0.2)
    assert [p[0] for p in scene._popups] == ["visible"]
    scene._update_popups(1)
    assert scene._popups == []
