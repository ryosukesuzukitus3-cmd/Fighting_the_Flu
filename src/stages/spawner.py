from __future__ import annotations
import random
from typing import TYPE_CHECKING
import pygame
from src.core.constants import SCREEN_HEIGHT

if TYPE_CHECKING:
    from src.core.game import Game
    from src.core.camera import Camera
    from src.entities.player import Player
    from src.entities.enemies.base import Enemy

_MARGIN = 60


class EnemySpawner:
    def __init__(self, game: Game, enemies: pygame.sprite.Group,
                 enemy_bullets: pygame.sprite.Group,
                 events: list, player: Player,
                 stage_id: int = 1,
                 terrain: pygame.sprite.Group | None = None) -> None:
        self._game          = game
        self._enemies       = enemies
        self._enemy_bullets = enemy_bullets
        self._events        = events
        self._player        = player
        self._stage_id      = stage_id
        self._terrain       = terrain
        self._index:   int   = 0
        self._elapsed: float = 0.0
        self.boss         = None   # Boss生成時にセットされる
        self.boss_pending = False  # Bossイベント発火済み・未生成

    def update(self, dt: float, camera: Camera) -> None:
        self._elapsed += dt
        while self._index < len(self._events):
            event = self._events[self._index]
            if self._elapsed >= event["time"]:
                self._spawn_event(event, camera)
                self._index += 1
            else:
                break

    def _spawn_event(self, event: dict, camera: Camera) -> None:
        enemy_type = event["type"]

        # 地形（壁・障害物・デブリ）: 画面右端から流す
        if enemy_type == "Terrain":
            if self._terrain is not None:
                from src.entities.terrain import Terrain
                self._terrain.add(Terrain(
                    camera.spawn_x(),
                    float(event.get("y", 0)),
                    int(event.get("w", 80)),
                    int(event.get("h", 80)),
                    event.get("kind", "wall"),
                ))
            return

        count      = event.get("count", 1)
        formation  = event.get("formation", "random")
        enhanced   = event.get("enhanced", False)
        # 砲台など y 固定で出したい場合は "y" を指定（formation より優先）
        if "y" in event:
            base_x = camera.spawn_x()
            positions = [(base_x + i * 44, float(event["y"])) for i in range(count)]
        else:
            positions = self._positions(count, formation, camera)
        for wx, wy in positions:
            enemy = self._make_enemy(enemy_type, wx, wy, enhanced=enhanced)
            if enemy:
                self._enemies.add(enemy)

    def _positions(self, count: int, formation: str, camera: Camera) -> list[tuple[float, float]]:
        base_x = camera.spawn_x()
        if formation == "line":
            step = (SCREEN_HEIGHT - 2 * _MARGIN) / max(count - 1, 1)
            return [(base_x, float(_MARGIN + i * step)) for i in range(count)]
        elif formation == "v_shape":
            cx = SCREEN_HEIGHT / 2
            return [
                (base_x + abs(i - count // 2) * 50, cx + (i - count // 2) * 60)
                for i in range(count)
            ]
        else:  # random
            return [
                (base_x + i * 40, float(random.randint(_MARGIN, SCREEN_HEIGHT - _MARGIN)))
                for i in range(count)
            ]

    def _make_enemy(self, enemy_type: str, wx: float, wy: float, *, enhanced: bool = False) -> Enemy | None:
        from src.entities.enemies.virus    import EnemyVirus
        from src.entities.enemies.takeshi  import EnemyTakeshi
        from src.entities.enemies.broly    import EnemyBroly
        from src.entities.enemies.pachemon import EnemyPachemon
        from src.entities.enemies.billy    import EnemyBilly
        from src.entities.enemies.turret   import EnemyTurret
        if enemy_type == "EnemyVirus":
            return EnemyVirus(self._game, wx, wy, enhanced=enhanced)
        if enemy_type == "EnemyTakeshi":
            return EnemyTakeshi(self._game, wx, wy, enhanced=enhanced)
        if enemy_type == "EnemyBroly":
            return EnemyBroly(self._game, wx, wy, target_y=self._player.sy, enhanced=enhanced)
        if enemy_type == "EnemyPachemon":
            return EnemyPachemon(self._game, wx, wy, self._enemy_bullets, self._player, enhanced=enhanced)
        if enemy_type == "EnemyTurret":
            return EnemyTurret(self._game, wx, wy, self._enemy_bullets, self._player, enhanced=enhanced)
        if enemy_type == "EnemyBilly":
            return EnemyBilly(self._game, wx, wy)
        if enemy_type == "Boss":
            self.boss_pending = True  # game_scene 側で confirm_spawn_boss() を呼ぶ
        return None

    def confirm_spawn_boss(self) -> None:
        """game_scene が ALERT 後に呼び出すことで実際にボスを生成する"""
        from src.entities.enemies.boss import Boss
        self.boss         = Boss(self._game, stage_id=self._stage_id)
        self.boss_pending = False
