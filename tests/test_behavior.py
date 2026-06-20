"""振る舞い（behavioral）テスト。

test_consistency.py が「ソースに特定の記述があるか」を文字列で検査するのに対し、
こちらは実際にオブジェクトのメソッドを呼んで *結果* を検証する。
ゲームロジックの回帰（例: PR #48 の先輩射撃バグ）を守る層。
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()


# ── Weapon（純ロジック）─────────────────────────────────────────────

def test_weapon_upgrade_caps_each_track() -> None:
    from src.entities.weapon import Weapon

    w = Weapon()
    for _ in range(20):
        w.upgrade("weapon_main")
    assert w.main_level == len(Weapon._MAIN_LEVELS) - 1
    assert w.main_at_max
    assert w.main_type == "medic"

    for _ in range(20):
        w.upgrade("speed")
    assert w.speed_at_max
    assert w.speed_multiplier == 1.0 + 5 * 0.2

    for _ in range(20):
        w.upgrade("laser")
    assert w.laser_level == 6 and w.has_laser

    for _ in range(20):
        w.upgrade("homing")
    assert w.homing_level == 7 and w.has_homing

    for _ in range(20):
        w.upgrade("magnet")
    assert w.magnet_level == 3

    w.upgrade("barrier")
    assert w.has_barrier


def test_weapon_downgrade_priority_order() -> None:
    """降格順は barrier → laser → homing → main。speed は永続。"""
    from src.entities.weapon import Weapon

    w = Weapon()
    w.upgrade("barrier")
    w.upgrade("laser")
    w.upgrade("homing")
    w.upgrade("weapon_main")
    w.upgrade("speed")
    main_before, speed_before = w.main_level, w.speed_level

    w.downgrade()
    assert not w.has_barrier
    w.downgrade()
    assert w.laser_level == 0
    w.downgrade()
    assert w.homing_level == 0
    w.downgrade()
    assert w.main_level == main_before - 1

    assert w.speed_level == speed_before  # speed は一度も下がらない


def test_weapon_barrier_block_consumes_once() -> None:
    from src.entities.weapon import Weapon

    w = Weapon()
    w.upgrade("barrier")
    assert w.barrier_block() is True
    assert w.has_barrier is False
    assert w.barrier_block() is False


def test_weapon_main_type_and_cooldown_follow_level() -> None:
    from src.entities.weapon import Weapon

    w = Weapon()
    assert w.main_type == "single"
    assert w.shoot_cooldown == 0.25
    w.main_level = 1
    assert w.main_type == "rapid1"
    assert w.shoot_cooldown == 0.15


def test_weapon_snapshot_restore_roundtrip() -> None:
    from src.entities.weapon import Weapon

    w = Weapon()
    for key in ("weapon_main", "speed", "laser", "homing", "magnet", "barrier"):
        w.upgrade(key)
    w.weapon_stock = 3
    snap = w.snapshot()

    restored = Weapon()
    restored.restore(snap)
    assert restored.snapshot() == snap


# ── Player（無敵・被弾）──────────────────────────────────────────────

def _make_player(hp: int = 100, max_hp: int = 100):
    """画像ロードを伴う __init__ を避け、被弾ロジックに必要な属性だけ持つ Player。"""
    from src.entities.player import Player
    from src.entities.weapon import Weapon

    p = object.__new__(Player)
    p.hp = hp
    p.max_hp = max_hp
    p._invincible_timer = 0.0
    p._blink_visible = True
    p._blink_timer = 0.0
    p.weapon = Weapon()
    return p


def test_player_take_damage_reduces_hp_and_grants_invincibility() -> None:
    from src.entities.player import _INVINCIBLE_TIME

    p = _make_player(hp=100)
    p.take_damage(15)
    assert p.hp == 85
    assert p.is_invincible
    assert p._invincible_timer == _INVINCIBLE_TIME


def test_player_invincible_blocks_repeat_damage() -> None:
    p = _make_player(hp=100)
    p.take_damage(10)
    hp_after_first = p.hp
    p.take_damage(10)  # まだ無敵 → 無効
    assert p.hp == hp_after_first


def test_player_take_damage_does_not_downgrade_weapon() -> None:
    """HP ゲージ制: 被弾でウェポン降格しない（旧仕様の回帰防止）。"""
    p = _make_player(hp=100)
    p.weapon.upgrade("weapon_main")
    p.weapon.upgrade("laser")
    before = p.weapon.snapshot()
    p.take_damage(10)
    assert p.weapon.snapshot() == before


# ── Companion（撤退→復帰・最大形態）──────────────────────────────────

class _SoundStub:
    def play_se_alias(self, *a, **k) -> None: ...
    def play_se(self, *a, **k) -> None: ...


class _GameStub:
    sound = _SoundStub()


class _PlayerStub:
    def __init__(self) -> None:
        self.rect = pygame.Rect(400, 300, 24, 32)

        class _W:
            speed_multiplier = 1.0

        self.weapon = _W()
        self.fire_held = False


def test_companion_damage_retire_and_revive_cycle() -> None:
    from src.entities.companion import Karonaru, _RETURN_TIME

    c = Karonaru(_GameStub())
    c.max_hp = 5
    c.hp = 5
    c.take_damage(5)  # hp -> 0 -> 撤退
    assert not c.is_active

    # _RETURN_TIME 経過で復帰し、HP 全快
    player = _PlayerStub()
    c.update(_RETURN_TIME + 1.0, player, pygame.sprite.Group(), None, pygame.sprite.Group())
    assert c.is_active
    assert c.hp == c.max_hp


def test_companion_max_mode_does_not_fall() -> None:
    """薬効最大形態は致死ダメージでも落ちず HP1 で踏みとどまる（台本「今度は落ちない」）。"""
    from src.entities.companion import Karonaru

    c = Karonaru(_GameStub())
    c.set_max()
    c._invincible_timer = 0.0  # 復帰直後の無敵を解いて致死ダメージを通す
    c.take_damage(10)
    assert c.is_active
    assert c.hp == 1


def test_companion_holds_fire_when_can_fire_false() -> None:
    """ボス出現演出中（can_fire=False）は player.fire_held でも撃たない（PR #48 回帰）。"""
    from src.entities.companion import Karonaru

    c = Karonaru(_GameStub())
    player = _PlayerStub()
    player.fire_held = True
    bullets = pygame.sprite.Group()
    empty = pygame.sprite.Group()

    class _Cam:
        x = 0.0

    c._shoot_cooldown = 0.0
    c.update(0.016, player, bullets, _Cam(), empty, empty, None, can_fire=False)
    assert len(bullets) == 0

    c._shoot_cooldown = 0.0
    c.update(0.016, player, bullets, _Cam(), empty, empty, None, can_fire=True)
    assert len(bullets) >= 1


