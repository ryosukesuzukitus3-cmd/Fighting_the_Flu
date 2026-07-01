import math
import random
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.story.script import TITLE_IDLE


_MENU = ["ゲームスタート", "チュートリアル", "ハイスコア", "統計", "設定"]

_IDLE_DELAY  = 6.0   # 無操作からアイドルテキスト表示までの秒数
_IDLE_ROTATE = 5.0   # アイドルテキストの切替間隔

_SUBTITLE = "すまん、陽性だったにょ"


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
        # 発熱ムード（暖→寒の縦グラデ＋暖色グロー）。静的レイヤは1回だけ生成。
        self._glow = _make_radial_glow(620, 420, (200, 70, 40), 120)
        self._grad = _make_vgrad((34, 10, 12), (6, 6, 10))
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
            elif TITLE_IDLE and self._idle_timer >= _IDLE_DELAY + _IDLE_ROTATE:
                self._idle_timer = _IDLE_DELAY
                self._idle_index = (self._idle_index + 1) % len(TITLE_IDLE)
        # デバッグジャンプ（python -O で除去）
        if __debug__:
            if inp.is_just_pressed(pygame.K_d):
                from src.scenes.game_scene import GameScene
                self.game.change_scene(GameScene(self.game, stage_id=99))
            elif inp.is_just_pressed(pygame.K_c):
                self._debug_jump_credits()
            elif inp.is_just_pressed(pygame.K_v):
                self._debug_jump_gameclear()

    def _debug_jump_credits(self) -> None:
        """スタッフロール（エンドロール）へ直行。確認用。"""
        from src.scenes.credits_roll import CreditsRollScene
        from src.scenes.story_flow import credits_pages
        self.game.change_scene(CreditsRollScene(
            self.game, credits_pages(),
            lambda: self.game.change_scene(TitleScene(self.game)),
        ))

    def _debug_jump_gameclear(self) -> None:
        """ラスボス撃破後のクリア画面へ直行（ENTER でスタッフロールへ続く）。"""
        from src.scenes.gameclear import GameClearScene
        self.game.change_scene(GameClearScene(self.game, record_result=False))

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
        cx = SCREEN_WIDTH // 2
        screen.blit(self._grad, (0, 0))
        ga = int(150 + 40 * (0.5 + 0.5 * math.sin(self._t * 1.6)))
        glow = self._glow.copy()
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
        ty = 138
        screen.blit(sh, (cx - ts.get_width() // 2 + 2, ty + 4))
        ts.set_alpha(min(255, breathe))
        screen.blit(ts, (cx - ts.get_width() // 2, ty))

        sub = self._small_font.render(_SUBTITLE, True, (214, 150, 120))
        sub.set_alpha(210)
        screen.blit(sub, (cx - sub.get_width() // 2, ty + ts.get_height() + 14))

        self._draw_menu(screen, cx, top=304)
        self._draw_footer(screen)

    def _draw_menu(self, screen, cx, top):
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
        if __debug__:
            dbg = self._idle_font.render(
                "D:デバッグ  C:スタッフロール  V:クリア画面", True, (74, 70, 80)
            )
            dbg.set_alpha(120)
            screen.blit(dbg, (SCREEN_WIDTH - dbg.get_width() - 14, SCREEN_HEIGHT - 28))
