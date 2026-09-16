"""Shared, readable presentation for menus and modal screens."""
from __future__ import annotations

from functools import lru_cache
import pygame
from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH

BG_TOP = (20, 22, 39)
BG_BOTTOM = (7, 11, 22)
PANEL_FILL = (12, 18, 33, 242)
TEXT = (237, 239, 247)
TEXT_MUTED = (183, 194, 215)
TEXT_DIM = (146, 160, 185)
ACCENT_GOLD = (255, 214, 116)


def fit_text(font: pygame.font.Font, text: str, max_width: int) -> str:
    """Ellipsize an auxiliary label without shrinking its font."""
    if font.size(text)[0] <= max_width:
        return text
    if font.size("…")[0] > max_width:
        return ""
    while text and font.size(text + "…")[0] > max_width:
        text = text[:-1]
    return text + "…"


def wrap_text(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """Wrap Japanese or Latin text by measured width, preserving every character."""
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for char in paragraph:
            if line and font.size(line + char)[0] > max_width:
                lines.append(line)
                line = ""
            line += char
        lines.append(line)
    return lines


@lru_cache(maxsize=16)
def _background(accent: tuple[int, int, int]) -> pygame.Surface:
    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    for y in range(SCREEN_HEIGHT):
        t = y / max(1, SCREEN_HEIGHT - 1)
        color = tuple(round(BG_TOP[i] * (1 - t) + BG_BOTTOM[i] * t) for i in range(3))
        pygame.draw.line(surface, color, (0, y), (SCREEN_WIDTH, y))
    glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for radius in range(430, 0, -3):
        alpha = round(20 * (1 - radius / 430) ** 1.7)
        pygame.draw.circle(glow, (*accent, alpha), (SCREEN_WIDTH // 2, 70), radius)
    surface.blit(glow, (0, 0))
    grid = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for x in range(0, SCREEN_WIDTH, 80):
        pygame.draw.line(grid, (170, 192, 225, 6), (x, 0), (x, SCREEN_HEIGHT))
    for y in range(0, SCREEN_HEIGHT, 60):
        pygame.draw.line(grid, (170, 192, 225, 6), (0, y), (SCREEN_WIDTH, y))
    surface.blit(grid, (0, 0))
    return surface


def draw_meta_background(screen: pygame.Surface, *, accent=ACCENT_GOLD) -> None:
    screen.blit(_background(tuple(accent)), (0, 0))


def draw_meta_panel(screen: pygame.Surface, rect: pygame.Rect, *,
                    accent=ACCENT_GOLD, fill=PANEL_FILL) -> None:
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, fill, panel.get_rect(), border_radius=8)
    pygame.draw.rect(panel, (*accent, 90), panel.get_rect(), 1, border_radius=8)
    screen.blit(panel, rect.topleft)


def draw_meta_title(screen: pygame.Surface, font: pygame.font.Font, title: str, *,
                    accent=ACCENT_GOLD, y: int = 38, eyebrow: str | None = None,
                    eyebrow_font: pygame.font.Font | None = None) -> None:
    cx = SCREEN_WIDTH // 2
    if eyebrow and eyebrow_font:
        label = eyebrow_font.render(fit_text(eyebrow_font, eyebrow, SCREEN_WIDTH - 80), True, TEXT_MUTED)
        screen.blit(label, (cx - label.get_width() // 2, y - 24))
    label = fit_text(font, title, SCREEN_WIDTH - 80)
    shadow = font.render(label, True, (3, 6, 15))
    text = font.render(label, True, accent)
    x = cx - text.get_width() // 2
    screen.blit(shadow, (x + 2, y + 3))
    screen.blit(text, (x, y))
    line_y = y + text.get_height() + 10
    pygame.draw.line(screen, accent, (cx - 30, line_y), (cx + 30, line_y), 2)


def draw_meta_footer(screen: pygame.Surface, font: pygame.font.Font, text: str, *,
                     y: int | None = None) -> None:
    """Keep instructions legible, wrapping long customized key names."""
    lines = []
    current = ""
    for chunk in text.split("   "):
        candidate = (current + "   " + chunk) if current else chunk
        if current and font.size(candidate)[0] > SCREEN_WIDTH - 48:
            lines.extend(wrap_text(font, current, SCREEN_WIDTH - 48))
            current = chunk
        else:
            current = candidate
    lines.extend(wrap_text(font, current, SCREEN_WIDTH - 48))
    line_h = font.get_linesize() + 2
    height = max(48, len(lines) * line_h + 16)
    rail_y = SCREEN_HEIGHT - height
    rail = pygame.Surface((SCREEN_WIDTH, height), pygame.SRCALPHA)
    rail.fill((5, 9, 18, 245))
    pygame.draw.line(rail, (55, 68, 91), (24, 0), (SCREEN_WIDTH - 24, 0))
    screen.blit(rail, (0, rail_y))
    text_y = rail_y + (height - len(lines) * line_h) // 2 if y is None else max(rail_y + 6, min(y, SCREEN_HEIGHT - len(lines) * line_h))
    for line in lines:
        hint = font.render(line, True, TEXT_MUTED)
        screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, text_y))
        text_y += line_h


def draw_selection_marker(screen: pygame.Surface, rect: pygame.Rect, *,
                          selected: bool, accent=ACCENT_GOLD) -> None:
    if not selected:
        return
    marker = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(marker, (*accent, 24), marker.get_rect(), border_radius=5)
    pygame.draw.rect(marker, (*accent, 140), marker.get_rect(), 1, border_radius=5)
    pygame.draw.rect(marker, (*accent, 255), (0, 5, 3, max(1, rect.h - 10)), border_radius=1)
    screen.blit(marker, rect.topleft)
