from __future__ import annotations
from typing import TYPE_CHECKING
from src.entities.items.base import Item
from src.core.balance import HEAL_AMOUNT

if TYPE_CHECKING:
    from src.entities.player import Player


class HealItem(Item):
    color = (60, 210, 80)
    label = "+"

    def apply(self, player: Player) -> None:
        player.hp = min(player.hp + HEAL_AMOUNT, player.max_hp)
