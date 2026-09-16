"""Pixel menus: restrained color, open spacing, and one clear cursor."""
from __future__ import annotations

import pygame
from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH

BG = (16, 16, 18)
PANEL_FILL = (*BG, 245)
TEXT = (238, 232, 219)
TEXT_MUTED = (184, 181, 176)
TEXT_DIM = (130, 128, 125)
ACCENT_CORAL = (222, 145, 120)
ACCENT_MINT = (139, 205, 177)


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


def draw_meta_background(screen: pygame.Surface) -> None:
    screen.fill(BG)


def draw_meta_panel(screen: pygame.Surface, rect: pygame.Rect, *,
                    fill=PANEL_FILL) -> None:
    """A flat backing for text over scenery; menus on BG need no panel."""
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill(fill)
    screen.blit(panel, rect.topleft)


def draw_meta_title(screen: pygame.Surface, font: pygame.font.Font, title: str, *,
                    accent=TEXT, y: int = 38, eyebrow: str | None = None,
                    eyebrow_font: pygame.font.Font | None = None) -> None:
    cx = SCREEN_WIDTH // 2
    if eyebrow and eyebrow_font:
        label = eyebrow_font.render(fit_text(eyebrow_font, eyebrow, SCREEN_WIDTH - 80), False, TEXT_MUTED)
        screen.blit(label, (cx - label.get_width() // 2, y - 24))
    label = fit_text(font, title, SCREEN_WIDTH - 80)
    text = font.render(label, False, accent)
    screen.blit(text, (cx - text.get_width() // 2, y))


def draw_meta_footer(screen: pygame.Surface, font: pygame.font.Font, text: str, *,
                     y: int | None = None) -> None:
    """Unframed hints, still wrapping unusually long customized key names."""
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
    footer_y = SCREEN_HEIGHT - height
    text_y = footer_y + (height - len(lines) * line_h) // 2 if y is None else max(footer_y + 6, min(y, SCREEN_HEIGHT - len(lines) * line_h))
    for line in lines:
        hint = font.render(line, False, TEXT_MUTED)
        screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, text_y))
        text_y += line_h


def draw_pixel_cursor(screen: pygame.Surface, x: int, center_y: int, *,
                      color=ACCENT_CORAL, scale: int = 2) -> None:
    """A stepped arrow drawn on the pixel grid, with no enclosing selection box."""
    for row, width in enumerate((1, 2, 3, 2, 1)):
        pygame.draw.rect(screen, color,
                         (x, center_y - 5 * scale // 2 + row * scale, width * scale, scale))


def draw_selection_marker(screen: pygame.Surface, rect: pygame.Rect, *,
                          selected: bool, accent=ACCENT_CORAL) -> None:
    if selected:
        draw_pixel_cursor(screen, rect.x + 4, rect.centery, color=accent)
