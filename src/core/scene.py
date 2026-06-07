from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from src.core.game import Game


class Scene(ABC):
    def __init__(self, game: Game) -> None:
        self.game = game

    def on_enter(self) -> None:
        """シーン開始時に呼ばれる"""

    def on_exit(self) -> None:
        """シーン終了時に呼ばれる"""

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    @abstractmethod
    def update(self, delta_time: float) -> None:
        pass

    @abstractmethod
    def draw(self, screen: pygame.Surface) -> None:
        pass
