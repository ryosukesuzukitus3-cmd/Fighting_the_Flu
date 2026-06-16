import math
import os
import random
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.story.script import TITLE_IDLE


_MENU = ["ゲームスタート", "チュートリアル", "ハイスコア", "統計", "設定"]

_IDLE_DELAY  = 6.0   # 無操作からアイドルテキスト表示までの秒数
_IDLE_ROTATE = 5.0   # アイドルテキストの切替間隔

def _make_radial_glow(w: int, h: int, color: tuple[int, int, int], max_alpha: int) -> pygame.Surface:
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w // 2, h // 2
    maxr = min(w, h) // 2
    for r in range(maxr, 0, -1):
        t = r / maxr
        a = int(max_alpha * (1 - t) ** 1.8)
        pygame.draw.circle(surf, (color[0], color[1], color[2], a), (cx, cy), r)
    return surf


def _make_vgrad(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> pygame.Surface:
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    for y in range(SCREEN_HEIGHT):
        t = y / (SCREEN_HEIGHT - 1)
        surf.fill(
            (int(top[0] + (bottom[0] - top[0]) * t),
             int(top[1] + (bottom[1] - top[1]) * t),
             int(top[2] + (bottom[2] - top[2]) * t)),
            (0, y, SCREEN_WIDTH, 1),
        )
    return surf


class TitleScene(Scene):
    def on_enter(self) -> None:
        self._title_font = self.game.resources.pixelfont(64)
        self._menu_font  = self.game.resources.pixelfont(28)
        self._small_font = self.game.resources.pixelfont(18)
        self._idle_font  = self.game.resources.pixelfont(18)
        self._cursor     = 0
        self._idle_timer = 0.0
        self._idle_index = random.randrange(len(TITLE_IDLE)) if TITLE_IDLE else 0
        self._t          = 0.0
        # タイトルデザインは2案を用意し、表示ごとにランダムで出す
        # （"A"=ミニマル黒 / "B"=発熱ムード）。env TITLE_VARIANT で固定も可。
        self._variant = (os.environ.get("TITLE_VARIANT") or random.choice(("A", "B"))).upper()
        # 静的レイヤは1回だけ生成
        self._glow_a = _make_radial_glow(560, 360, (150, 28, 24), 90)
        self._glow_b = _make_radial_glow(620, 420, (200, 70, 40), 120)
        self._grad_b = _make_vgrad((34, 10, 12), (6, 6, 10))
        self.game.sound.play_bgm_if_new("music/bgm/The_Final_Battle_short.mp3")

    def on_exit(self) -> None:
        pass

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        self._t += dt
        inp = self.game.input
        moved = False
        if inp.is_just_pressed(pygame.K_UP):
            self._cursor = (self._cursor - 1) % len(_MENU)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
            moved = True
        if inp.is_just_pressed(pygame.K_DOWN):
            self._cursor = (self._cursor + 1) % len(_MENU)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
            moved = True
        if inp.is_just_pressed(pygame.K_SPACE) or inp.is_just_pressed(pygame.K_RETURN):
            self._select()
            moved = True

        if moved:
            self._idle_timer = 0.0
        else:
            prev = self._idle_timer
            self._idle_timer += dt
            if TITLE_IDLE and prev < _IDLE_DELAY <= self._idle_timer:
                self._idle_index = random.randrange(len(TITLE_IDLE))
            elif self._idle_timer >= _IDLE_DELAY + _IDLE_ROTATE:
                self._idle_timer = _IDLE_DELAY
                self._idle_index = (self._idle_index + 1) % len(TITLE_IDLE)
        if inp.is_just_pressed(pygame.K_d):
            from src.scenes.game_scene import GameScene
            self.game.change_scene(GameScene(self.game, stage_id=99))

    def _select(self) -> None:
        self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
        if self._cursor == 0:
            from src.scenes.prologue_scene import PrologueScene
            self.game.change_scene(PrologueScene(self.game))
        elif self._cursor == 1:
            from src.scenes.tutorial_scene import TutorialScene
            self.game.change_scene(TutorialScene(self.game))
        elif self._cursor == 2:
            from src.scenes.highscore_scene import HighScoreScene
            self.game.change_scene(HighScoreScene(self.game))
        elif self._cursor == 3:
            from src.scenes.stats_scene import StatsScene
            self.game.change_scene(StatsScene(self.game))
        elif self._cursor == 4:
            from src.scenes.settings_scene import SettingsScene
            self.game.change_scene(SettingsScene(self.game, self))

    # ── 描画 ─────────────────────────────────────────────────────
    def draw(self, screen: pygame.Surface) -> None:
        if self._variant == "B":
            self._draw_b(screen)
        else:
            self._draw_a(screen)

    def _blit_center(self, screen, surf, y, alpha=None):
        if alpha is not None:
            surf = surf.copy()
            surf.set_alpha(alpha)
        screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, y))
        return surf.get_height()

    def _draw_footer(self, screen):
        cx = SCREEN_WIDTH // 2
        if TITLE_IDLE and self._idle_timer >= _IDLE_DELAY:
            a = int(110 + 60 * (0.5 + 0.5 * math.sin(self._t * 2.0)))
            idle = self._idle_font.render(TITLE_IDLE[self._idle_index], True, (150, 146, 150))
            idle.set_alpha(a)
            screen.blit(idle, (cx - idle.get_width() // 2, SCREEN_HEIGHT - 72))
        hint = self._small_font.render("↑↓  SPACE / ENTER", True, (110, 106, 112))
        hint.set_alpha(150)
        screen.blit(hint, (cx - hint.get_width() // 2, SCREEN_HEIGHT - 40))
        dbg = self._idle_font.render("D : デバッグ", True, (74, 70, 80))
        dbg.set_alpha(120)
        screen.blit(dbg, (SCREEN_WIDTH - dbg.get_width() - 14, SCREEN_HEIGHT - 28))

    # ── Variant A : ミニマル黒（クール）──────────────────────────
    def _draw_a(self, screen: pygame.Surface) -> None:
        cx = SCREEN_WIDTH // 2
        screen.fill((11, 11, 13))
        screen.blit(self._glow_a, (cx - self._glow_a.get_width() // 2, 28))

        text = "インフルとの死闘"
        ts = self._title_font.render(text, True, (240, 238, 234))
        sh = self._title_font.render(text, True, (0, 0, 0))
        sh.set_alpha(110)
        ty = 138
        screen.blit(sh, (cx - ts.get_width() // 2 + 2, ty + 3))
        screen.blit(ts, (cx - ts.get_width() // 2, ty))

        # 細い赤のアクセント罫線
        rule_y = ty + ts.get_height() + 18
        rw = 132
        pygame.draw.rect(screen, (208, 56, 46), (cx - rw // 2, rule_y, rw, 3))
        temp = self._small_font.render("38.9℃", True, (150, 120, 116))
        screen.blit(temp, (cx - temp.get_width() // 2, rule_y + 12))

        self._draw_menu_a(screen, cx, top=302)
        self._draw_footer(screen)

    def _draw_menu_a(self, screen, cx, top):
        row_h = 46
        for i, label in enumerate(_MENU):
            y = top + i * row_h
            selected = (i == self._cursor)
            color = (244, 244, 246) if selected else (112, 110, 116)
            surf = self._menu_font.render(label, True, color)
            x = cx - surf.get_width() // 2
            screen.blit(surf, (x, y))
            if selected:
                pulse = 0.5 + 0.5 * math.sin(self._t * 3.6)
                sq = 9
                sy = y + surf.get_height() // 2 - sq // 2
                sx = x - 22 - int(3 * pulse)
                pygame.draw.rect(screen, (212, 56, 46), (sx, sy, sq, sq))

    # ── Variant B : 発熱ムード（シネマティック）─────────────────
    def _draw_b(self, screen: pygame.Surface) -> None:
        cx = SCREEN_WIDTH // 2
        screen.blit(self._grad_b, (0, 0))
        ga = int(150 + 40 * (0.5 + 0.5 * math.sin(self._t * 1.6)))
        glow = self._glow_b.copy()
        glow.set_alpha(ga)
        screen.blit(glow, (cx - glow.get_width() // 2, 8))
        # 下側ビネット
        vig = pygame.Surface((SCREEN_WIDTH, 170), pygame.SRCALPHA)
        for y in range(170):
            vig.fill((0, 0, 0, int(150 * (y / 170))), (0, y, SCREEN_WIDTH, 1))
        screen.blit(vig, (0, SCREEN_HEIGHT - 170))

        text = "インフルとの死闘"
        breathe = int(245 + 10 * math.sin(self._t * 1.8))
        ts = self._title_font.render(text, True, (250, 236, 222))
        sh = self._title_font.render(text, True, (40, 6, 6))
        sh.set_alpha(150)
        ty = 142
        screen.blit(sh, (cx - ts.get_width() // 2 + 2, ty + 4))
        ts.set_alpha(min(255, breathe))
        screen.blit(ts, (cx - ts.get_width() // 2, ty))

        temp = self._small_font.render("― 38.9℃ ―", True, (214, 150, 120))
        temp.set_alpha(210)
        screen.blit(temp, (cx - temp.get_width() // 2, ty + ts.get_height() + 14))

        self._draw_menu_b(screen, cx, top=302)
        self._draw_footer(screen)

    def _draw_menu_b(self, screen, cx, top):
        row_h = 46
        for i, label in enumerate(_MENU):
            y = top + i * row_h
            selected = (i == self._cursor)
            color = (255, 212, 146) if selected else (150, 134, 130)
            surf = self._menu_font.render(label, True, color)
            x = cx - surf.get_width() // 2
            screen.blit(surf, (x, y))
            if selected:
                pulse = 0.5 + 0.5 * math.sin(self._t * 3.6)
                uw = int(surf.get_width() * (0.62 + 0.10 * pulse))
                uy = y + surf.get_height() + 3
                pygame.draw.rect(screen, (236, 150, 96), (cx - uw // 2, uy, uw, 2))
