from __future__ import annotations
import math
from typing import Callable
import pygame

from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.story.lines import Page
from src.story.speakers import speaker_name, speaker_color, DEFAULT_TEXT_COLOR, NARRATION

_SCROLL_SPEED = 40.5          # BGM を聴かせつつ、間延びしない速さ
_FAST_MULT = 3.6
_SIDE_PAD = 72
_FADEOUT_MS = 2400
_FADEOUT_SEC = _FADEOUT_MS / 1000.0
_FINAL_HOLD_SEC = 3.0         # 他が流れ切った後、最終行を中央で保持する秒数
_FINAL_GAP_ENTRIES = 7        # 最終行（Thank you）の手前に足す空行数（少し離す）

# エンドロール記法（script.py CREDITS / POSTCREDIT のテキスト先頭マーカー）
_TITLE_MARK = "■"             # セクション見出し（大・金・下線）
_ROLE_MARK = "/"              # 役職ラベル（小・控えめ色）

_TITLE_COLOR = (255, 220, 120)
_ROLE_COLOR = (170, 164, 148)


class CreditsRollScene(Scene):
    def __init__(self, game, pages: list[Page], on_complete: Callable[[], None]) -> None:
        super().__init__(game)
        self._pages = list(pages)
        self._on_complete = on_complete

    def on_enter(self) -> None:
        self._font_title = self.game.resources.pixelfont(44)
        self._font_speaker = self.game.resources.pixelfont(22)
        self._font_name = self.game.resources.pixelfont(28)
        self._font_role = self.game.resources.pixelfont(19)
        self._font_body = self.game.resources.pixelfont(24)
        self._font_small = self.game.resources.pixelfont(18)
        self._hint_font = self.game.resources.pixelfont(16)
        self._entries: list[tuple[str, str, tuple[int, int, int]]] = []
        self._build_entries()
        self._insert_final_gap()
        self._content_h = sum(self._entry_height(kind, text) for text, kind, _ in self._entries)
        self._scroll_y = float(SCREEN_HEIGHT + 70)
        self._init_final_entry_geometry()
        self._hold_timer = 0.0
        self._timer = 0.0
        self._finished = False
        self._completed = False
        self._fadeout_timer = 0.0
        self._bg = self._make_background()
        self.game.sound.play_bgm_alias("BGM_CREDITS", loops=0)

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        self._timer += dt
        if self._finished:
            self._fadeout_timer -= dt
            if self._fadeout_timer <= 0.0 and not self._completed:
                self._completed = True
                self._on_complete()
            return

        inp = self.game.input
        if inp.is_action_just_pressed("ui_back"):
            self._finish(fadeout=False)
            return

        # Thank you for playing（最終行）だけ画面中央で止まり、他はそのまま
        # 流れて消えていく（描画側で最終行の y をクランプ）。他が流れ切ったら
        # 最終行を単独で保持 → 時間経過 or キーでフェードアウト。
        if self._scroll_y + self._final_prefix_h < -80:
            self._hold_timer += dt
            if (self._hold_timer >= _FINAL_HOLD_SEC
                    or inp.is_action_just_pressed("ui_accept")):
                self._finish(fadeout=True)
            return

        speed = _SCROLL_SPEED
        if inp.is_action_pressed("ui_accept"):
            speed *= _FAST_MULT
        self._scroll_y -= speed * dt

    def draw(self, screen: pygame.Surface) -> None:
        screen.blit(self._bg, (0, 0))
        self._draw_slow_rays(screen)

        y = self._scroll_y
        for i, (text, kind, color) in enumerate(self._entries):
            h = self._entry_height(kind, text)
            # 最終行（Thank you for playing）だけ中央より上へは行かない
            draw_y = max(y, self._final_center_y) if i == self._final_idx else y
            if text and -70 <= draw_y <= SCREEN_HEIGHT + 40:
                font = self._font_for(kind, text)
                surf = font.render(text, True, color)
                screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, int(draw_y)))
                if kind == "title":
                    line_y = int(draw_y + surf.get_height() + 12)
                    pygame.draw.line(screen, (190, 160, 70), (190, line_y), (SCREEN_WIDTH - 190, line_y), 1)
            y += h

        self._draw_vignette(screen)
        accept = self.game.settings.key_display("ui_accept")
        back = self.game.settings.key_display("ui_back")
        hint = self._hint_font.render(
            f"{accept}: FAST   {back}: TITLE", True, (175, 170, 155),
        )
        screen.blit(hint, (SCREEN_WIDTH - hint.get_width() - 18, SCREEN_HEIGHT - 28))

    def _last_text_index(self) -> int | None:
        for i in range(len(self._entries) - 1, -1, -1):
            if self._entries[i][0]:
                return i
        return None

    def _insert_final_gap(self) -> None:
        """最終行（Thank you）の手前に空行を足して、少し離す。"""
        idx = self._last_text_index()
        if idx is None:
            return
        gap = [("", "space", DEFAULT_TEXT_COLOR)] * _FINAL_GAP_ENTRIES
        self._entries[idx:idx] = gap

    def _init_final_entry_geometry(self) -> None:
        """最終行のインデックス・手前の高さ合計・中央クランプ位置を確定する。"""
        idx = self._last_text_index()
        if idx is None:
            self._final_idx = -1
            self._final_prefix_h = self._content_h
            self._final_center_y = 0.0
            return
        self._final_idx = idx
        self._final_prefix_h = sum(self._entry_height(kind, text)
                                   for text, kind, _ in self._entries[:idx])
        text, kind, _ = self._entries[idx]
        font = self._font_for(kind, text)
        self._final_center_y = float(SCREEN_HEIGHT // 2 - font.get_linesize() // 2)

    def _finish(self, *, fadeout: bool) -> None:
        if self._finished:
            return
        if not fadeout:
            self._completed = True
            self._on_complete()
            return
        self._finished = True
        self._fadeout_timer = _FADEOUT_SEC
        self.game.sound.stop_bgm(fadeout_ms=_FADEOUT_MS)

    def _build_entries(self) -> None:
        # 先頭に少し間を取り、最初の見出しが落ち着いて入ってくるようにする
        self._entries.append(("", "space", DEFAULT_TEXT_COLOR))
        for page in self._pages:
            narration = page.speaker == NARRATION
            name = speaker_name(page.speaker)
            if name:
                self._append_line(name, "speaker", speaker_color(page.speaker))
            for line in page.lines:
                if not line:
                    self._entries.append(("", "space", DEFAULT_TEXT_COLOR))
                elif line.startswith(_TITLE_MARK):
                    self._append_line(line[len(_TITLE_MARK):].strip(), "title", _TITLE_COLOR)
                elif line.startswith(_ROLE_MARK):
                    self._append_line(line[len(_ROLE_MARK):].strip(), "role", _ROLE_COLOR)
                elif narration:
                    self._append_line(line, "body", DEFAULT_TEXT_COLOR)
                else:
                    self._append_line(line, "name", DEFAULT_TEXT_COLOR)
            self._entries.append(("", "space", DEFAULT_TEXT_COLOR))

    def _append_line(self, text: str, kind: str, color: tuple[int, int, int]) -> None:
        font = self._font_for(kind, text)
        max_w = SCREEN_WIDTH - _SIDE_PAD * 2
        if kind in ("title", "speaker") or font.size(text)[0] <= max_w:
            self._entries.append((text, kind, color))
            return

        buf = ""
        for ch in text:
            if not buf or font.size(buf + ch)[0] <= max_w:
                buf += ch
            else:
                self._entries.append((buf, "small", color))
                buf = ch
        if buf:
            self._entries.append((buf, "small", color))

    def _font_for(self, kind: str, text: str) -> pygame.font.Font:
        if kind == "title":
            return self._font_title
        if kind == "speaker":
            return self._font_speaker
        if kind == "name":
            return self._font_name
        if kind == "role":
            return self._font_role
        if kind == "small":
            return self._font_small
        return self._font_body

    def _entry_height(self, kind: str, text: str) -> int:
        if not text:
            return 24
        if kind == "title":
            return self._font_for(kind, text).get_linesize() + 28
        if kind == "role":
            return self._font_for(kind, text).get_linesize() + 2
        return self._font_for(kind, text).get_linesize() + 8

    def _make_background(self) -> pygame.Surface:
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t = y / max(1, SCREEN_HEIGHT - 1)
            r = int(7 + 10 * t)
            g = int(8 + 8 * t)
            b = int(12 + 12 * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (SCREEN_WIDTH, y))
        for x in range(0, SCREEN_WIDTH, 48):
            pygame.draw.line(surf, (22, 21, 24), (x, 0), (x - 80, SCREEN_HEIGHT), 1)
        return surf

    def _draw_slow_rays(self, screen: pygame.Surface) -> None:
        layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT + 120
        for i in range(9):
            ang = -1.1 + i * 0.275 + math.sin(self._timer * 0.25 + i) * 0.035
            x = cx + math.cos(ang) * 760
            y = cy + math.sin(ang) * 760
            pygame.draw.line(layer, (210, 170, 70, 18), (cx, cy), (int(x), int(y)), 18)
        screen.blit(layer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_vignette(self, screen: pygame.Surface) -> None:
        fade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for i in range(90):
            alpha = int(175 * (1.0 - i / 90))
            pygame.draw.line(fade, (0, 0, 0, alpha), (0, i), (SCREEN_WIDTH, i))
            y = SCREEN_HEIGHT - 1 - i
            pygame.draw.line(fade, (0, 0, 0, alpha), (0, y), (SCREEN_WIDTH, y))
        screen.blit(fade, (0, 0))
