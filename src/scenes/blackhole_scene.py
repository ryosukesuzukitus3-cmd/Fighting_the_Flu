from __future__ import annotations

import math
from typing import Callable

import pygame

from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.core.sprite_art import fit_character_art
from src.entities.companion import Karonaru
from src.entities.player import Player
from src.story.aliases import bgm_path
from src.story.lines import Page
from src.story.speakers import SAWAGUCHI, KARONARU, speaker_portrait

_TYPEWRITER_SPEED = 34.0
_TYPE_SE_INTERVAL = 0.045
_TYPE_SE_VOLUME = 0.12
_CENTER = (566.0, 181.0)
_HORIZON = (470.0, 216.0)
_PHASE_TAGS = {
    "bh_balance": "balance", "bh_pull": "pull", "bh_resolve": "resolve",
    "bh_charge": "charge",
    "bh_push": "push", "bh_fall": "fall", "bh_hold": "hold",
    "bh_farewell": "farewell", "bh_gone": "gone", "bh_silence": "silence",
}
_MIN_PHASE_TIME = {"charge": 1.2, "push": 1.25, "fall": 1.6, "gone": 1.1, "silence": 0.8}
_MOTION_TIME = {
    "balance": 1.5, "pull": 2.0, "resolve": 1.0, "charge": 1.2, "push": 1.25,
    "fall": 2.5, "hold": 0.7, "farewell": 0.45, "gone": 1.1, "silence": 0.8,
}


def _lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _curve(start, control, end, t):
    return _lerp(_lerp(start, control, t), _lerp(control, end, t), t)


