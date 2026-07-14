"""バトルシステムv2（体幹/体温/持ち駒/症状悪化）のテスト。

前半は pygame 非依存の純ロジック（battle_systems.py）、後半はヘッドレス
ハーネス上の Boss で体幹→ダウン→倍率→回復のサイクルを検証する。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from tools.headless import build_game_scene  # noqa: E402
import pygame  # noqa: E402

from src.core import balance  # noqa: E402
from src.core.battle_systems import HeatSystem, award_pieces, enrage_mult  # noqa: E402


# ── HeatSystem ───────────────────────────────────────────────────────
def test_heat_accumulates_and_overheats():
    h = HeatSystem()
    assert not h.overheated
    started = h.add(balance.HEAT_MAX - 1.0)
    assert not started and not h.overheated
    started = h.add(5.0)
    assert started and h.overheated
    # 熱暴走中は追加加熱もオーバーヒート再発火もしない
    assert h.add(50.0) is False


def test_heat_unlocks_after_duration_with_residual_heat():
    h = HeatSystem()
    h.add(balance.HEAT_MAX)
    h.update(balance.OVERHEAT_DURATION + 0.1)
    assert not h.overheated
    assert h.heat == pytest.approx(balance.HEAT_AFTER_OVERHEAT)


def test_heat_cooling_scales_with_karonaru_and_boss_down():
    base = HeatSystem();  base.heat = 60.0
    kalv = HeatSystem();  kalv.heat = 60.0
    down = HeatSystem();  down.heat = 60.0
    base.update(1.0)
    kalv.update(1.0, karonaru_lv=3)
    down.update(1.0, boss_down=True)
    assert base.heat == pytest.approx(60.0 - balance.HEAT_COOL_RATE)
    assert kalv.heat == pytest.approx(
        60.0 - (balance.HEAT_COOL_RATE + 3 * balance.HEAT_COOL_KARONARU))
    assert down.heat == pytest.approx(
        60.0 - balance.HEAT_COOL_RATE * balance.HEAT_BOSS_DOWN_MULT)


def test_display_temp_range():
    h = HeatSystem()
    assert h.display_temp == pytest.approx(balance.HEAT_TEMP_MIN)
    h.heat = balance.HEAT_MAX
    assert h.display_temp == pytest.approx(balance.HEAT_TEMP_MAX)


# ── 持ち駒 ───────────────────────────────────────────────────────────
def test_award_pieces_on_threshold_crossing():
    thresholds = sorted(balance.PIECE_COMBO_THRESHOLDS)
    t0 = thresholds[0]
    assert award_pieces(t0 - 1, t0, 0) == [balance.PIECE_COMBO_THRESHOLDS[t0]]
    # 通過済みの閾値では再取得しない
    assert award_pieces(t0, t0 + 1, 1) == []


def test_award_pieces_respects_cap():
    lo, hi = min(balance.PIECE_COMBO_THRESHOLDS), max(balance.PIECE_COMBO_THRESHOLDS)
    gained = award_pieces(lo - 1, hi, balance.PIECE_MAX_HELD - 1)
    assert len(gained) == 1   # 空き1枠なら1つだけ
    assert award_pieces(lo - 1, hi, balance.PIECE_MAX_HELD) == []


# ── 症状悪化 ─────────────────────────────────────────────────────────
def test_enrage_mult_ramp():
    assert enrage_mult(0.0) == 1.0
    assert enrage_mult(balance.ENRAGE_T0) == 1.0
    mid = (balance.ENRAGE_T0 + balance.ENRAGE_T1) / 2
    assert 1.0 < enrage_mult(mid) < balance.ENRAGE_MAX_MULT
    assert enrage_mult(balance.ENRAGE_T1 + 60) == pytest.approx(balance.ENRAGE_MAX_MULT)


# ── Boss 体幹（ヘッドレスハーネス）───────────────────────────────────
@pytest.fixture(scope="module")
def game():
    g, _ = build_game_scene(1)
    yield g
    pygame.quit()


def _fight_boss(game, stage_id: int):
    from src.entities.enemies.boss import Boss
    b = Boss(game, stage_id=stage_id)
    b._state = "fight"
    return b


def test_shield_boss_stance_break_and_down_cycle(game):
    b = _fight_boss(game, 1)
    assert b.stance_ratio() == pytest.approx(1.0)
    b._shield_active = True
    b.add_stance(999.0)                      # シールド中は体幹が削れない
    assert b.stance_ratio() == pytest.approx(1.0)
    b._shield_active = False
    b.add_stance(balance.STANCE_MAX[1])      # 解除中に削り切る → ダウン
    assert b.is_stance_down and b._down_timer > 0
    hp0 = b.hp
    b.take_damage(10)
    assert hp0 - b.hp == int(10 * balance.STANCE_DOWN_MULT)   # ダウン中×2
    # ダウン時間を消化すると体幹全回復で復帰
    b.update(balance.STANCE_DOWN_DUR + 0.1, pygame.sprite.Group(), game._scene.player)
    assert not b.is_stance_down
    assert b.stance_ratio() == pytest.approx(1.0)


def test_intact_stance_heavily_reduces_boss_hp_damage(game):
    b = _fight_boss(game, 4)
    b._shield_active = False
    hp0 = b.hp
    b.take_damage(25)
    assert hp0 - b.hp == 4  # int(25 * 0.16), before the stance is broken


def test_weakpoint_boss_stance_break_exposes_core(game):
    b = _fight_boss(game, 2)
    hp0 = b.hp
    b.take_damage(10)                        # 露出前は HP 無効・体幹のみ削れる
    assert b.hp == hp0
    assert b.stance_ratio() < 1.0
    b.add_stance(balance.STANCE_MAX[2])      # 削り切ると弱点露出（＝ダウン）
    assert b._weak_timer > 0 and b.is_stance_down
    b.take_damage(10)
    assert hp0 - b.hp == 20                  # 露出中×2（既存 _WEAK_MULT）


def test_bomb_stance_ignores_shield(game):
    b = _fight_boss(game, 1)
    b._shield_active = True
    b.add_stance(balance.STANCE_MAX[1], ignore_shield=True)   # ボムはシールド貫通
    assert b.is_stance_down
    assert b._shield_active is False


def test_enrage_speeds_up_attacks_but_not_form3(game):
    b = _fight_boss(game, 1)
    b._fight_time = balance.ENRAGE_T1 + 10
    assert b._enrage_mult() == pytest.approx(balance.ENRAGE_MAX_MULT)
    assert 0.99 <= b.enrage_ratio <= 1.0
    b4 = _fight_boss(game, 4)
    b4._form3 = True
    b4._fight_time = balance.ENRAGE_T1 + 10
    assert b4._enrage_mult() == 1.0          # Form3 は症状悪化の対象外


def test_form3_is_exempt_from_stance(game):
    b = _fight_boss(game, 4)
    b._form3 = True
    b._reset_battle_v2_for_form()
    assert b.stance_ratio() is None
    b.add_stance(999.0)
    assert not b.is_stance_down
