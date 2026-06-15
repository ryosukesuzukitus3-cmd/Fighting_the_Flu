import math
import random
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.entities.background import ScrollingBackground
from src.story.script import TITLE_IDLE


_MENU = ["ゲームスタート", "チュートリアル", "ハイスコア", "統計", "設定"]

_IDLE_DELAY  = 6.0   # 無操作からアイドルテキスト表示までの秒数
_IDLE_ROTATE = 5.0   # アイドルテキストの切替間隔

# 配色（発熱テーマに合わせた暖色基調）
_C_TITLE      = (238, 102, 56)
_C_TITLE_GLOW = (255, 64, 32)
_C_SEL        = (255, 226, 120)
_C_UNSEL      = (178, 170, 176)
_C_PANEL      = (14, 8, 12)
_C_PANEL_EDGE = (200, 92, 60)
_C_BADGE      = (255, 158, 96)


class TitleScene(Scene):
    def on_enter(self) -> None:
        self._title_font  = self.game.resources.pixelfont(66)
        self._menu_font   = self.game.resources.pixelfont(28)
        self._idle_font   = self.game.resources.pixelfont(20)
        self._badge_font  = self.game.resources.pixelfont(22)
        self._mascot_font = self.game.resources.pixelfont(16)
        self._hint_font   = self.game.resources.pixelfont(18)
        self._dbg_font    = self.game.resources.pixelfont(14)
        self._cursor     = 0
        self._idle_timer = 0.0
        self._idle_index = random.randrange(len(TITLE_IDLE)) if TITLE_IDLE else 0
        self._t          = 0.0
        # 発熱回廊テーマ（脈打つ血球・熱の霞）をタイトル背景に流用
        self._bg = ScrollingBackground(stage_id=1)
        # サブメニューから戻った場合はBGMを再起動しない
        self.game.sound.play_bgm_if_new("music/bgm/The_Final_Battle_short.mp3")

    def on_exit(self) -> None:
        pass  # BGMはサブメニューでも継続させる（ゲーム開始時にgame_sceneが停止する）

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

        # アイドルテキスト: 一定時間ごとに切替（操作でリセット）
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
        cx = SCREEN_WIDTH // 2
        # 1) 発熱テーマの動く背景（camera_x をゆっくり流して視差）
        self._bg.draw(screen, camera_x=self._t * 26.0)
        # 2) 読みやすさのための減光＋上下ビネット
        self._draw_vignette(screen)
        # 3) タイトル（ヒートグロー＋微鼓動）＋ 38.9℃ バッジ
        self._draw_title(screen, cx)
        # 4) メニュー（パネル＋ハイライト＋カーソル）
        self._draw_menu(screen, cx)
        # 5) アイドルテキスト（無操作時に点滅表示）
        if TITLE_IDLE and self._idle_timer >= _IDLE_DELAY:
            a = int(120 + 70 * (0.5 + 0.5 * math.sin(self._t * 2.2)))
            idle = self._idle_font.render(TITLE_IDLE[self._idle_index], True, (212, 192, 162))
            idle.set_alpha(a)
            screen.blit(idle, (cx - idle.get_width() // 2, SCREEN_HEIGHT - 70))
        # 6) フッター
        hint = self._hint_font.render("↑↓: 選択   SPACE / ENTER: 決定", True, (150, 140, 140))
        hint.set_alpha(180)
        screen.blit(hint, (cx - hint.get_width() // 2, SCREEN_HEIGHT - 40))
        dbg = self._dbg_font.render("D : デバッグステージ", True, (95, 84, 98))
        dbg.set_alpha(150)
        screen.blit(dbg, (SCREEN_WIDTH - dbg.get_width() - 12, SCREEN_HEIGHT - 26))
        # 7) カロナール先輩マスコット（右下に浮かぶカプセル＋「にょ」）
        self._draw_mascot(screen)

    def _draw_vignette(self, screen: pygame.Surface) -> None:
        ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((6, 4, 8, 96))   # 全体を軽く沈めてテキストを浮かせる
        screen.blit(ov, (0, 0))
        band = 150
        top = pygame.Surface((SCREEN_WIDTH, band), pygame.SRCALPHA)
        for y in range(band):
            a = int(150 * (1 - y / band))
            pygame.draw.line(top, (0, 0, 0, a), (0, y), (SCREEN_WIDTH, y))
        screen.blit(top, (0, 0))
        screen.blit(pygame.transform.flip(top, False, True), (0, SCREEN_HEIGHT - band))

    def _glow_text(self, screen, font, text, color, glow, pos, *, radius=3, glow_alpha=70):
        gs = font.render(text, True, glow)
        gs.set_alpha(glow_alpha)
        x, y = pos
        for dx, dy in ((-radius, 0), (radius, 0), (0, -radius), (0, radius),
                       (-radius, -radius), (radius, -radius), (-radius, radius), (radius, radius)):
            screen.blit(gs, (x + dx, y + dy))
        screen.blit(font.render(text, True, color), pos)

    def _draw_title(self, screen: pygame.Surface, cx: int) -> None:
        text = "インフルとの死闘"
        throb = math.sin(self._t * 2.0)
        title_surf = self._title_font.render(text, True, _C_TITLE)
        tw, th = title_surf.get_size()
        x = cx - tw // 2
        y = 112 + int(throb * 3)
        # 影
        sh = self._title_font.render(text, True, (0, 0, 0))
        sh.set_alpha(120)
        screen.blit(sh, (x + 4, y + 5))
        # ヒートグロー（強度を鼓動させる）
        ga = int(50 + 32 * (0.5 + 0.5 * throb))
        self._glow_text(screen, self._title_font, text, _C_TITLE, _C_TITLE_GLOW, (x, y),
                        radius=3, glow_alpha=ga)
        # 38.9℃ バッジ（両脇に線）
        badge = self._badge_font.render("38.9℃", True, _C_BADGE)
        bw, bh = badge.get_size()
        by = y + th + 8
        line_y = by + bh // 2
        pygame.draw.line(screen, (150, 60, 40), (cx - bw // 2 - 64, line_y), (cx - bw // 2 - 16, line_y), 2)
        pygame.draw.line(screen, (150, 60, 40), (cx + bw // 2 + 16, line_y), (cx + bw // 2 + 64, line_y), 2)
        screen.blit(badge, (cx - bw // 2, by))

    def _draw_menu(self, screen: pygame.Surface, cx: int) -> None:
        n = len(_MENU)
        row_h = 46
        top = 290
        half_w = 156
        pad_y = 16
        panel = pygame.Rect(cx - half_w, top - pad_y, half_w * 2, row_h * (n - 1) + 30 + pad_y * 2)
        ps = pygame.Surface(panel.size, pygame.SRCALPHA)
        ps.fill((*_C_PANEL, 142))
        pygame.draw.rect(ps, (*_C_PANEL_EDGE, 95), ps.get_rect(), 1, border_radius=10)
        screen.blit(ps, panel.topleft)

        pulse = 0.5 + 0.5 * math.sin(self._t * 4.0)
        for i, label in enumerate(_MENU):
            row_y = top + i * row_h
            selected = (i == self._cursor)
            if selected:
                hl = pygame.Surface((half_w * 2 - 24, row_h - 8), pygame.SRCALPHA)
                hl.fill((255, 120, 60, int(38 + 30 * pulse)))
                screen.blit(hl, (cx - half_w + 12, row_y - 4))
            color = _C_SEL if selected else _C_UNSEL
            surf = self._menu_font.render(label, True, color)
            screen.blit(surf, (cx - surf.get_width() // 2, row_y))
            if selected:
                # 三角カーソル（左右に微動）。グリフ非依存で描画する。
                tx = cx - surf.get_width() // 2 - 26 + int(4 * pulse)
                tcy = row_y + surf.get_height() // 2
                pygame.draw.polygon(screen, color,
                                    [(tx, tcy - 8), (tx, tcy + 8), (tx + 12, tcy)])

    def _draw_mascot(self, screen: pygame.Surface) -> None:
        bob = int(math.sin(self._t * 1.6) * 3)
        bx, by = SCREEN_WIDTH - 96, SCREEN_HEIGHT - 156 + bob
        cap = pygame.Surface((54, 26), pygame.SRCALPHA)
        pygame.draw.rect(cap, (236, 240, 236), (0, 0, 27, 26),
                         border_top_left_radius=13, border_bottom_left_radius=13)
        pygame.draw.rect(cap, (72, 200, 112), (27, 0, 27, 26),
                         border_top_right_radius=13, border_bottom_right_radius=13)
        pygame.draw.rect(cap, (255, 255, 255), (5, 5, 16, 5), border_radius=2)
        cap = pygame.transform.rotate(cap, 18)
        screen.blit(cap, (bx, by))
        ny = self._mascot_font.render("にょ", True, (152, 236, 172))
        screen.blit(ny, (bx + 10, by - 16))
