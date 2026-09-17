"""Regression coverage for missing-companion dialogue and the stage-three escape route."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pygame
import pytest

from src.entities.enemies.boss import Boss
from src.entities.enemies.boss_drone import MatchingZeroDrone
from src.entities.weapon import Weapon
from src.scenes.game_scene import GameScene
from src.story import script


@pytest.fixture
def dialogue_scene():
    scene = object.__new__(GameScene)
    scene.game = SimpleNamespace(
        story=SimpleNamespace(karonaru_available=True),
        shared=SimpleNamespace(boss_break_tutorial_shown=False), sound=Mock(),
    )
    scene._companion = SimpleNamespace(is_active=True)
    scene.player = SimpleNamespace(sx=120, sy=300)
    scene.particles, scene.camera = Mock(), Mock()
    scene._spawn_popup = Mock()
    scene._play_video_effect = Mock()
    scene._play_shogi_snap = Mock()
    scene._enqueue_boss_dialogue = Mock()
    scene._overheat_barked = False
    scene._boss_dialogue_timer = 0
    scene._hitstop_timer = scene._boss_break_flash_timer = 0
    scene._boss = SimpleNamespace(rect=pygame.Rect(520, 200, 100, 100))
    scene._boss_stage_id = lambda: 4
    return scene


@pytest.mark.parametrize("state", ["story_absent", "missing", "retired"])
def test_unavailable_companion_cannot_bark_but_break_still_teaches(dialogue_scene, state):
    scene = dialogue_scene
    if state == "story_absent":
        scene.game.story.karonaru_available = False
    elif state == "missing":
        scene._companion = None
    else:
        scene._companion.is_active = False

    scene._on_overheat_started()
    scene._enqueue_boss_dialogue.assert_not_called()
    assert not scene._overheat_barked
    scene._spawn_popup.assert_called_once()
    scene._on_boss_break()
    assert scene._enqueue_boss_dialogue.call_args.args[0] == script.BOSS_BREAK_TUTORIAL_SOLO
    assert all(line.speaker == script.SYS for line in scene._enqueue_boss_dialogue.call_args.args[0])
    scene._on_boss_break()
    assert scene._enqueue_boss_dialogue.call_count == 1


def test_active_companion_barks_once_and_explains_break(dialogue_scene):
    scene = dialogue_scene
    scene._on_overheat_started()
    scene._on_overheat_started()
    scene._enqueue_boss_dialogue.assert_called_once()
    assert scene._enqueue_boss_dialogue.call_args.args[0][0] in script.OVERHEAT_BARKS
    scene._on_boss_break()
    assert scene._enqueue_boss_dialogue.call_args.args[0] == script.BOSS_BREAK_TUTORIAL


@pytest.fixture
def fortress():
    surface = pygame.Surface((160, 160), pygame.SRCALPHA)
    surface.fill((100, 80, 60, 255))
    game = SimpleNamespace(resources=SimpleNamespace(image=lambda _: surface), sound=Mock())
    boss = Boss(game, 3)
    boss._state = "fight"
    boss.rect.center = (600, 300)
    group = pygame.sprite.Group()
    boss._summoned = [MatchingZeroDrone(game, boss, i) for i in range(3)]
    group.add(*boss._summoned)
    camera = SimpleNamespace(to_world_x=lambda x: x)
    return boss, group, camera


@pytest.mark.parametrize("lost_laser", [False, True])
def test_front_pair_opens_normal_shot_route_without_laser(fortress, lost_laser):
    boss, group, camera = fortress
    weapon = Weapon()
    if lost_laser:
        weapon.upgrade("laser")
        weapon.downgrade()
    assert not weapon.has_laser and weapon.weapon_stock == 0
    front_a, rear, front_b = boss._summoned
    hp = rear.hp
    assert not rear.take_damage(10000) and rear.hp == hp
    assert rear.blocks_projectile_damage(None)
    assert rear.rect.left > boss.rect.left

    assert front_a.take_damage(front_a.hp)
    front_a.kill()
    assert boss._summoned_alive() == 2
    assert boss.stance_ratio() == pytest.approx(2 / 3)
    assert len(boss._summoned) == 3
    boss._update_gimmick(0.01, "turrets", pygame.sprite.Group(), None)
    assert rear.requires_laser  # one front drone is not enough
    assert front_b.take_damage(front_b.hp)
    front_b.kill()
    boss._update_gimmick(0.01, "turrets", pygame.sprite.Group(), None)
    assert boss.rear_drone_exposed_just_now is rear
    assert not rear.requires_laser and not rear.blocks_projectile_damage(None)
    assert rear._base_image is rear._unshielded_image
    boss.rear_drone_exposed_just_now = None
    boss._update_gimmick(0.01, "turrets", pygame.sprite.Group(), None)
    assert boss.rear_drone_exposed_just_now is None  # no repeated message
    assert boss.suppresses_hit_feedback()  # the final drone must still be defeated

    rear.update(0.7, camera)
    assert rear.rect.right < boss.rect.left  # ordinary shots can physically reach it
    for _ in range(hp):
        killed = rear.take_damage(1)
    assert killed
    rear.kill()
    assert not group
    boss._update_gimmick(0.01, "turrets", pygame.sprite.Group(), None)
    assert boss._stun_timer > 0
    before = boss.hp
    boss.take_damage(10)
    assert boss.hp < before


def test_laser_can_destroy_rear_drone_before_the_front_pair(fortress):
    boss, _, _ = fortress
    front_a, rear, front_b = boss._summoned
    assert rear.take_laser_damage(rear.hp)
    rear.kill()
    boss._update_gimmick(0.01, "turrets", pygame.sprite.Group(), None)
    assert front_a.alive() and front_b.alive()
    assert boss.rear_drone_exposed_just_now is None


@pytest.mark.parametrize("stage_id,count", [(2, 2), (3, 3)])
def test_turret_wave_defeat_stuns_core_then_resummons_and_guards_again(fortress, stage_id, count):
    boss, group, _ = fortress
    group.empty()
    boss._stage_id = stage_id
    # Stage two normally uses weakpoint; cover the shared two-node turrets
    # branch as well as stage three's production three-node branch.
    boss._current_gimmick = lambda: "turrets"
    boss._summoned = []
    boss._summon_cd = 0

    def summon(amount):
        wave = [pygame.sprite.Sprite() for _ in range(amount)]
        group.add(*wave)
        return wave

    boss.summon_turret_fn = Mock(side_effect=summon)
    bullets = pygame.sprite.Group()
    boss._update_gimmick(0.01, "turrets", bullets, None)
    assert len(boss._summoned) == count
    before = boss.hp
    boss.take_damage(5)
    assert boss.hp == before

    for node in list(group):
        node.kill()
    # A draw/hit query can happen before the next update. It must not erase
    # the wave, otherwise the next update cannot enter the stun state.
    assert not boss.suppresses_hit_feedback()
    assert boss.stance_ratio() == 0
    assert len(boss._summoned) == count
    boss._update_gimmick(0.01, "turrets", bullets, None)
    assert boss._stun_timer > 0 and not boss._summoned
    boss.take_damage(5)
    assert boss.hp < before

    boss._update_gimmick(boss._stun_timer + 0.01, "turrets", bullets, None)
    boss._update_gimmick(boss._summon_cd + 0.01, "turrets", bullets, None)
    assert boss.summon_turret_fn.call_count == 2
    assert len(group) == count and boss._summoned_alive() == count
    assert boss.stance_ratio() == 1
    before = boss.hp
    boss.take_damage(5)
    assert boss.hp == before


def test_release_feedback_is_visible_without_an_active_companion(dialogue_scene, fortress):
    scene = dialogue_scene
    boss, _, _ = fortress
    scene._companion = None
    scene.game.story.karonaru_available = False
    scene._on_rear_drone_exposed(boss._summoned[1])
    scene.particles.spawn_spark.assert_called_once()
    assert "盾解除" in scene._spawn_popup.call_args.args[0]
    assert scene._enqueue_boss_dialogue.call_args.args[0] == script.SAKURA_SHIELD_RELEASED
    assert all(line.speaker == script.SYS for line in script.SAKURA_SHIELD_RELEASED)


def test_changed_story_is_verbatim_in_review_document():
    document = (Path(__file__).resolve().parents[1] / "docs" / "story.md").read_text("utf-8")
    pages = [*script.PROLOGUE, *script.BOSS_INTRO[3], *script.FINAL_SEQ["return"],
             *script.BOSS_BREAK_TUTORIAL_SOLO, *script.SAKURA_SHIELD_RELEASED]
    for page in pages:
        for line in page.lines:
            assert line in document
