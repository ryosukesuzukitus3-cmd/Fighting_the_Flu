from __future__ import annotations
import random
from typing import TYPE_CHECKING
import pygame
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.core.factories import make_enemy

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
                 terrain: pygame.sprite.Group | None = None,
                 world_events: list | None = None) -> None:
        self._game          = game
        self._enemies       = enemies
        self._enemy_bullets = enemy_bullets
        self._events        = events
        self._world_events  = sorted(
            world_events or [],
            key=lambda e: e.get("trigger_x", e.get("x", e.get("world_x", 0))),
        )
        self._player        = player
        self._stage_id      = stage_id
        self._terrain       = terrain
        self._index:   int   = 0
        self._world_index: int = 0
        self._elapsed: float = 0.0
        self.boss              = None   # Boss生成時にセットされる
        self.boss_pending      = False  # Bossイベント発火済み・未生成
        self.boss_pending_event: dict | None = None
        self.boss_gate_pending = False
        self.boss_gate_event: dict | None = None

    def update(self, dt: float, camera: Camera) -> None:
        self._elapsed += dt
        while self._index < len(self._events):
            event = self._events[self._index]
            if self._elapsed >= event["time"]:
                self._spawn_event(event, camera)
                self._index += 1
            else:
                break
        self._spawn_due_world_events(camera)

    def _spawn_due_world_events(self, camera: Camera) -> None:
        while self._world_index < len(self._world_events):
            event = self._world_events[self._world_index]
            preload = float(event.get("preload", event.get("spawn_margin", 80.0)))
            if camera.x + SCREEN_WIDTH + preload >= self._world_trigger_x(event):
                self._spawn_event(event, camera, world_locked=True)
                self._world_index += 1
            else:
                break

    def _world_trigger_x(self, event: dict) -> float:
        return float(event.get("trigger_x", event.get("x", event.get("world_x", 0.0))))

    def spawn_terrain_events(self, events: list[dict], camera: Camera) -> None:
        """Spawn terrain blueprints outside the enemy timeline."""
        for event in events:
            self._spawn_terrain_event(event, camera)

    def _spawn_event(self, event: dict, camera: Camera, *, world_locked: bool = False) -> None:
        enemy_type = event["type"]
        if self._spawn_terrain_event(event, camera):
            return
        if enemy_type == "BossGate":
            self.boss_gate_pending = True
            self.boss_gate_event = dict(event)
            return
        if enemy_type == "Boss":
            self.boss_pending = True
            self.boss_pending_event = dict(event)
            return

        count      = event.get("count", 1)
        formation  = event.get("formation", "random")
        enhanced   = event.get("enhanced", False)

        # 砲台などを地形表面に吸着させたい場合は "surface" を指定。
        if world_locked and ("x" in event or "world_x" in event):
            positions = self._world_positions(
                event,
                count,
                str(event.get("surface", "bottom")),
                camera,
                offset=float(event.get("surface_offset", event.get("offset", 20))),
                step=float(event.get("surface_step", event.get("step", 56))),
            )
        elif "surface" in event:
            positions = self._surface_positions(
                count,
                str(event.get("surface", "bottom")),
                camera,
                offset=float(event.get("surface_offset", 20)),
                step=float(event.get("surface_step", 56)),
            )
        # y 固定で出したい場合は "y" を指定（formation より優先）
        elif "y" in event:
            base_x = camera.spawn_x()
            positions = [(base_x + i * 44, float(event["y"])) for i in range(count)]
        else:
            positions = self._positions(count, formation, camera)
        for wx, wy in positions:
            enemy = self._make_enemy(
                enemy_type, wx, wy,
                enhanced=enhanced,
                surface=str(event.get("surface", "bottom")),
            )
            if enemy:
                self._enemies.add(enemy)

    def _world_positions(
        self,
        event: dict,
        count: int,
        surface: str,
        camera: Camera,
        *,
        offset: float,
        step: float,
    ) -> list[tuple[float, float]]:
        base_x = float(event.get("x", event.get("world_x", camera.spawn_x())))
        if "surface" in event:
            positions: list[tuple[float, float]] = []
            for i in range(count):
                wx = base_x + i * step
                sy = self._surface_y_at(wx, surface)
                if sy is None:
                    safe_top, safe_bottom = self._safe_y_bounds(wx, margin=_MARGIN)
                    sy = safe_bottom if surface == "bottom" else safe_top
                wy = sy - offset if surface == "bottom" else sy + offset
                positions.append((wx, wy))
            return positions
        if "y" in event:
            return [(base_x + i * step, float(event["y"])) for i in range(count)]

        safe_top, safe_bottom = self._safe_y_bounds(base_x, margin=_MARGIN)
        if safe_bottom <= safe_top:
            safe_top, safe_bottom = float(_MARGIN), float(SCREEN_HEIGHT - _MARGIN)
        formation = event.get("formation", "random")
        if formation == "line":
            y_step = (safe_bottom - safe_top) / max(count - 1, 1)
            return [(base_x + i * step, float(safe_top + i * y_step)) for i in range(count)]
        if formation == "v_shape":
            cy = (safe_top + safe_bottom) / 2
            amp = min(60.0, max(24.0, (safe_bottom - safe_top) * 0.25))
            return [
                (base_x + abs(i - count // 2) * step,
                 max(safe_top, min(safe_bottom, cy + (i - count // 2) * amp)))
                for i in range(count)
            ]
        return [
            (base_x + i * step, random.uniform(safe_top, safe_bottom))
            for i in range(count)
        ]

    def _positions(self, count: int, formation: str, camera: Camera) -> list[tuple[float, float]]:
        base_x = camera.spawn_x()
        safe_top, safe_bottom = self._safe_y_bounds(base_x, margin=_MARGIN)
        if safe_bottom <= safe_top:
            safe_top, safe_bottom = float(_MARGIN), float(SCREEN_HEIGHT - _MARGIN)

        if formation == "line":
            step = (safe_bottom - safe_top) / max(count - 1, 1)
            return [(base_x, float(safe_top + i * step)) for i in range(count)]
        elif formation == "v_shape":
            cx = (safe_top + safe_bottom) / 2
            amp = min(60.0, max(24.0, (safe_bottom - safe_top) * 0.25))
            return [
                (base_x + abs(i - count // 2) * 50,
                 max(safe_top, min(safe_bottom, cx + (i - count // 2) * amp)))
                for i in range(count)
            ]
        else:  # random
            return [
                (base_x + i * 40, random.uniform(safe_top, safe_bottom))
                for i in range(count)
            ]

    def _surface_positions(
        self,
        count: int,
        surface: str,
        camera: Camera,
        *,
        offset: float,
        step: float,
    ) -> list[tuple[float, float]]:
        base_x = camera.spawn_x()
        positions: list[tuple[float, float]] = []
        for i in range(count):
            wx = base_x + i * step
            sy = self._surface_y_at(wx, surface)
            if sy is None:
                safe_top, safe_bottom = self._safe_y_bounds(wx, margin=_MARGIN)
                sy = safe_bottom if surface == "bottom" else safe_top
            wy = sy - offset if surface == "bottom" else sy + offset
            positions.append((wx, wy))
        return positions

    def _terrain_at_x(self, world_x: float) -> list:
        if self._terrain is None:
            return []
        result = []
        for ter in self._terrain:
            left = getattr(ter, "world_x", 0.0)
            right = left + ter.rect.width
            if left <= world_x <= right:
                result.append(ter)
        return result

    def _safe_y_bounds(self, world_x: float, *, margin: float) -> tuple[float, float]:
        top = float(margin)
        bottom = float(SCREEN_HEIGHT - margin)
        for ter in self._terrain_at_x(world_x):
            side = getattr(ter, "side", "")
            y = float(getattr(ter, "y", ter.rect.y))
            h = float(ter.rect.height)
            if side == "top" or y <= 1:
                top = max(top, y + h + margin)
            elif side == "bottom" or y + h >= SCREEN_HEIGHT - 1:
                bottom = min(bottom, y - margin)
        return top, bottom

    def _surface_y_at(self, world_x: float, surface: str) -> float | None:
        candidates = []
        for ter in self._terrain_at_x(world_x):
            side = getattr(ter, "side", "")
            if surface == "bottom" and side == "bottom":
                candidates.append(getattr(ter, "surface_y", ter.rect.top))
            elif surface == "top" and side == "top":
                candidates.append(getattr(ter, "surface_y", ter.rect.bottom))
            elif not side:
                if surface == "bottom":
                    candidates.append(float(getattr(ter, "y", ter.rect.top)))
                elif surface == "top":
                    candidates.append(float(getattr(ter, "y", ter.rect.top)) + ter.rect.height)
        if not candidates:
            return None
        return min(candidates) if surface == "bottom" else max(candidates)

    def _make_enemy(
        self,
        enemy_type: str,
        wx: float,
        wy: float,
        *,
        enhanced: bool = False,
        surface: str = "bottom",
    ) -> Enemy | None:
        if enemy_type == "Boss":
            self.boss_pending = True  # game_scene 側で confirm_spawn_boss() を呼ぶ
            return None
        return make_enemy(
            enemy_type, self._game, wx, wy,
            enemy_bullets=self._enemy_bullets,
            player=self._player,
            terrain=self._terrain,
            surface=surface,
            enhanced=enhanced,
        )

    def _spawn_terrain_event(self, event: dict, camera: Camera) -> bool:
        enemy_type = event.get("type")
        if enemy_type in {"Terrain", "solid", "platform", "gate", "breakable_gate", "turret_mount"}:
            if self._terrain is not None:
                from src.entities.terrain import Terrain
                world_x = self._terrain_world_x(event, camera)
                destructible = bool(event.get("destructible", enemy_type in {"gate", "breakable_gate"}))
                self._terrain.add(Terrain(
                    world_x,
                    float(event.get("y", 0)),
                    int(event.get("w", 80)),
                    int(event.get("h", 80)),
                    event.get("kind", "wall"),
                    destructible=destructible,
                    hp=int(event.get("hp", 5)),
                    drop_chance=float(event.get("drop_chance", 0.0)),
                ))
            return True

        if enemy_type in {"TerrainStrip", "cave_section", "corridor"}:
            if self._terrain is not None:
                from src.entities.terrain import make_terrain_strip
                start_x = self._terrain_start_x(event, camera)
                segments = make_terrain_strip(
                    start_x,
                    length=int(event.get("length", 3600)),
                    theme=event.get("theme", "fever_cave"),
                    segment_w=int(event.get("segment_w", 64)),
                    seed=int(event.get("seed", self._stage_id)),
                    gap_min=int(event.get("gap_min", 270)),
                    gap_max=int(event.get("gap_max", 380)),
                    center_y=int(event.get("center_y", SCREEN_HEIGHT // 2)),
                    center_wave=int(event.get("center_wave", 42)),
                    top_min=int(event.get("top_min", 38)),
                    bottom_min=int(event.get("bottom_min", 42)),
                    irregularity=int(event.get("irregularity", 36)),
                    breakable_chance=float(event.get("breakable_chance", 0.0)),
                    breakable_hp=int(event.get("breakable_hp", 3)),
                    breakable_drop_chance=float(event.get("breakable_drop_chance", 0.0)),
                    profile=str(event.get("profile", "normal")),
                )
                self._terrain.add(*segments)
            return True

        return False

    def _terrain_world_x(self, event: dict, camera: Camera) -> float:
        if "x" in event:
            return float(event["x"])
        if "world_x" in event:
            return float(event["world_x"])
        if "screen_x" in event:
            return camera.x + float(event["screen_x"])
        if "start_offset" in event:
            return camera.x + float(event["start_offset"])
        return camera.spawn_x(float(event.get("spawn_margin", 50.0)))

    def _terrain_start_x(self, event: dict, camera: Camera) -> float:
        if "x" in event:
            return float(event["x"])
        if "world_x" in event:
            return float(event["world_x"])
        if "screen_x" in event:
            return camera.x + float(event["screen_x"])
        return camera.x + float(event.get("start_offset", -80))

    def skip_all_events(self) -> None:
        self._index = len(self._events)
        self._world_index = len(self._world_events)
        self.clear_boss_gate()

    def confirm_spawn_boss(self, stage_id: int | None = None) -> None:
        """game_scene が ALERT 後に呼び出すことで実際にボスを生成する"""
        from src.entities.enemies.boss import Boss
        boss_stage_id = self._stage_id if stage_id is None else stage_id
        self.boss         = Boss(self._game, stage_id=boss_stage_id)
        self.boss_pending = False
        self.boss_pending_event = None

    def clear_boss_gate(self) -> None:
        self.boss_gate_pending = False
        self.boss_gate_event = None
