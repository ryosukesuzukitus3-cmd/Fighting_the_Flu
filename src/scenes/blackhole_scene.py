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
    KARONARU,
    speaker_color,
    speaker_name,
    speaker_portrait,
)

_TYPEWRITER_SPEED = 34.0
_TYPE_SE_INTERVAL = 0.045
_TYPE_SE_VOLUME = 0.16
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
        self._type_se_cooldown = 0.0
        self._time = 0.0
        self._phase = self._phase_for_page()
        self._phase_time = 0.0
        self._noise_level = 0.0
        self._player_pos = (150.0, 300.0)
        self._karonaru_pos = (95.0, 330.0)
        self._karonaru_alpha = 255.0
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
        self._phase_time += dt
        previous_chars = min(int(self._chars), self._total_chars())
        self._chars += _TYPEWRITER_SPEED * dt
        self._tick_type_sound(dt, previous_chars)
        self._shake_t = max(0.0, self._shake_t - dt)
        self._flash_t = max(0.0, self._flash_t - dt)
        self._fade_in_t = max(0.0, self._fade_in_t - dt)
        self._update_actor_motion(dt)

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
        self._type_se_cooldown = 0.0
        if not self._pages:
            return
        new_phase = self._phase_for_page()
        if new_phase != self._phase:
            self._phase = new_phase
            self._phase_time = 0.0
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

    def _tick_type_sound(self, dt: float, previous_chars: int) -> None:
        self._type_se_cooldown = max(0.0, self._type_se_cooldown - dt)
        current_chars = min(int(self._chars), self._total_chars())
        if current_chars > previous_chars and self._type_se_cooldown <= 0.0:
            self.game.sound.play_se_alias("SE_TYPE", volume=_TYPE_SE_VOLUME)
            self._type_se_cooldown = _TYPE_SE_INTERVAL

    def _begin_finish(self) -> None:
        if not self._fade_out:
            self._fade_out = True
            self._fade_out_t = 0.0

    def _event_ratio(self) -> float:
        if not self._pages:
            return 1.0
        return self._page / max(1, len(self._pages) - 1)

    def _phase_for_page(self) -> str:
        r = self._event_ratio()
        if r < 0.52:
            return "balance"
        if r < 0.68:
            return "reaction"
        if r < 0.88:
            return "fall"
        return "silence"

    def _update_actor_motion(self, dt: float) -> None:
        wobble = math.sin(self._time * 4.5) * 2.2
        if self._phase == "balance":
            p_target = (164.0, 306.0 + wobble)
            k_target = (130.0, 334.0 - wobble * 0.4)
            alpha_target = 255.0
            noise_target = 0.0
            rate = 0.55
        elif self._phase == "reaction":
            pulse = min(1.0, self._phase_time / 0.45)
            p_target = (126.0 - 10.0 * pulse, 326.0 + wobble)
            k_target = (222.0 + 20.0 * pulse, 306.0 - wobble * 0.3)
            alpha_target = 255.0
            noise_target = 0.12
            rate = 1.9
        elif self._phase == "fall":
            fall = min(1.0, self._phase_time / 5.8)
            p_target = (122.0, 334.0 + wobble * 0.35)
            k_target = (
                self._karonaru_pos[0] + (_CENTER[0] - self._karonaru_pos[0]) * 0.06,
                self._karonaru_pos[1] + (_CENTER[1] - self._karonaru_pos[1]) * 0.06,
            )
            alpha_target = 255.0 * (1.0 - fall)
            noise_target = 0.20 + 0.75 * fall
            rate = 1.15
        else:
            p_target = (122.0, 336.0)
            k_target = _CENTER
            alpha_target = 0.0
            noise_target = 1.0
            rate = 1.8

        blend = 1.0 - math.exp(-rate * dt)
        px, py = self._player_pos
        kx, ky = self._karonaru_pos
        self._player_pos = (
            px + (p_target[0] - px) * blend,
            py + (p_target[1] - py) * blend,
        )
        self._karonaru_pos = (
            kx + (k_target[0] - kx) * blend,
            ky + (k_target[1] - ky) * blend,
        )
        self._karonaru_alpha += (alpha_target - self._karonaru_alpha) * blend
        self._noise_level += (noise_target - self._noise_level) * blend

    def draw(self, screen: pygame.Surface) -> None:
        self._bg.draw(screen, self._time * 42.0)
        self._draw_blackhole(screen)

        px, py = self._player_pos
        kx, ky = self._karonaru_pos
        karonaru_alpha = max(0.0, min(255.0, self._karonaru_alpha))
        self._player.sx = px
        self._player.sy = py
        self._player.rect.topleft = (int(px), int(py))
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
        strength = min(1.0, 0.28 + r * 0.9)
        disk = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for i in range(9, 0, -1):
            rr = int((72 + i * 44) * strength)
            alpha = max(0, 34 - i * 2)
            pygame.draw.circle(vignette, (20, 5, 38, alpha), (cx, cy), rr)
        screen.blit(vignette, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        for i in range(14):
            rx = int((86 + i * 10) * strength)
            ry = max(12, int(rx * (0.25 + i * 0.006)))
            rect = pygame.Rect(cx - rx, cy - ry, rx * 2, ry * 2)
            start = (t * (1.2 + i * 0.03) + i * 0.37) % math.tau
            span = math.pi * (0.34 + (i % 3) * 0.05)
            color = (
                120 + min(95, i * 8),
                70 + min(95, i * 5),
                185 + min(55, i * 3),
                max(18, 112 - i * 5),
            )
            pygame.draw.arc(disk, color, rect, start, start + span, 3)
            pygame.draw.arc(disk, (230, 180, 255, max(10, 60 - i * 3)), rect,
                            start + math.pi, start + math.pi + span * 0.72, 2)

        for n in range(110):
            seed = n * 0.611
            phase = (t * (0.16 + (n % 9) * 0.012) + seed) % 1.0
            ang = t * (0.7 + (n % 5) * 0.08) + seed * math.tau
            rad = (1.0 - phase) * (310 - 95 * strength) + 18
            squash = 0.42 + 0.18 * math.sin(seed * 4.0)
            alpha = int((34 + 180 * phase) * strength)
            x = int(cx + math.cos(ang) * rad)
            y = int(cy + math.sin(ang) * rad * squash)
            pygame.draw.circle(disk, (230, 220, 255, alpha), (x, y), 1 + (n % 2))

        screen.blit(disk, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        core_r = int(30 + 25 * strength)
        core = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for i in range(5, 0, -1):
            rr = core_r + i * 6
            pygame.draw.circle(core, (130, 80, 180, 26), (cx, cy), rr)
        screen.blit(core, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        pygame.draw.circle(screen, (0, 0, 4), (cx, cy), core_r)
        pygame.draw.circle(screen, (205, 165, 255), (cx, cy), core_r + 4, 2)
        pygame.draw.circle(screen, (60, 20, 100), (cx, cy), core_r + 12, 1)

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
        if self._noise_level > 0.03:
            self._draw_signal_noise(screen, pygame.Rect(18, box_y, SCREEN_WIDTH - 36, box_h))

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
                if pg.speaker == KARONARU and self._noise_level > 0.1:
                    visible = self._noisy_text(visible, self._noise_level)
                surf = self._font_body.render(visible, True, DEFAULT_TEXT_COLOR)
                jitter = int(random.uniform(-2, 3) * self._noise_level)
                screen.blit(surf, (x + jitter, y))
            y += 30

        progress = f"{self._page + 1}/{len(self._pages)}"
        hint = "ENTER" if self._is_text_complete() else progress
        hs = self._font_hint.render(hint, True, (190, 160, 220))
        screen.blit(hs, (SCREEN_WIDTH - hs.get_width() - 30, box_y + box_h - 24))

    def _draw_signal_noise(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        noise = max(0.0, min(1.0, self._noise_level))
        layer = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        for y in range(3, rect.height, 9):
            alpha = int(16 + 40 * noise * random.random())
            pygame.draw.line(layer, (210, 190, 255, alpha), (0, y), (rect.width, y), 1)
        specks = int(10 + 42 * noise)
        for _ in range(specks):
            x = random.randrange(0, rect.width)
            y = random.randrange(0, rect.height)
            w = random.randrange(1, 8)
            alpha = int(45 + 130 * noise * random.random())
            pygame.draw.rect(layer, (230, 230, 255, alpha), (x, y, w, 1))
        screen.blit(layer, rect.topleft, special_flags=pygame.BLEND_RGBA_ADD)

    def _noisy_text(self, text: str, noise: float) -> str:
        keep = max(0.0, min(0.28, noise * 0.28))
        out: list[str] = []
        for ch in text:
            if ch.isspace() or random.random() > keep:
                out.append(ch)
            else:
                out.append(random.choice(("#", ".", "…")))
        return "".join(out)
