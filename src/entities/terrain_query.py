from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Callable

import pygame


def is_terrain_collidable(terrain: object) -> bool:
    return not bool(getattr(terrain, "terrain_visual_only", False))


def iter_collidable_terrain(terrain: Iterable[object] | None) -> Iterator[object]:
    if terrain is None:
        return
    for ter in terrain:
        if is_terrain_collidable(ter):
            yield ter


def terrain_collideany(
    sprite: pygame.sprite.Sprite,
    terrain: Iterable[pygame.sprite.Sprite] | None,
    collided: Callable[[pygame.sprite.Sprite, pygame.sprite.Sprite], bool] | None = None,
) -> pygame.sprite.Sprite | None:
    for ter in iter_collidable_terrain(terrain):
        if not isinstance(ter, pygame.sprite.Sprite):
            continue
        if collided is not None:
            if collided(sprite, ter):
                return ter
        elif sprite.rect.colliderect(ter.rect):
            return ter
    return None
