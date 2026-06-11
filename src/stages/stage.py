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
        self.boss_terrain: list    = list(data.get("boss_terrain", []))
        self.events: list    = sorted(data.get("events", []), key=lambda e: e["time"])

    def _load(self, stage_id: int) -> dict:
        path = _DATA_DIR / f"stage{stage_id}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {"bgm": "MEGALOVANIA.mp3", "events": []}

    def update(self, dt: float) -> None:
        self.elapsed += dt
