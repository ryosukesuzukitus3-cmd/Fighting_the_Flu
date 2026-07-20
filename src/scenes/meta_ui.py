"""Shared presentation helpers for non-gameplay screens.

The title screen owns the game's strongest visual language: a dark fever-toned
background, warm highlights, and restrained pixel ornament.  Meta screens use
these helpers so they feel related without forcing every scene into one accent.
"""
from __future__ import annotations

import pygame

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH


BG_TOP = (24, 12, 26)
BG_BOTTOM = (6, 8, 18)
PANEL_FILL = (10, 13, 27, 224)
TEXT = (232, 230, 238)
TEXT_MUTED = (166, 170, 188)
TEXT_DIM = (126, 132, 154)
ACCENT_GOLD = (255, 214, 116)


def draw_meta_background(
    screen: pygame.Surface,
    *,
    accent: tuple[int, int, int] = ACCENT_GOLD,
) -> None:
    """Draw the common dark fever-space background used by meta screens."""
    for y in range(SCREEN_HEIGHT):
        t = y / max(1, SCREEN_HEIGHT - 1)
        color = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        pygame.draw.line(screen, color, (0, y), (SCREEN_WIDTH, y))

    glow = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    for radius, alpha in ((330, 10), (240, 13), (150, 16)):
        pygame.draw.circle(glow, (*accent, alpha), (SCREEN_WIDTH // 2, 120), radius)
    screen.blit(glow, (0, 0))

    # Pixel-grid ornament: visible enough to bind the screens, quiet enough not
    # to compete with tables and menu text.
    grid = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    for x in range(0, SCREEN_WIDTH, 80):
        pygame.draw.line(grid, (120, 112, 150, 12), (x, 0), (x, SCREEN_HEIGHT))
    for y in range(0, SCREEN_HEIGHT, 60):
        pygame.draw.line(grid, (120, 112, 150, 10), (0, y), (SCREEN_WIDTH, y))
    screen.blit(grid, (0, 0))


def draw_meta_panel(
    screen: pygame.Surface,
    rect: pygame.Rect,
    *,
    accent: tuple[int, int, int] = ACCENT_GOLD,
    fill: tuple[int, int, int, int] = PANEL_FILL,
) -> None:
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill(fill)
    pygame.draw.rect(panel, (*accent, 150), panel.get_rect(), 2, border_radius=8)
    pygame.draw.line(panel, (*accent, 90), (12, 8), (rect.w - 12, 8), 2)
    screen.blit(panel, rect.topleft)


def draw_meta_title(
    screen: pygame.Surface,
    font: pygame.font.Font,
    title: str,
    *,
    accent: tuple[int, int, int] = ACCENT_GOLD,
    y: int = 38,
    eyebrow: str | None = None,
    eyebrow_font: pygame.font.Font | None = None,
) -> None:
    cx = SCREEN_WIDTH // 2
    if eyebrow and eyebrow_font:
        label = eyebrow_font.render(eyebrow, True, TEXT_MUTED)
        screen.blit(label, (cx - label.get_width() // 2, y - 22))
    shadow = font.render(title, True, (24, 8, 16))
    text = font.render(title, True, accent)
    x = cx - text.get_width() // 2
    screen.blit(shadow, (x + 2, y + 3))
    screen.blit(text, (x, y))
    line_y = y + text.get_height() + 8
    pygame.draw.line(screen, (*accent,), (cx - 92, line_y), (cx + 92, line_y), 2)


def draw_meta_footer(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    *,
    y: int = SCREEN_HEIGHT - 42,
) -> None:
    """Draw instructions at readable contrast in the shared footer rail."""
    rail = pygame.Surface((SCREEN_WIDTH, 48), pygame.SRCALPHA)
    rail.fill((3, 5, 13, 205))
    screen.blit(rail, (0, SCREEN_HEIGHT - 48))
    hint = font.render(text, True, TEXT_MUTED)
    screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, y))


def draw_selection_marker(
    screen: pygame.Surface,
    rect: pygame.Rect,
    *,
    selected: bool,
    accent: tuple[int, int, int] = ACCENT_GOLD,
) -> None:
    if not selected:
        return
    marker = pygame.Surface(rect.size, pygame.SRCALPHA)
    marker.fill((*accent, 18))
    pygame.draw.rect(marker, (*accent, 190), marker.get_rect(), 2, border_radius=5)
    screen.blit(marker, rect.topleft)
