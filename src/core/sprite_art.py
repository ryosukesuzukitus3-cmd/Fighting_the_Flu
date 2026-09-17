"""Fit character art without stretching faces or letting faint glow set its size."""
from functools import lru_cache

import pygame


@lru_cache(maxsize=96)
def _fitted_art(source, size, alpha_threshold, pixel_grid):
    bounds = source.get_bounding_rect(min_alpha=alpha_threshold)
    canvas = pygame.Surface(size, pygame.SRCALPHA)
    if not bounds.width or not bounds.height:
        return canvas
    art = source.subsurface(bounds)
    scale = min(size[0] / bounds.width, size[1] / bounds.height)
    target = (max(1, round(bounds.width * scale)), max(1, round(bounds.height * scale)))
    if scale >= 1:
        # Keep the original pixels crisp when enlarging old, small portraits.
        fitted = pygame.transform.scale(art, target)
    elif pixel_grid > 1:
        # Sample large illustrations once onto the game's two-pixel grid.
        sample_size = tuple(max(1, n // pixel_grid) for n in target)
        sampled = pygame.transform.smoothscale(art, sample_size)
        fitted = pygame.transform.scale(sampled, tuple(n * pixel_grid for n in sample_size))
    else:
        fitted = pygame.transform.smoothscale(art, target)
    canvas.blit(fitted, fitted.get_rect(center=canvas.get_rect().center))
    return canvas


def fit_character_art(source, size, *, alpha_threshold=32, pixel_grid=1):
    """Return a mutable copy, leaving both source and cached art untouched."""
    return _fitted_art(source, tuple(size), alpha_threshold, pixel_grid).copy()