class BlackholeScene(Scene):
    """A rescue and farewell, timed by authored cues rather than page counts."""

    def __init__(self, game, pages: list[Page], on_complete: Callable[[], None]) -> None:
        super().__init__(game)
        self._pages = list(pages)
        self._on_complete = on_complete

    def on_enter(self) -> None:
        raw = self.game.resources.image("graphic/cinematics/blackhole.png")
        self._background = pygame.transform.scale(raw, (400, 300))
        self._player = Player(self.game)
        self._player.image = fit_character_art(
            self.game.resources.image(speaker_portrait(SAWAGUCHI)), (74, 96), pixel_grid=2,
        )
        self._player.rect = self._player.image.get_rect()
        self._karonaru = Karonaru(self.game)
        self._karonaru.image = fit_character_art(
            self.game.resources.image(speaker_portrait(KARONARU, facing="left")), (66, 100), pixel_grid=2,
        )
        self._karonaru.rect = self._karonaru.image.get_rect()
        self._page = 0
        self._chars = 0.0
        self._type_se_cooldown = 0.0
        self._time = 0.0
        self._phase = ""
        self._phase_time = 0.0
        self._player_pos = (196.0, 244.0)
        self._karonaru_pos = (126.0, 256.0)
        self._karonaru_alpha = 255.0
        self._karonaru_scale = 1.0
        self._shake_t = 0.0
        self._fade_in_t = 0.6
        self._fade_out_t = 0.0
        self._fade_out = False
        self._finished = False
        self._quiet = False
        self._rescue_origin = (336.0, 230.0)
        self._rescue_age = None
        self._rescue_fx = pygame.Surface((400, 171), pygame.SRCALPHA)
        self._advance_queued = False
        self._buf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self._sky = pygame.Surface((400, 300), pygame.SRCALPHA)
        if self._pages:
            self.game.sound.play_bgm(bgm_path("BGM_BLACKHOLE"), volume=0.48)
            self._enter_page()
        else:
            self._set_phase("silence")
            self._begin_finish()

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        if self._finished:
            return
        self._time += dt
        self._phase_time += dt
        if self._rescue_age is not None:
            self._rescue_age += dt
        self._shake_t = max(0.0, self._shake_t - dt)
        self._fade_in_t = max(0.0, self._fade_in_t - dt)
        self._update_actor_motion(dt)
        if self._fade_out:
            self._fade_out_t += dt
            if self._fade_out_t >= 1.2:
                self._finished = True
                self._on_complete()
            return

        previous_chars = min(int(self._chars), self._total_chars())
        self._chars += _TYPEWRITER_SPEED * dt
        self._tick_type_sound(dt, previous_chars)
        inp = self.game.input
        if inp.is_action_just_pressed("ui_back"):
            self._begin_finish()
            return
        advance = inp.is_action_held_with_repeat(
            "ui_accept", initial_delay=0.25, repeat_interval=0.12,
        )
        if advance and not self._is_text_complete():
            self._chars = float(self._total_chars())
        elif advance or self._advance_queued:
            if self._phase_time < _MIN_PHASE_TIME.get(self._phase, 0.0):
                self._advance_queued = True
            else:
                self._advance_queued = False
                if self._page < len(self._pages) - 1:
                    self._page += 1
                    self._enter_page()
                else:
                    self._begin_finish()

    def _enter_page(self) -> None:
        self._chars = 0.0
        self._type_se_cooldown = 0.0
        self._advance_queued = False
        if not self._pages:
            return
        new_phase = self._phase_for_page()
        if new_phase != self._phase:
            self._set_phase(new_phase)
        pg = self._cur()
        if pg.se and not self._quiet:
            self.game.sound.play_se_alias(pg.se, volume=0.55)
        if not self._quiet and ("blackhole" in pg.fx or "shake" in pg.fx):
            self._shake_t = 0.45

    def _set_phase(self, phase: str) -> None:
        self._phase = phase
        self._phase_time = 0.0
        self._motion_start_player = self._player_pos
        self._motion_start_karonaru = self._karonaru_pos
        self._motion_start_alpha = self._karonaru_alpha
        self._motion_start_scale = self._karonaru_scale
        if phase == "push":
            self._shake_t = 0.65
            self._rescue_origin = self._karonaru_pos
            self._rescue_age = 0.0
            self.game.sound.play_se_alias("SE_KARONARU_ARRIVE", volume=0.75)
        if phase in {"gone", "silence"}:
            self._enter_quiet()

    def _enter_quiet(self) -> None:
        self._shake_t = 0.0
        if not self._quiet:
            self._quiet = True
            self.game.sound.stop_bgm(fadeout_ms=850)

    def _phase_for_page(self) -> str:
        # Carry the last cue across ordinary dialogue pages. Inserting a line
        # cannot accidentally move the rescue or make the companion disappear.
        for pg in reversed(self._pages[:self._page + 1]):
            for tag in reversed(pg.fx):
                if tag in _PHASE_TAGS:
                    return _PHASE_TAGS[tag]
        return "balance"

    def _cur(self) -> Page:
        return self._pages[self._page]

    def _total_chars(self) -> int:
        return sum(len(line) for line in self._cur().lines) if self._pages else 0

    def _is_text_complete(self) -> bool:
        return int(self._chars) >= self._total_chars()

    def _tick_type_sound(self, dt: float, previous_chars: int) -> None:
        self._type_se_cooldown = max(0.0, self._type_se_cooldown - dt)
        current_chars = min(int(self._chars), self._total_chars())
        if not self._quiet and current_chars > previous_chars and self._type_se_cooldown <= 0.0:
            self.game.sound.play_se_alias("SE_TYPE", volume=_TYPE_SE_VOLUME)
            self._type_se_cooldown = _TYPE_SE_INTERVAL

    def _begin_finish(self) -> None:
        if not self._fade_out and not self._finished:
            self._fade_out = True
            self._fade_out_t = 0.0
            self._enter_quiet()

    def _update_actor_motion(self, dt: float) -> None:
        phase = self._phase
        progress = min(1.0, self._phase_time / _MOTION_TIME.get(phase, 1.0))
        eased = progress * progress * (3.0 - 2.0 * progress)
        player_target = {
            "balance": (200.0, 244.0), "pull": (274.0, 240.0),
            "resolve": (280.0, 240.0), "charge": (280.0, 240.0),
        }.get(phase, (-72.0, 270.0))
        companion_target = {
            "balance": (130.0, 256.0), "pull": (192.0, 248.0),
            "resolve": (336.0, 230.0), "charge": (336.0, 230.0),
            "push": (412.0, 214.0),
            "fall": _HORIZON, "hold": (474.0, 212.0),
            "farewell": (478.0, 208.0),
        }.get(phase, _CENTER)
        self._player_pos = _lerp(self._motion_start_player, player_target, eased)
        if phase in {"resolve", "fall", "gone"}:
            sx, sy = self._motion_start_karonaru
            ex, ey = companion_target
            bend = -40.0 if phase == "resolve" else 25.0
            self._karonaru_pos = _curve(
                (sx, sy), ((sx + ex) * 0.5, (sy + ey) * 0.5 + bend), (ex, ey), eased,
            )
        else:
            self._karonaru_pos = _lerp(self._motion_start_karonaru, companion_target, eased)
        # Reading time never consumes the farewell. Only the authored 'gone'
        # cue lets the body cross the horizon and dissolve.
        alpha = {"fall": 215.0, "hold": 200.0, "farewell": 190.0,
                 "gone": 0.0, "silence": 0.0}.get(phase, 255.0)
        scale = {"fall": 0.65, "hold": 0.61, "farewell": 0.58,
                 "gone": 0.06, "silence": 0.06}.get(phase, 1.0)
        self._karonaru_alpha = self._motion_start_alpha + (alpha - self._motion_start_alpha) * eased
        self._karonaru_scale = self._motion_start_scale + (scale - self._motion_start_scale) * eased

    def _shake_offset(self) -> tuple[int, int]:
        if self._quiet or self._shake_t <= 0.0:
            return (0, 0)
        strength = 3.0 * min(1.0, self._shake_t / 0.4)
        return (round(math.sin(self._time * 47.0) * strength),
                round(math.cos(self._time * 39.0) * strength))

    def _draw_blackhole(self, screen: pygame.Surface) -> None:
        sky = self._sky
        sky.blit(self._background, (0, 0))
        if not self._quiet:
            # Near dust travels faster than distant stars, with restrained gold
            # fragments along the disk. The event horizon stays entirely dark.
            cx, cy = _CENTER[0] * 0.5, _CENTER[1] * 0.5
            for i in range(36):
                angle = i * 2.39996 + self._time * (0.07 + i % 3 * 0.018)
                radius = 51.0 + i % 11 * 5.7
                dx, dy = math.cos(angle) * radius, math.sin(angle) * radius * 0.18
                x, y = cx + dx, cy + dy - dx * 0.09
                if math.hypot(x - cx, y - cy) > 44.0:
                    color = (167 + i % 4 * 15, 123 + i % 4 * 15, 88 + i % 3 * 14)
                    pygame.draw.rect(sky, color, (round(x), round(y), 1 + (i % 9 == 0), 1))
            for i in range(12):
                x = (i * 71 + self._time * (0.17 + i % 3 * 0.1)) % 390
                y = 12 + (i * 37) % 137
                if math.hypot(x - cx, y - cy) > 70:
                    pygame.draw.rect(sky, (105, 116, 143), (int(x), y, 1, 1))
        screen.blit(pygame.transform.scale(sky, (SCREEN_WIDTH, SCREEN_HEIGHT)), (0, 0))

    def _draw_rescue_power(self, screen: pygame.Surface) -> None:
        """Release all remaining pressure leftward; the equal recoil carries K right.

        The beam and its short afterimage use an independent clock, so page
        advances cannot replay the blast. It is confined above the dialogue.
        """
        fx = self._rescue_fx
        fx.fill((0, 0, 0, 0))
        if self._quiet:
            return
        if self._phase == "charge":
            cx, cy = (int(n / 2) for n in self._karonaru_pos)
            power = min(1.0, self._phase_time / 1.2)
            for i in range(22):
                a = i * 2.39996 + self._time * 1.8
                radius = 12 + (1 - (self._time * .8 + i / 22) % 1) * 38
                x, y = cx + math.cos(a) * radius, cy + math.sin(a) * radius * .75
                pygame.draw.rect(fx, (136, 255, 220, int(80 + 160 * power)), (int(x), int(y), 2, 2))
            radius = int(10 + 18 * power)
            pygame.draw.circle(fx, (196, 255, 228, 200), (cx, cy), radius, 2)
            pygame.draw.circle(fx, (244, 255, 235, 110), (cx, cy), max(3, radius // 2))
        age = self._rescue_age
        if age is not None and age < 1.55:
            cx, cy = (int(n / 2) for n in self._rescue_origin)
            life = max(0.0, 1.0 - age / 1.55)
            width = max(1, int(24 * life))
            length = int(240 * min(1.0, age / .20))
            # A directional cone, three bright layers, then a broken shock ring.
            for spread, color in [(width + 12, (47, 196, 159, int(90 * life))),
                                  (width, (114, 255, 202, int(210 * life))),
                                  (max(2, width // 3), (245, 255, 230, int(255 * life)))]:
                pygame.draw.polygon(fx, color, [(cx, cy - 3), (cx - length, cy - spread),
                                              (cx - length, cy + spread), (cx, cy + 3)])
            radius = int(12 + age * 96)
            for i in range(12):
                a = i * math.tau / 12
                x, y = cx + math.cos(a) * radius, cy + math.sin(a) * radius * .68
                pygame.draw.rect(fx, (171, 255, 220, int(230 * life)), (int(x), int(y), 3, 2))
            for i in range(18):
                x = cx - ((age * (160 + i * 5) + i * 19) % 300)
                y = cy + ((i * 17) % 55) - 27
                pygame.draw.line(fx, (184, 255, 222, int(150 * life)), (x, y), (x + 8, y), 1)
        screen.blit(pygame.transform.scale(fx, (800, 342)), (0, 0))

    def _draw_actors(self, screen: pygame.Surface) -> None:
        px, py = self._player_pos
        self._player.rect.center = (round(px), round(py))
        screen.blit(self._player.image, self._player.rect)
        if self._karonaru_alpha <= 0.5:
            return
        kx, ky = self._karonaru_pos
        scale = self._karonaru_scale
        alpha = round(self._karonaru_alpha)
        light = pygame.Surface((400, 300), pygame.SRCALPHA)
        glow_x, glow_y = round(kx / 2), round(ky / 2)
        if self._phase in {"push", "fall", "hold", "farewell", "gone"}:
            for radius, opacity in ((19, 12), (12, 22), (7, 34)):
                pygame.draw.circle(light, (100, 245, 202, round(opacity * alpha / 255)),
                                   (glow_x, glow_y), max(2, round(radius * scale)))
            # The last few motes follow the companion, never cover the words.
            for i in range(8):
                age = (self._phase_time * 0.32 + i / 8) % 1.0
                x = glow_x - 5 - age * 29
                y = glow_y + 6 + math.sin(i * 2.0) * 7 * age
                pygame.draw.rect(light, (159, 255, 220, round((1 - age) * alpha * 0.55)),
                                 (round(x), round(y), 1, 1))
        screen.blit(pygame.transform.scale(light, (SCREEN_WIDTH, SCREEN_HEIGHT)), (0, 0))
        image = pygame.transform.scale(self._karonaru.image,
                                       (max(2, round(66 * scale)), max(2, round(100 * scale))))
        image.set_alpha(alpha)
        self._karonaru.rect = image.get_rect(center=(round(kx), round(ky)))
        screen.blit(image, self._karonaru.rect)

    def draw(self, screen: pygame.Surface) -> None:
        self._draw_blackhole(self._buf)
        self._draw_rescue_power(self._buf)
        self._draw_actors(self._buf)
        screen.fill((0, 0, 0))
        screen.blit(self._buf, self._shake_offset())
        self._draw_dialogue(screen)
        fade_a = 0
        if self._fade_out:
            fade_a = int(255 * min(1.0, max(0.0, self._fade_out_t - 0.35) / 0.85))
        elif self._fade_in_t > 0:
            fade_a = int(255 * self._fade_in_t / 0.6)
        if fade_a:
            fade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            fade.set_alpha(fade_a)
            fade.fill((0, 0, 0))
            screen.blit(fade, (0, 0))

    def _draw_dialogue(self, screen: pygame.Surface) -> None:
        if not self._pages:
            return
        from src.scenes.dialogue_panel import draw_story_panel
        pg = self._cur()
        accept = self.game.settings.key_display("ui_accept")
        back = self.game.settings.key_display("ui_back")
        advance = "次へ" if self._is_text_complete() else "全文表示"
        hint = f"{accept}: {advance}（長押し可）　{back}: 会話を省略"
        draw_story_panel(
            screen, self.game.resources, pg.speaker, pg.lines,
            chars=int(self._chars), complete=self._is_text_complete(),
            hint_text=hint, show_portrait=False,
        )
