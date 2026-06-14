from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

import pygame

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from src.story.speakers import (
    DEFAULT_TEXT_COLOR,
    speaker_color,
    speaker_name,
    speaker_portrait,
)


@dataclass(frozen=True)
class DialoguePanelStyle:
    fill: tuple[int, int, int, int]
    border: tuple[int, int, int, int]
    name_fill: tuple[int, int, int, int]
    hint: tuple[int, int, int]
    text: tuple[int, int, int] = DEFAULT_TEXT_COLOR
    border_radius: int = 8


DARK_STYLE = DialoguePanelStyle(
    fill=(8, 10, 22, 232),
    border=(70, 105, 150, 210),
    name_fill=(7, 9, 18, 238),
    hint=(126, 146, 178),
)

LIGHT_STYLE = DialoguePanelStyle(
    fill=(255, 247, 220, 236),
    border=(126, 98, 70, 210),
    name_fill=(255, 240, 204, 242),
    hint=(120, 96, 72),
    text=(54, 42, 32),
)

COMBAT_RED_STYLE = DialoguePanelStyle(
    fill=(14, 4, 20, 224),
    border=(190, 72, 72, 214),
    name_fill=(18, 5, 20, 236),
    hint=(160, 126, 150),
)

COMBAT_BLUE_STYLE = DialoguePanelStyle(
    fill=(4, 12, 26, 224),
    border=(74, 132, 190, 214),
    name_fill=(4, 14, 28, 236),
    hint=(120, 158, 190),
    text=(210, 232, 255),
)

COMBAT_PURPLE_STYLE = DialoguePanelStyle(
    fill=(12, 4, 24, 226),
    border=(170, 72, 170, 214),
    name_fill=(15, 5, 28, 238),
    hint=(180, 132, 190),
    text=(255, 235, 245),
)


def _scaled_alpha(color: tuple[int, int, int, int], alpha: int) -> tuple[int, int, int, int]:
    return (*color[:3], min(color[3], alpha))


def _fit_font(resources, lines: tuple[str, ...], max_width: int, base_size: int, min_size: int):
    for size in range(base_size, min_size - 1, -2):
        font = resources.pixelfont(size)
        if all(font.size(line)[0] <= max_width for line in lines if line):
            return font
    return resources.pixelfont(min_size)


