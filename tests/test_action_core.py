"""Player-facing regressions for the simplified action controls and progression."""
import json
import pygame
import pytest
from tools.agent_playtest import Session


def test_tutorial_reaches_laser_practice_and_finishes_by_releasing(tmp_path):
    from src.scenes.tutorial_scene import TutorialScene, _TARGET_SHOTS
    with_session = Session(tmp_path/'tutorial')
    try:
        game=with_session.game
        game.change_scene(TutorialScene(game))
        with_session.command({'step':1,'actions':[]})
        scene=game._scene
        scene.player._entering=False
        scene._start_shoot()
        scene._shots=_TARGET_SHOTS-1
        with_session.command({'step':1,'actions':['fire']})
        assert scene._in_dialogue
        with_session.command({'tap':'ui_accept'})
        assert scene._phase == 'laser'
        with_session.command({'step':40,'actions':['laser']})
        assert scene.laser.is_active and scene._heat.heat > 0
        assert scene._laser_practiced
        with_session.command({'step':120,'actions':[]})
        assert scene._phase == 'dummy' and scene._in_dialogue
        assert scene.player.weapon.laser_level == 0  # Practice equipment is temporary.
    finally:
        with_session.close()


def test_removed_piece_binding_is_ignored_without_losing_custom_controls(monkeypatch,tmp_path):
    from src.managers.settings import SettingsManager
    monkeypatch.setenv('FLU_USER_DATA_DIR',str(tmp_path))
    (tmp_path/'settings.json').write_text(json.dumps({'key_bindings':{'bomb':'K_b','fire':'K_q'}}),encoding='utf-8')
    settings=SettingsManager()
    assert 'bomb' not in settings.get_key_bindings()
    assert settings.get_key_bindings()['fire'] == pygame.K_q


def test_legacy_speed_is_capped_and_each_upgrade_is_useful():
    from src.entities.weapon import Weapon, _SPEED_MAX_LEVEL
    weapon=Weapon()
    previous=1
    for _ in range(_SPEED_MAX_LEVEL):
        weapon.upgrade('speed')
        assert previous < weapon.speed_multiplier <= 1.4
        previous=weapon.speed_multiplier
    weapon.restore({'speed_level':5})
    assert weapon.speed_at_max
    assert weapon.speed_multiplier == pytest.approx(previous)


def test_fortress_does_not_leave_an_unintended_unguarded_resummon_gap(monkeypatch,tmp_path):
    import pygame
    from tools.headless import build_game_scene
    from src.entities.enemies.boss import Boss
    monkeypatch.setenv('FLU_USER_DATA_DIR',str(tmp_path))
    game,_=build_game_scene(3)
    try:
        boss=Boss(game,3)
        boss._state='fight'
        dead=pygame.sprite.Sprite()
        boss._summoned=[dead]
        boss._update_gimmick(.01,'turrets',pygame.sprite.Group(),None)
        assert boss.is_stance_down
        before=boss.hp
        boss.take_damage(5)
        assert before-boss.hp == 10
        boss._update_gimmick(3,'turrets',pygame.sprite.Group(),None)
        before=boss.hp
        boss.take_damage(5)
        assert boss.hp == before
        group=pygame.sprite.Group()
        def summon(count):
            sprites=[pygame.sprite.Sprite() for _ in range(count)]
            group.add(*sprites)
            return sprites
        boss.summon_turret_fn=summon
        boss._update_gimmick(.01,'turrets',pygame.sprite.Group(),None)
        assert len(boss._summoned) == 3
    finally:
        game.close()


def test_fortress_loses_shield_after_two_waves_and_keeps_attacking(monkeypatch, tmp_path):
    from tools.headless import build_game_scene
    from src.entities.enemies.boss import Boss
    monkeypatch.setenv("FLU_USER_DATA_DIR", str(tmp_path))
    game, scene = build_game_scene(3)
    try:
        boss = Boss(game, 3)
        boss._state = "fight"
        group = pygame.sprite.Group()
        def summon(count):
            wave = [pygame.sprite.Sprite() for _ in range(count)]
            group.add(*wave)
            return wave
        boss.summon_turret_fn = summon
        for wave_number in (1, 2):
            boss._update_gimmick(.01, "turrets", group, scene.player)
            assert len(boss._summoned) == 3
            assert boss._turret_waves == wave_number
            for drone in list(boss._summoned):
                drone.kill()
            assert boss._update_gimmick(.01, "turrets", group, scene.player)
            boss._update_gimmick(3, "turrets", group, scene.player)
        for _ in range(3):
            assert not boss._update_gimmick(10, "turrets", group, scene.player)
        assert boss._turret_core_exposed and not boss.is_stance_down
        assert boss._turret_waves == 2 and not boss._summoned
        assert boss._phase[1] == "rock_fall"
        hp = boss.hp
        boss.take_damage(5)
        assert hp - boss.hp == 5
    finally:
        game.close()
