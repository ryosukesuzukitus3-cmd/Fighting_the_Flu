"""Lightweight playback for transparent, video-derived PNG sequences."""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from src.core.video_effects import VIDEO_EFFECTS, VideoEffectSpec, video_effect_spec


_FRAME_CACHE: dict[str, tuple[pygame.Surface, ...]] = {}


def load_video_effect_frames(resources, key: str) -> tuple[pygame.Surface, ...]:
    if key not in _FRAME_CACHE:
        spec = video_effect_spec(key)
        _FRAME_CACHE[key] = tuple(
            resources.image(spec.frame_path(i)) for i in range(spec.frame_count)
        )
    return _FRAME_CACHE[key]


@dataclass
class _PlayingEffect:
    spec: VideoEffectSpec
    frames: tuple[pygame.Surface, ...]
    center: tuple[float, float]
    size: tuple[int, int]
    angle: float = 0.0
    flip_x: bool = False
    opacity: int = 255
    loop: bool = False
    elapsed: float = 0.0
    _cached_index: int = -1
    _cached_image: pygame.Surface | None = None

    @property
    def finished(self) -> bool:
        return not self.loop and self.elapsed >= self.spec.duration

    def update(self, dt: float) -> None:
        self.elapsed += max(0.0, dt)

    def _frame_index(self) -> int:
        raw = int(self.elapsed * self.spec.fps)
        if self.loop:
            return raw % len(self.frames)
        return min(len(self.frames) - 1, raw)

    def image(self) -> pygame.Surface:
        index = self._frame_index()
        if index == self._cached_index and self._cached_image is not None:
            return self._cached_image
        image = self.frames[index]
        if image.get_size() != self.size:
            image = pygame.transform.smoothscale(image, self.size)
        if self.flip_x:
            image = pygame.transform.flip(image, True, False)
        if self.angle:
            image = pygame.transform.rotate(image, self.angle)
        if self.opacity < 255:
            image = image.copy()
            image.set_alpha(self.opacity)
        # Keep only the current scaled frame.  Full-screen effects can contain
        # 30+ frames; retaining every 800x600 transform would otherwise add
        # tens of megabytes for a cue that only lives for a second or two.
        self._cached_index = index
        self._cached_image = image
        return image


class VideoEffectLayer:
    """Owns screen-space video effects for one scene."""

    def __init__(self, resources) -> None:
        self._resources = resources
        self._effects: list[_PlayingEffect] = []

    def clear(self) -> None:
        self._effects.clear()

    def play(
        self,
        key: str,
        *,
        center: tuple[float, float] | None = None,
        size: tuple[int, int] | None = None,
        angle: float = 0.0,
        flip_x: bool = False,
        opacity: int = 255,
        loop: bool = False,
    ) -> None:
        spec = video_effect_spec(key)
        # Repeated boss patterns restart their named cue instead of stacking
        # several full-screen copies and washing out all gameplay readability.
        self._effects = [effect for effect in self._effects if effect.spec.key != key]
        self._effects.append(_PlayingEffect(
            spec=spec,
            frames=load_video_effect_frames(self._resources, key),
            center=center or (SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2),
            size=size or spec.default_size,
            angle=angle,
            flip_x=flip_x,
            opacity=max(0, min(255, opacity)),
            loop=loop,
        ))

    def play_debug(self, key: str) -> None:
        self.clear()
        spec = VIDEO_EFFECTS[key]
        self.play(key, center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2), size=spec.default_size)

    def update(self, dt: float) -> None:
        for effect in self._effects:
            effect.update(dt)
        self._effects = [effect for effect in self._effects if not effect.finished]

    def draw(self, surface: pygame.Surface) -> None:
        for effect in self._effects:
            image = effect.image()
            rect = image.get_rect(center=(int(effect.center[0]), int(effect.center[1])))
            flags = pygame.BLEND_RGBA_ADD if effect.spec.blend == "add" else 0
            surface.blit(image, rect, special_flags=flags)
