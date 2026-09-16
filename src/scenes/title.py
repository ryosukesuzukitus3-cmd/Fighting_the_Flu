import random
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.story.script import TITLE_IDLE
from src.scenes.meta_ui import (
    ACCENT_GOLD, TEXT, TEXT_MUTED, draw_meta_background,
    draw_meta_footer, draw_meta_panel, draw_selection_marker, fit_text,
)


_MENU = ["ゲームをはじめる", "操作の練習", "ハイスコア", "プレイ記録", "設定"]
_MENU_HELP = [
    "物語のはじめから出撃します。",
    "移動とショットの基本を練習します。",
    "これまでの最高スコアを確認します。",
    "挑戦の記録やステージごとの成績を確認します。",
    "音量と操作キーを変更します。",
]

_IDLE_DELAY  = 6.0   # 無操作からアイドルテキスト表示までの秒数
_IDLE_ROTATE = 5.0   # アイドルテキストの切替間隔

_SUBTITLE = "すまん、陽性だったにょ"


class TitleScene(Scene):
    def on_enter(self) -> None:
        self._title_font = self.game.resources.pixelfont(64)
        self._menu_font  = self.game.resources.pixelfont(28)
        self._small_font = self.game.resources.pixelfont(20)
        self._idle_font  = self.game.resources.pixelfont(18)
        self._cursor     = 0
        self._idle_timer = 0.0
        self._idle_index = random.randrange(len(TITLE_IDLE)) if TITLE_IDLE else 0
        self._t          = 0.0
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
        # Preserve the original title shortcut only with the default confirm key.
        legacy_space = (self.game.settings.get_key("ui_accept") == pygame.K_RETURN
                        and inp.is_just_pressed(pygame.K_SPACE))
        if inp.is_action_just_pressed("ui_accept") or legacy_space:
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
        if __debug__ and not moved:
            if inp.is_just_pressed(pygame.K_d):
                from src.scenes.game_scene import GameScene
                self.game.change_scene(GameScene(self.game, stage_id=99))
            elif inp.is_just_pressed(pygame.K_c):
                self._debug_jump_credits()
            elif inp.is_just_pressed(pygame.K_v):
                self._debug_jump_gameclear()

    def _debug_jump_credits(self) -> None:
        """スタッフロール（エンドロール）へ直行。確認用。本編同様、終了後は注意書きへ。"""
        from src.scenes.credits_roll import CreditsRollScene
        from src.scenes.disclaimer_scene import DisclaimerScene
        from src.scenes.story_flow import credits_pages
        self.game.change_scene(CreditsRollScene(
            self.game, credits_pages(),
            lambda: self.game.change_scene(DisclaimerScene(self.game)),
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

    def draw(self, screen: pygame.Surface) -> None:
        cx = SCREEN_WIDTH // 2
        draw_meta_background(screen, accent=(240, 149, 94))
        title = self._title_font.render("インフルとの死闘", True, (255, 237, 215))
        shadow = self._title_font.render("インフルとの死闘", True, (3, 6, 14))
        x = cx - title.get_width() // 2
        screen.blit(shadow, (x + 2, 78 + 3))
        screen.blit(title, (x, 78))
        subtitle = self._small_font.render(_SUBTITLE, True, (228, 179, 147))
        screen.blit(subtitle, (cx - subtitle.get_width() // 2, 166))
        pygame.draw.line(screen, (181, 123, 89), (cx - 32, 207), (cx + 32, 207), 2)

        panel = pygame.Rect(186, 238, 428, 244)
        draw_meta_panel(screen, panel, accent=(208, 172, 117))
        for i, label in enumerate(_MENU):
            row = pygame.Rect(panel.x + 14, panel.y + 12 + i * 44, panel.w - 28, 42)
            selected = i == self._cursor
            draw_selection_marker(screen, row, selected=selected)
            color = ACCENT_GOLD if selected else TEXT
            text = self._menu_font.render(label, True, color)
            screen.blit(text, (cx - text.get_width() // 2, row.centery - text.get_height() // 2))
            if selected:
                pygame.draw.polygon(screen, ACCENT_GOLD, [(row.x + 18, row.centery - 5), (row.x + 24, row.centery), (row.x + 18, row.centery + 5)])

        help_text = _MENU_HELP[self._cursor]
        if TITLE_IDLE and self._idle_timer >= _IDLE_DELAY:
            help_text = TITLE_IDLE[self._idle_index]
        help_label = self._small_font.render(fit_text(self._small_font, help_text, 700), True, TEXT_MUTED)
        screen.blit(help_label, (cx - help_label.get_width() // 2, 506))
        accept = self.game.settings.key_display("ui_accept")
        if self.game.settings.get_key("ui_accept") == pygame.K_RETURN:
            accept += " / SPACE"
        draw_meta_footer(screen, self._small_font, f"↑↓: 選択   {accept}: 決定")
