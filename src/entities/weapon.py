from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.entities.bullet import Bullet
    import pygame

# メインウェポンの強化段階（laserはアドオンスロットに分離）
# rapid1: 連射(発射間隔0.15s), rapid2: 超連射(0.12s), wide1: 2本, wide2: 3本
_MAIN_LEVELS = ["single", "rapid1", "rapid2", "wide1", "wide2", "medic"]

# (発射数/射撃, クールダウン秒, ダメージ/発)
_MAIN_FIRE_CONFIG: dict[str, tuple[int, float, int]] = {
    "single": (1, 0.25, 1),
    "rapid1": (1, 0.15, 1),
    "rapid2": (1, 0.12, 1),
    "wide1":  (2, 0.12, 1),
    "wide2":  (3, 0.12, 1),
    "medic":  (3, 0.12, 2),
}

# スピードアップ最大段階（1段階あたり+20%、最大2倍）
_SPEED_MAX_LEVEL = 5

# レベル別: (クールダウン秒, 発射角リスト)
_HOMING_CONFIG: dict[int, tuple[float, list[float]]] = {
    1: (1.07, [0.0]),
    2: (0.82, [0.0]),
    3: (0.63, [0.0]),
    4: (0.79, [-22.5, 22.5]),
    5: (0.66, [-22.5, 22.5]),
    6: (0.83, [-45.0, 0.0, 45.0]),
    7: (0.55, [-45.0, 0.0, 45.0]),
}


class Weapon:
    _MAIN_LEVELS = _MAIN_LEVELS  # 外部参照用

    def __init__(self) -> None:
        self.main_level:   int  = 0
        self.speed_level:  int  = 0
        self.laser_level:  int  = 0   # 0=なし, 1〜6
        self.homing_level: int  = 0   # 0=なし, 1〜7
        self.magnet_level: int  = 0   # 0=なし, 1=弱, 2=中, 3=強
        self.has_barrier:  bool = False
        self.weapon_stock: int  = 0   # 取得済みウェポンアイテム在庫（V で選択画面を開いて消費）
        self._homing_timer: float = 0.0   # ホーミング専用クールダウン

    @property
    def has_laser(self) -> bool:
        return self.laser_level > 0

    @property
    def has_homing(self) -> bool:
        return self.homing_level > 0

    @property
    def shoot_cooldown(self) -> float:
        return _MAIN_FIRE_CONFIG[self.main_type][1]

    @property
    def main_type(self) -> str:
        return _MAIN_LEVELS[self.main_level]

    @property
    def main_at_max(self) -> bool:
        return self.main_level >= len(_MAIN_LEVELS) - 1

    @property
    def speed_multiplier(self) -> float:
        return 1.0 + self.speed_level * 0.2

    @property
    def speed_at_max(self) -> bool:
        return self.speed_level >= _SPEED_MAX_LEVEL

    def upgrade(self, item_type: str) -> None:
        if item_type == "weapon_main":
            self.main_level = min(self.main_level + 1, len(_MAIN_LEVELS) - 1)
        elif item_type == "speed":
            self.speed_level = min(self.speed_level + 1, _SPEED_MAX_LEVEL)
        elif item_type == "laser":
            self.laser_level = min(self.laser_level + 1, 6)
        elif item_type == "homing":
            self.homing_level = min(self.homing_level + 1, 7)
        elif item_type == "magnet":
            self.magnet_level = min(self.magnet_level + 1, 3)
        elif item_type == "barrier":
            self.has_barrier = True

    def downgrade(self) -> None:
        """被弾時に1段階降格（barrier → laser → homing → main の順、speedは永続）"""
        if self.has_barrier:
            self.has_barrier = False
        elif self.laser_level > 0:
            self.laser_level -= 1
        elif self.homing_level > 0:
            self.homing_level -= 1
        elif self.main_level > 0:
            self.main_level -= 1

    def barrier_block(self) -> bool:
        """バリアがあればダメージを1回吸収してTrueを返す"""
        if self.has_barrier:
            self.has_barrier = False
            return True
        return False

    def snapshot(self) -> dict:
        """ステージ引き継ぎ用にウェポン状態を辞書化"""
        return {
            "main_level":   self.main_level,
            "speed_level":  self.speed_level,
            "laser_level":  self.laser_level,
            "homing_level": self.homing_level,
            "magnet_level": self.magnet_level,
            "has_barrier":  self.has_barrier,
            "weapon_stock": self.weapon_stock,
        }

    def restore(self, data: dict) -> None:
        """snapshot から状態を復元"""
        self.main_level   = data.get("main_level",   0)
        self.speed_level  = data.get("speed_level",  0)
        self.laser_level  = data.get("laser_level",  0)
        self.homing_level = data.get("homing_level", 0)
        self.magnet_level = data.get("magnet_level", 0)
        self.has_barrier  = data.get("has_barrier",  False)
        self.weapon_stock = data.get("weapon_stock", 0)

    def get_bullets(
        self,
        wx: float,
        wy: float,
        enemies: "pygame.sprite.Group",
        game=None,
        boss=None,
    ) -> "list[Bullet]":
        from src.entities.bullets.player_bullet import (
            NormalBullet, WideBullet, PierceBullet, HomingBullet,
        )
        bullets: list = []

        t = self.main_type
        if t in ("single", "rapid1", "rapid2"):
            bullets.append(NormalBullet(wx, wy))
        elif t == "wide1":
            bullets += [WideBullet(wx, wy, angle) for angle in (-12, 12)]
        elif t == "wide2":
            bullets += [WideBullet(wx, wy, angle) for angle in (-20, 0, 20)]
        elif t == "medic":
            bullets += [PierceBullet(wx, wy, angle, game=game) for angle in (0, 15, -15)]

        if self.has_homing and self._homing_timer <= 0:
            cooldown, angles = _HOMING_CONFIG.get(self.homing_level, (1.60, [0.0]))
            for angle in angles:
                bullets.append(HomingBullet(wx, wy, enemies, game=game, boss=boss, init_angle=angle))
            self._homing_timer = cooldown

        return bullets
