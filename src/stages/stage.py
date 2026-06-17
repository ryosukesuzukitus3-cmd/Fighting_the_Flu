from __future__ import annotations
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.game import Game

_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "stages"


class Stage:
    def __init__(self, game: Game, stage_id: int) -> None:
        self.game     = game
        self.stage_id = stage_id
        self.elapsed: float = 0.0
        self.cleared: bool  = False

        data      = self._load(stage_id)
        self.bgm: str        = data.get("bgm", "MEGALOVANIA.mp3")
        self.initial_terrain: list = list(data.get("initial_terrain", []))
        self.terrain_layout: list  = list(data.get("terrain_layout", self.initial_terrain))
        self.boss_terrain: list    = list(data.get("boss_terrain", []))
        self.boss_terrain_mode: str = str(data.get("boss_terrain_mode", "replace"))
        self.weapon_drop_limit: int = max(0, int(data.get("weapon_drop_limit", 0)))
        self.events: list    = sorted(data.get("events", []), key=lambda e: e["time"])
        self.world_events: list = sorted(
            data.get("world_events", []),
            key=lambda e: e.get("trigger_x", e.get("x", e.get("world_x", 0))),
        )

    def _load(self, stage_id: int) -> dict:
        path = _DATA_DIR / f"stage{stage_id}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {"bgm": "MEGALOVANIA.mp3", "events": []}

    def update(self, dt: float) -> None:
        self.elapsed += dt
