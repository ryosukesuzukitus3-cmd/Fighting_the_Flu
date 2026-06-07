from __future__ import annotations
from typing import TYPE_CHECKING
from src.entities.items.base import Item

if TYPE_CHECKING:
    from src.entities.player import Player


class ScoreItem(Item):
    color     = (255, 215, 40)
    label     = "★"
    popup_text = "+1000"

    def apply(self, player: Player) -> None:
        player.game.shared.score += 1000
