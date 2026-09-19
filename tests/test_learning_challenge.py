"""Progression limits and real restart boundaries for learnable challenges."""
import json
from pathlib import Path
import pygame
import pytest
from tools.headless import build_game_scene
from src.scenes.game_scene import GameScene
from src.scenes.gameover import GameOverScene
from src.core.balance import SUPPLY_BUDGET
from src.scenes.game.learning_mixin import LearningEncounter, terrain_key


@pytest.fixture
def scene(tmp_path, monkeypatch):
    monkeypatch.setenv('FLU_USER_DATA_DIR', str(tmp_path))
    game, first = build_game_scene(1)
    game.start_new_run()
    first = GameScene(game,1)
    game._scene=first
    first.on_enter()
    try:
        yield first
    finally:
        game.close()


def resume(scene):
    game=scene.game
    game._next_scene=None
    over=GameOverScene(game)
    over.on_enter()
    over._do_continue()
    new=game._next_scene
    game._scene=new
    game._next_scene=None
    new.on_enter()
    return new


def test_authored_rewards_have_a_finite_budget_and_never_depend_on_random_drops():
    root=Path(__file__).resolve().parents[1]
    totals=[]
    for sid in range(1,5):
        data=json.loads((root/f'data/stages/stage{sid}.json').read_text(encoding='utf-8'))
        rewards=sum(e.get('count',1) for e in data['world_events'] if e.get('fixed_drop')=='WeaponItem')
        totals.append(rewards)
    assert totals==[3,2,2,3]
    assert sum(totals)+3==13


def test_early_choices_include_speed_and_both_addon_weapons(scene):
    scene.player.weapon.weapon_stock=1
    assert all(scene._is_upgrade_available(k) for k in ('speed','laser','homing','weapon_main'))
    scene._pickup_weapon_item()
    assert scene._companion.stock==0
    scene._pickup_weapon_item()
    assert scene._companion.stock==1


def test_explicit_empty_gate_reward_does_not_turn_back_into_weapon(scene):
    scene.spawner.spawn_terrain_events([dict(type='weapon_gate',x=100,y=180,w=50,h=50,fixed_drop=None)],scene.camera)
    gate=list(scene.terrain)[-1]
    assert gate.fixed_drop is None


def test_supply_budget_cannot_be_refilled_by_waiting_or_upgrading(scene):
    c=scene._companion
    sent=[]
    c._spawn_heal_fn=sent.append
    c.apply_upgrade('kt_supply')
    for _ in range(100):
        c._tick_supply(10)
    assert sum(sent)==SUPPLY_BUDGET[1]
    c.apply_upgrade('kt_supply')
    for _ in range(100):
        c._tick_supply(10)
    assert sum(sent)==SUPPLY_BUDGET[2]
    c.refill_supply()
    for _ in range(100):
        c._tick_supply(10)
    assert sum(sent)==2*SUPPLY_BUDGET[2]


def test_road_retry_restores_loadout_score_and_destroyed_terrain_without_limit(scene):
    scene.camera.x=scene.stage.learning['checkpoint_x']
    scene.spawner._spawn_due_world_events(scene.camera)
    scene.enemies.empty()
    scene.terrain.update(0,scene.camera)
    breakable=next(t for t in scene.terrain if getattr(t,'destructible',False))
    removed=terrain_key(breakable)
    breakable.kill()
    scene._learning_rest_done=True
    scene._safe_restart_position()
    scene.player.weapon.upgrade('speed')
    scene.player.weapon.weapon_stock=2
    scene.game.shared.score=400
    scene.game.shared.support_pickups=2
    scene._save_checkpoint('road','test rest')
    for _ in range(5):
        scene.player.weapon.upgrade('laser')
        scene._pickup_weapon_item()
        scene.game.shared.score+=999
        scene=resume(scene)
        assert scene.player.hp==100
        assert scene.player.weapon.laser_level==0
        assert scene.player.weapon.speed_level==1
        assert scene.player.weapon.weapon_stock==2
        assert scene.game.shared.score==400 and scene.game.shared.support_pickups==2
        assert removed not in {terrain_key(t) for t in scene.terrain}
        assert scene._learning_rest_done and not scene._learning_done
        assert not scene.player._entering


