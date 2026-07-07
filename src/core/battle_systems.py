"""バトルシステムv2 の純ロジック（pygame 非依存・ユニットテスト対象）。

- HeatSystem   : 射撃で体温が上がり、放置と先輩（解熱弾Lv）で冷える。
                 39.9℃到達で「熱暴走」＝一定時間メイン/レーザー射撃不可。
- award_pieces : コンボ閾値の通過判定で持ち駒（歩/金/龍）を獲得する。
- enrage_mult  : ボスフェーズ経過時間 → 症状悪化（攻撃間隔短縮）倍率。

数値の SSOT は src/core/balance.py。配線は game_scene / boss.py が行う。
"""
from __future__ import annotations

from src.core.balance import (
    ENRAGE_MAX_MULT, ENRAGE_T0, ENRAGE_T1,
    HEAT_AFTER_OVERHEAT, HEAT_BOSS_DOWN_MULT, HEAT_COOL_KARONARU,
    HEAT_COOL_RATE, HEAT_MAX, HEAT_TEMP_MAX, HEAT_TEMP_MIN,
    OVERHEAT_DURATION, PIECE_COMBO_THRESHOLDS, PIECE_MAX_HELD,
)


class HeatSystem:
    """プレイヤーの体温ゲージ。add() が True を返した瞬間が熱暴走の発生。"""

    def __init__(self) -> None:
        self.heat: float = 0.0
        self._lock_timer: float = 0.0

    @property
    def overheated(self) -> bool:
        return self._lock_timer > 0.0

    @property
    def ratio(self) -> float:
        return max(0.0, min(1.0, self.heat / HEAT_MAX))

    @property
    def display_temp(self) -> float:
        """HUD 表示用の体温（℃）。"""
        return HEAT_TEMP_MIN + self.ratio * (HEAT_TEMP_MAX - HEAT_TEMP_MIN)

    def add(self, pts: float) -> bool:
        """射撃による加熱。熱暴走が「この加熱で始まった」とき True。"""
        if self.overheated:
            return False
        self.heat = min(HEAT_MAX, self.heat + pts)
        if self.heat >= HEAT_MAX:
            self._lock_timer = OVERHEAT_DURATION
            return True
        return False

    def update(self, dt: float, karonaru_lv: int = 0, boss_down: bool = False) -> None:
        if self._lock_timer > 0.0:
            self._lock_timer -= dt
            if self._lock_timer <= 0.0:
                self._lock_timer = 0.0
                self.heat = HEAT_AFTER_OVERHEAT
            return
        cool = HEAT_COOL_RATE + max(0, karonaru_lv) * HEAT_COOL_KARONARU
        if boss_down:
            cool *= HEAT_BOSS_DOWN_MULT
        self.heat = max(0.0, self.heat - cool * dt)


def award_pieces(prev_combo: int, new_combo: int, held_count: int) -> list[str]:
    """コンボが prev→new に伸びたとき新たに獲得する持ち駒のリスト。

    閾値の「通過」でのみ獲得（同一コンボ中の二重取得なし）。所持上限
    PIECE_MAX_HELD を超える分は切り捨てる。
    """
    gained: list[str] = []
    for threshold in sorted(PIECE_COMBO_THRESHOLDS):
        if prev_combo < threshold <= new_combo:
            if held_count + len(gained) < PIECE_MAX_HELD:
                gained.append(PIECE_COMBO_THRESHOLDS[threshold])
    return gained


def enrage_mult(fight_time: float) -> float:
    """症状悪化倍率。ENRAGE_T0 まで 1.0、ENRAGE_T1 で最大に線形到達。"""
    if fight_time <= ENRAGE_T0:
        return 1.0
    t = min(1.0, (fight_time - ENRAGE_T0) / (ENRAGE_T1 - ENRAGE_T0))
    return 1.0 + (ENRAGE_MAX_MULT - 1.0) * t