def _draw_outline_rect(surface: pygame.Surface, rect: pygame.Rect,
                       color: tuple[int, int, int, int], radius: int) -> None:
    pygame.draw.rect(surface, color, rect, 2, border_radius=radius)
    inner = rect.inflate(-6, -6)
    if inner.width > 0 and inner.height > 0:
        pygame.draw.rect(surface, (*color[:3], max(35, color[3] // 3)), inner, 1, border_radius=max(0, radius - 2))


def draw_story_panel(
    screen: pygame.Surface,
    resources,
    speaker: str,
    lines: tuple[str, ...],
    *,
    chars: int | None,
    page_index: int,
    total_pages: int,
    complete: bool,
    blink: float,
    hint_last: str,
    hint_next: str,
    style: DialoguePanelStyle = DARK_STYLE,
    show_portrait: bool = True,
    text_transform: Callable[[str], str] | None = None,
    text_color: tuple[int, int, int] | None = None,
    text_jitter: int = 0,
) -> None:
    rect = pygame.Rect(40, SCREEN_HEIGHT - 236, SCREEN_WIDTH - 80, 198)
    _draw_panel(screen, resources, speaker, lines, rect=rect, chars=chars,
                page_index=page_index, total_pages=total_pages, complete=complete,
                blink=blink, hint_last=hint_last, hint_next=hint_next, style=style,
                show_portrait=show_portrait, body_size=26, min_body_size=20,
                portrait_size=88, text_transform=text_transform,
                text_color=text_color, text_jitter=text_jitter)


def draw_combat_panel(
    screen: pygame.Surface,
    resources,
    speaker: str,
    lines: tuple[str, ...],
    *,
    page_index: int | None = None,
    total_pages: int | None = None,
    hint_text: str | None = None,
    style: DialoguePanelStyle = COMBAT_RED_STYLE,
    alpha: int = 255,
) -> None:
    rect = pygame.Rect(28, SCREEN_HEIGHT - 150, SCREEN_WIDTH - 56, 92)
    _draw_panel(screen, resources, speaker, lines, rect=rect, chars=None,
                page_index=page_index, total_pages=total_pages, complete=hint_text is not None,
                blink=0.0, hint_last=hint_text or "", hint_next=hint_text or "",
                style=style, show_portrait=True, body_size=26, min_body_size=20,
                portrait_size=68, alpha=alpha)


def _draw_panel(
    screen: pygame.Surface,
    resources,
    speaker: str,
    lines: tuple[str, ...],
    *,
    rect: pygame.Rect,
    chars: int | None,
    page_index: int | None,
    total_pages: int | None,
    complete: bool,
    blink: float,
    hint_last: str,
    hint_next: str,
    style: DialoguePanelStyle,
    show_portrait: bool,
    body_size: int,
    min_body_size: int,
    portrait_size: int,
    alpha: int = 255,
    text_transform: Callable[[str], str] | None = None,
    text_color: tuple[int, int, int] | None = None,
    text_jitter: int = 0,
) -> None:
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill(_scaled_alpha(style.fill, alpha))
    _draw_outline_rect(panel, panel.get_rect(), _scaled_alpha(style.border, alpha), style.border_radius)
    screen.blit(panel, rect.topleft)

    name = speaker_name(speaker)
    portrait_path = speaker_portrait(speaker) if show_portrait else None
    portrait_gap = portrait_size + 34 if portrait_path else 0
    text_x = rect.x + 24 + portrait_gap
    text_w = rect.w - 48 - portrait_gap
    compact = rect.h <= 110
    content_top = rect.y + (28 if compact else 42)
    footer_y = rect.y + rect.h - (24 if compact else 22)
    has_footer = bool((total_pages and total_pages > 1) or complete)
    content_bottom = footer_y - 8 if has_footer else rect.y + rect.h - 18
    content_h = max(0, content_bottom - content_top)

    if portrait_path:
        raw = resources.image(portrait_path)
        img = pygame.transform.smoothscale(raw, (portrait_size, portrait_size)).convert_alpha()
        img.set_alpha(alpha)
        px = rect.x + 24
        py = rect.y + (rect.h - portrait_size) // 2 + 6
        shadow = pygame.Surface((portrait_size + 8, portrait_size + 8), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, min(90, alpha)), shadow.get_rect(), border_radius=10)
        screen.blit(shadow, (px - 4, py - 2))
        screen.blit(img, (px, py))
        pygame.draw.rect(screen, (*speaker_color(speaker), min(230, alpha)),
                         (px, py, portrait_size, portrait_size), 2, border_radius=8)

    if name:
        name_font = resources.pixelfont(18)
        label = name_font.render(name, True, speaker_color(speaker))
        label.set_alpha(alpha)
        pad_x = 12
        plate = pygame.Rect(text_x - 4, rect.y - 16, label.get_width() + pad_x * 2, 30)
        ps = pygame.Surface(plate.size, pygame.SRCALPHA)
        ps.fill(_scaled_alpha(style.name_fill, alpha))
        pygame.draw.rect(ps, (*speaker_color(speaker), min(210, alpha)), ps.get_rect(), 2, border_radius=6)
        screen.blit(ps, plate.topleft)
        screen.blit(label, (plate.x + pad_x, plate.y + 5))

    visible_lines = _visible_lines(lines, chars)
    body_font = _fit_font(resources, visible_lines or lines, text_w, body_size, min_body_size)
    line_h = body_font.get_height() + (3 if compact else 4)
    total_h = len(lines) * line_h
    start_y = content_top + max(0, (content_h - total_h) // 2)

    for idx, line in enumerate(visible_lines):
        draw_line = text_transform(line) if text_transform is not None else line
        surf = body_font.render(draw_line, True, text_color or style.text)
        surf.set_alpha(alpha)
        jitter_x = random.randint(-text_jitter, text_jitter) if text_jitter > 0 else 0
        screen.blit(surf, (text_x + jitter_x, start_y + idx * line_h))

    if total_pages and total_pages > 1:
        dot_font = resources.pixelfont(16)
        if total_pages > 8:
            indicator = f"{(page_index or 0) + 1}/{total_pages}"
        else:
            indicator = "  ".join("●" if i == page_index else "○" for i in range(total_pages))
        dot = dot_font.render(indicator, True, style.hint)
        dot.set_alpha(alpha)
        indicator_x = text_x if compact and portrait_path else rect.x + 24
        screen.blit(dot, (indicator_x, footer_y))

    if complete and int(blink * 2) % 2 == 0:
        hint_font = resources.pixelfont(16)
        is_last = bool(total_pages is not None and page_index == total_pages - 1)
        hint_text = hint_last if is_last else hint_next
        hint = hint_font.render(hint_text, True, style.hint)
        hint.set_alpha(alpha)
        screen.blit(hint, (rect.right - hint.get_width() - 24, footer_y))


def _visible_lines(lines: tuple[str, ...], chars: int | None) -> tuple[str, ...]:
    if chars is None:
        return lines
    out: list[str] = []
    remaining = chars
    for line in lines:
        if remaining <= 0:
            break
        visible = line[:remaining]
        remaining -= len(line)
        if visible:
            out.append(visible)
    return tuple(out)
