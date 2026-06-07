from __future__ import annotations
from typing import TYPE_CHECKING
from src.entities.items.base import Item

if TYPE_CHECKING:
    from src.entities.player import Player


class ExtraLifeItem(Item):
    color     = (160, 80, 220)
    label     = "▲"
    popup_text = "1UP!"

    def apply(self, player: Player) -> None:
        player.game.shared.lives += 1
