"""
シーン間で共有されるゲーム状態の型安全なコンテナ。
game.shared dict の代替として使用する。
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class GameState:
    # ゲーム進行
    score:      int = 0
    kill_count: int = 0
    stage:      int = 1

    # 残機（コンティニュー可能回数）
    lives: int = 3

    # ステージ引き継ぎ（ボス撃破→StageClear 間のみ使用。pop 相当で取得後は None にする）
    carry_hp:     int | None  = None
    carry_weapon: dict | None = None

    # コンティニュー用: ステージ開始時のウェポンスナップショット
    stage_start_weapon: dict | None = None

    def take_carry(self) -> tuple[int, dict] | None:
        """引き継ぎデータを取り出す。データがなければ None を返す。"""
        if self.carry_hp is None or self.carry_weapon is None:
            return None
        hp, wp = self.carry_hp, self.carry_weapon
        self.carry_hp     = None
        self.carry_weapon = None
        return hp, wp

    def has_carry(self) -> bool:
        return self.carry_hp is not None and self.carry_weapon is not None