@pytest.mark.parametrize('sid,kind',[(1,'boss'),(2,'boss'),(3,'boss'),(4,'boss'),(4,'final'),(4,'final_pair')])
def test_boss_retry_reaches_fight_without_replaying_previous_sections(scene,sid,kind):
    game=scene.game
    game.story.karonaru_available=sid<4 or kind=='final_pair'
    scene=GameScene(game,sid)
    game._scene=scene
    scene.on_enter()
    boss_event=next(e for e in scene.stage.world_events if e['type']=='Boss')
    scene.camera.x=boss_event['x']-800
    scene.spawner.spawn_terrain_events(scene.stage.world_events,scene.camera)
    scene.spawner.skip_all_events()
    scene._prepare_boss_terrain(sid)
    scene.terrain.update(0,scene.camera)
    scene._safe_restart_position()
    scene._learning_done=True
    scene.player.weapon.upgrade('laser')
    scene._save_checkpoint(kind,'boss')
    scene=resume(scene)
    assert scene._boss_intro_state=='fight_banner' and scene._boss_intro_timer <= 1
    assert scene._boss._state=='fight' and scene._boss.hp==scene._boss.max_hp
    assert scene.camera.scroll_speed==0 and scene.player.weapon.laser_level==1
    assert scene._learning_done and not scene._final.dialogue_active
    if kind=='final':
        assert scene._boss._form3 and scene._final.phase==1
        assert scene._companion is None
    if kind=='final_pair':
        assert scene._boss._form3 and scene._boss._form3_act==2
        assert scene._final.phase==2 and scene._companion.mode=='max'


def test_encounter_does_not_end_by_waiting_and_dead_emitter_stops_its_attacks(scene):
    encounter=LearningEncounter(scene,scene.stage.learning)
    for _ in range(60):
        encounter.update(.2)
    assert not encounter.complete and encounter.wave==0
    encounter.attack("warn", 0)
    warning = encounter.warning_sprites[0]
    encounter.emitters[0].kill()
    encounter.update(1/60)
    assert not warning.alive() and 0 not in encounter.pending
    scene.enemy_bullets.empty()
    encounter.attack('fan',0)
    assert not scene.enemy_bullets
    encounter.attack('fan',1)
    assert len(scene.enemy_bullets)==3
    encounter.emitters[1].kill()
    encounter.update(1)
    assert encounter.wave==1 and any(e.alive() for e in encounter.emitters)


def test_two_broly_shots_keep_warnings_until_fire_and_open_after_second(scene):
    from src.entities.enemies.boss import Boss
    from src.entities.bullets.laser_fx import LaserBeamSprite
    boss=Boss(scene.game,2)
    boss._state='fight'
    boss.sx,boss.sy=610,300
    boss._shoot_timer=0
    group=pygame.sprite.Group()
    fired=0
    seen=set()
    first_open=False
    for _ in range(480):
        group.update(1/60)
        boss.update(1/60,group,scene.player)
        for bullet in group:
            if isinstance(bullet,LaserBeamSprite) and not bullet.warning_only and bullet not in seen:
                fired+=1;seen.add(bullet)
        if boss._beam_charge_pattern:
            assert any(isinstance(b,LaserBeamSprite) and b.warning_only for b in group)
        if boss.is_stance_down:
            assert fired>=2
            first_open=True
            break
    assert first_open


def test_billy_has_one_heal_and_only_an_explicit_weapon_reward(scene):
    from src.entities.enemies.billy import EnemyBilly
    for reward, expected in ((None, ['HealItem']), ('WeaponItem', ['HealItem','WeaponItem'])):
        scene.items.empty()
        enemy = EnemyBilly(scene.game, 300, 300)
        enemy.fixed_drop = reward
        scene.enemies.add(enemy)
        scene._on_enemy_killed(enemy)
        assert sorted(type(item).__name__ for item in scene.items) == expected


def test_rest_point_does_not_delete_a_visible_weapon_reward(scene):
    from src.entities.items.weapon_item import WeaponItem
    scene.camera.x = scene.stage.learning['checkpoint_x']
    item = WeaponItem(scene.camera.x+200,300)
    item.rect.center = (200,300)
    scene.items.add(item)
    scene._update_learning(.1)
    assert not scene._learning_rest_done and item in scene.items
    item.kill()
    scene._update_learning(.1)
    assert scene._learning_rest_done


def test_queueing_boss_cannot_also_start_a_road_encounter(scene):
    scene.camera.x = 7240
    scene._queue_boss_spawn(1)
    scene._update_learning(1/60)
    assert scene._learning_encounter is None
    assert not any(getattr(e,'learning_emitter',False) for e in scene.enemies)


def test_reactive_policy_sidesteps_a_nearby_shot_instead_of_waiting_for_contact(scene):
    from tools.challenge_lab import reactive_actions
    from src.entities.bullets.enemy_bullet import EnemyBullet
    scene.terrain.empty()
    scene.camera.scroll_speed = 0
    scene.player.rect.center = (165,402)
    scene.enemy_bullets.add(EnemyBullet(220,398,-235,0))
    actions = reactive_actions(scene)
    assert 'move_up' in actions or 'move_down' in actions


def test_terrain_identity_keeps_equal_sized_blocks_at_different_heights_separate():
    from types import SimpleNamespace
    high = SimpleNamespace(world_x=123,rect=pygame.Rect(123,0,40,60))
    low = SimpleNamespace(world_x=123,rect=pygame.Rect(123,500,40,60))
    assert terrain_key(high) != terrain_key(low)