# ── ボス出現演出ステートマシン ──────────────────────────────────────

class _InputStub:
    def is_held_with_repeat(self, *a, **k) -> bool: return False
    def is_pressed(self, *a, **k) -> bool: return False
    def is_action_pressed(self, *a, **k) -> bool: return False


class _SceneGameStub:
    def __init__(self) -> None:
        self.input = _InputStub()
        self.sound = _SoundStub()
        self.sound.play_bgm = lambda *a, **k: None          # type: ignore[attr-defined]
        self.sound.play_bgm_if_new = lambda *a, **k: None    # type: ignore[attr-defined]


def test_boss_intro_fight_banner_advances_to_fighting() -> None:
    from src.scenes.game_scene import GameScene

    s = object.__new__(GameScene)
    s.game = _SceneGameStub()
    s._boss_intro_state = "fight_banner"
    s._boss_intro_timer = 0.05
    GameScene._update_boss_intro(s, 0.1)  # タイマー満了
    assert s._boss_intro_state == "fighting"


def test_boss_intro_start_helpers_set_expected_state() -> None:
    from src.scenes.game_scene import GameScene

    s = object.__new__(GameScene)
    s.game = _SceneGameStub()
    s._active_boss_stage_id = 1
    s._pending_boss_stage_id = None
    s._stage_id = 1
    s._fight_sound_played = False

    GameScene._start_boss_name(s)
    assert s._boss_intro_state == "boss_name"

    GameScene._start_fight_banner(s)
    assert s._boss_intro_state == "fight_banner"
    assert s._fight_sound_played is True


def test_boss_intro_freeze_states_are_distinct_from_combat() -> None:
    """戦闘可能なのは ("", "fighting") のみ。alert/entering は
    フリーズでも戦闘でもない「演出中」で、ここが PR #48 のバグの温床だった。"""
    from src.scenes.game_scene import _BOSS_INTRO_FREEZE

    combat = {"", "fighting"}
    assert combat.isdisjoint(_BOSS_INTRO_FREEZE)
    for state in ("alert", "entering"):
        assert state not in _BOSS_INTRO_FREEZE
        assert state not in combat
