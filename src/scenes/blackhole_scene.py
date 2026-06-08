from __future__ import annotations

import math
import random
from typing import Callable

import pygame

from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.entities.background import ScrollingBackground
from src.entities.companion import Karonaru
from src.entities.player import Player
from src.story.lines import Page
from src.story.speakers import (
    DEFAULT_TEXT_COLOR,
    speaker_color,
    speaker_name,
    speaker_portrait,
)

_TYPEWRITER_SPEED = 34.0
_CENTER = (SCREEN_WIDTH * 0.64, SCREEN_HEIGHT * 0.46)


class BlackholeScene(Scene):
    """Stage3 after-boss event with in-stage actors and a blackhole."""

    def __init__(self, game, pages: list[Page], on_complete: Callable[[], None]) -> None:
        super().__init__(game)
        self._pages = list(pages)
        self._on_complete = on_complete

    def on_enter(self) -> None:
        self._bg = ScrollingBackground(3)
        self._player = Player(self.game)
        self._player.sx = 150.0
        self._player.sy = 300.0
        self._player.rect.topleft = (int(self._player.sx), int(self._player.sy))

        self._karonaru = Karonaru(self.game)
        self._karonaru.sx = 95.0
        self._karonaru.sy = 330.0
        self._karonaru.rect.center = (int(self._karonaru.sx), int(self._karonaru.sy))

        self._font_name = self.game.resources.pixelfont(20)
        self._font_body = self.game.resources.pixelfont(25)
        self._font_hint = self.game.resources.pixelfont(16)
        self._page = 0
        self._chars = 0.0
        self._time = 0.0
        self._shake_t = 0.0
        self._flash_t = 0.0
        self._fade_in_t = 0.45
        self._fade_out_t = 0.0
        self._fade_out = False
        self._finished = False
        self.game.sound.stop_bgm(fadeout_ms=500)
        self._enter_page()

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        self._time += dt
        self._chars += _TYPEWRITER_SPEED * dt
        self._shake_t = max(0.0, self._shake_t - dt)
        self._flash_t = max(0.0, self._flash_t - dt)
        self._fade_in_t = max(0.0, self._fade_in_t - dt)

        if self._fade_out:
            self._fade_out_t += dt
            if self._fade_out_t >= 0.5 and not self._finished:
                self._finished = True
                self._on_complete()
            return

        inp = self.game.input
        advance = (
            inp.is_held_with_repeat(pygame.K_RETURN, 0.25, 0.12)
            or inp.is_held_with_repeat(pygame.K_SPACE, 0.25, 0.12)
        )
        if advance:
            if not self._is_text_complete():
                self._chars = float(self._total_chars() + 1)
            elif self._page < len(self._pages) - 1:
                self._page += 1
                self._enter_page()
            else:
                self._begin_finish()
        if inp.is_just_pressed(pygame.K_x):
            self._begin_finish()

    def _enter_page(self) -> None:
        self._chars = 0.0
        if not self._pages:
            return
        pg = self._cur()
        if pg.se:
            self.game.sound.play_se_alias(pg.se)
        if "shake" in pg.fx or "blackhole" in pg.fx:
            self._shake_t = 0.5
        if "white_particle" in pg.fx or "light" in pg.fx:
            self._flash_t = 0.35

    def _cur(self) -> Page:
        return self._pages[self._page]

    def _total_chars(self) -> int:
        return sum(len(line) for line in self._cur().lines)

    def _is_text_complete(self) -> bool:
        return int(self._chars) >= self._total_chars()

    def _begin_finish(self) -> None:
        if not self._fade_out:
            self._fade_out = True
            self._fade_out_t = 0.0

    def _event_ratio(self) -> float:
        if not self._pages:
            return 1.0
        return self._page / max(1, len(self._pages) - 1)

    def _actor_positions(self) -> tuple[tuple[float, float], tuple[float, float], float]:
        r = self._event_ratio()
        cx, cy = _CENTER
        wobble = math.sin(self._time * 7.0) * min(18.0, 5.0 + r * 22.0)

        if r < 0.28:
            t = r / 0.28
            px = 145 + t * 40
            py = 315 + wobble * 0.15
            kx = 88 + t * 90
            ky = 346 + wobble * 0.2
            ka = 255
        elif r < 0.58:
            t = (r - 0.28) / 0.30
            px = 185 + t * 120
            py = 315 + wobble * 0.4
            kx = 178 + t * 210
            ky = 346 - t * 58 + wobble * 0.35
            ka = 255
        elif r < 0.78:
            t = (r - 0.58) / 0.20
            px = 305 - t * 90
            py = 315 + t * 35 + wobble * 0.5
            kx = 388 + t * (cx - 388)
            ky = 288 + t * (cy - 288)
            ka = int(255 * (1.0 - t * 0.75))
        else:
            t = (r - 0.78) / 0.22
            px = 210 - t * 35
            py = 350 + wobble * 0.15
            kx = cx
            ky = cy
            ka = 0
        return (px, py), (kx, ky), max(0.0, min(255.0, ka))

    def draw(self, screen: pygame.Surface) -> None:
        self._bg.draw(screen, self._time * 42.0)
        self._draw_blackhole(screen)

        (px, py), (kx, ky), karonaru_alpha = self._actor_positions()
        self._player.sx = px
        self._player.sy = py
        self._player.rect.topleft = (int(px), int(py))
        self._draw_pull_lines(screen, self._player.rect.center, karonaru_alpha > 0)
        self._player.draw(screen)

        if karonaru_alpha > 0:
            self._karonaru.sx = kx
            self._karonaru.sy = ky
            self._karonaru.rect.center = (int(kx), int(ky))
            if karonaru_alpha < 255:
                img = self._karonaru.image.copy()
                img.set_alpha(int(karonaru_alpha))
                screen.blit(img, self._karonaru.rect)
            else:
                self._karonaru.draw(screen)

        self._draw_dialogue(screen)

        if self._flash_t > 0:
            a = int(210 * self._flash_t / 0.35)
            flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            flash.fill((255, 255, 255, a))
            screen.blit(flash, (0, 0))

        fade_a = 0
        if self._fade_in_t > 0:
            fade_a = int(255 * self._fade_in_t / 0.45)
        elif self._fade_out:
            fade_a = int(255 * min(1.0, self._fade_out_t / 0.5))
        if fade_a:
            fade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            fade.set_alpha(fade_a)
            fade.fill((0, 0, 0))
            screen.blit(fade, (0, 0))

    def _draw_blackhole(self, screen: pygame.Surface) -> None:
        cx, cy = int(_CENTER[0]), int(_CENTER[1])
        r = self._event_ratio()
        t = self._time
        strength = min(1.0, 0.18 + r * 1.2)
        radius = int(34 + 95 * strength)

        for i in range(8, 0, -1):
            rr = radius + i * 28
            ring = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
            pygame.draw.circle(ring, (64, 24, 92, max(0, 56 - i * 5)), (rr, rr), rr)
            screen.blit(ring, (cx - rr, cy - rr))

        for arm in range(6):
            pts = []
            for k in range(34):
                ang = t * (1.8 + strength) + arm * math.tau / 6 + k * 0.26
                rad = 18 + k * (5.0 + strength * 5.5)
                pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
            pygame.draw.lines(screen, (160, 90, 210), False, pts, 2)

        for n in range(80):
            seed = n * 0.37
            phase = (t * (0.28 + (n % 7) * 0.03) + seed) % 1.0
            ang = t * (0.9 + (n % 5) * 0.15) + seed * math.tau
            rad = (1.0 - phase) * (340 - 110 * strength) + 10
            alpha = int(230 * phase * strength)
            x = int(cx + math.cos(ang) * rad)
            y = int(cy + math.sin(ang) * rad)
            pygame.draw.circle(screen, (225, 210, 255, alpha), (x, y), 1 + (n % 2))

        pygame.draw.circle(screen, (1, 0, 6), (cx, cy), int(32 + 20 * strength))
        pygame.draw.circle(screen, (92, 45, 130), (cx, cy), int(32 + 20 * strength), 2)

    def _draw_pull_lines(self, screen: pygame.Surface, player_center: tuple[int, int], show_companion: bool) -> None:
        cx, cy = _CENTER
        targets = [player_center]
        if show_companion:
            targets.append(self._karonaru.rect.center)
        for tx, ty in targets:
            for i in range(4):
                off = math.sin(self._time * 5.0 + i) * 10
                pygame.draw.line(
                    screen,
                    (150, 80, 190),
                    (int(tx + off), int(ty - 12 + i * 8)),
                    (int(cx), int(cy)),
                    1,
                )

    def _draw_dialogue(self, screen: pygame.Surface) -> None:
        if not self._pages:
            return
        pg = self._cur()
        box_h = 130
        box_y = SCREEN_HEIGHT - box_h - 16
        box = pygame.Surface((SCREEN_WIDTH - 36, box_h), pygame.SRCALPHA)
        box.fill((8, 4, 18, 220))
        pygame.draw.rect(box, (130, 80, 180, 220), box.get_rect(), 2, border_radius=6)
        screen.blit(box, (18, box_y))

        x = 34
        portrait = speaker_portrait(pg.speaker)
        if portrait:
            try:
                raw = self.game.resources.image(portrait)
                pimg = pygame.transform.smoothscale(raw, (62, 62)).convert_alpha()
                screen.blit(pimg, (x, box_y + 16))
                pygame.draw.rect(screen, speaker_color(pg.speaker), (x, box_y + 16, 62, 62), 2)
                x += 78
            except Exception:
                pass

        name = speaker_name(pg.speaker)
        if name:
            ns = self._font_name.render(name, True, speaker_color(pg.speaker))
            screen.blit(ns, (x, box_y + 14))

        chars_left = int(self._chars)
        y = box_y + 44
        for line in pg.lines:
            if chars_left <= 0:
                break
            visible = line[:chars_left]
            chars_left -= len(line)
            if visible:
                surf = self._font_body.render(visible, True, DEFAULT_TEXT_COLOR)
                screen.blit(surf, (x, y))
            y += 30

        progress = f"{self._page + 1}/{len(self._pages)}"
        hint = "ENTER" if self._is_text_complete() else progress
        hs = self._font_hint.render(hint, True, (190, 160, 220))
        screen.blit(hs, (SCREEN_WIDTH - hs.get_width() - 30, box_y + box_h - 24))
