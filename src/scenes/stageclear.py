from __future__ import annotations
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH
from src.core.balance import PLAYER_MAX_HP
from src.scenes.game.config import STAGE_NAMES
from src.entities.weapon import Weapon
from src.scenes.meta_ui import (
    ACCENT_GOLD,
    TEXT,
    TEXT_MUTED,
    draw_meta_background,
    draw_meta_footer,
    draw_meta_panel,
    draw_meta_title,
    fit_text,
)

_INPUT_DELAY = 1.5


class StageClearScene(Scene):
    """ステージ間クリア画面。next_stage_id のゲームシーンへ遷移する。"""

    def __init__(self, game, cleared_stage: int, next_stage_id: int) -> None:
        super().__init__(game)
        self._cleared_stage = cleared_stage
        self._next_stage_id = next_stage_id

    def on_enter(self) -> None:
        self._title_font = self.game.resources.pixelfont(44)
        self._info_font  = self.game.resources.pixelfont(26)
        self._small_font = self.game.resources.pixelfont(18)
        self._score      = self.game.shared.score
        self._kills      = self.game.shared.kill_count
        self._remaining_hp = self.game.shared.carry_hp
        self._weapon     = self.game.shared.carry_weapon or {}
        self._lives      = self.game.shared.lives
        self._timer      = 0.0
        self.game.sound.stop_bgm(fadeout_ms=600)

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        self._timer += dt
        if self._timer >= _INPUT_DELAY:
            if self.game.input.is_action_just_pressed("ui_accept"):
                self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
                self._advance()

    def _advance(self) -> None:
        """次ステージの直前ビート（幕間／導入／ブラックホール）を再生して本編へ。

        どの幕間を挟むか・フラグ更新は物語タイムライン（STORY_BEATS）が持つので、
        ここはステージ番号を渡して story_flow に委譲するだけでよい。
        """
        from src.scenes.story_flow import start_stage
        start_stage(self.game, self._next_stage_id)

    def draw(self, screen: pygame.Surface) -> None:
        accent = (132, 225, 194)
        draw_meta_background(screen, accent=accent)
        cx = SCREEN_WIDTH // 2
        chapter, stage_name, _ = STAGE_NAMES.get(
            self._cleared_stage, (f"第{self._cleared_stage}章", "", "")
        )
        next_chapter, next_name, _ = STAGE_NAMES.get(
            self._next_stage_id, (f"第{self._next_stage_id}章", "", "")
        )
        draw_meta_title(
            screen,
            self._title_font,
            f"{chapter}  クリア",
            accent=accent,
            y=52,
            eyebrow=stage_name,
            eyebrow_font=self._small_font,
        )
        panel = pygame.Rect(90, 144, 620, 290)
        draw_meta_panel(screen, panel, accent=accent)

        main_level = max(0, min(int(self._weapon.get("main_level", 0)), len(Weapon._MAIN_LEVELS) - 1))
        stats = [
            ("累計スコア", f"{self._score:,}"),
            ("累計撃破数", f"{self._kills:,} 体"),
            ("残りHP", "—" if self._remaining_hp is None else f"{self._remaining_hp} / {PLAYER_MAX_HP}"),
            ("メイン武器", Weapon._MAIN_LEVELS[main_level].upper()),
            ("残り有給", f"{self._lives} 日"),
        ]
        for i, (label, value) in enumerate(stats):
            y = panel.y + 24 + i * 49
            ls = self._small_font.render(label, True, TEXT_MUTED)
            color = ACCENT_GOLD if i == 0 else accent if i == 2 else TEXT
            vs = self._info_font.render(fit_text(self._info_font, value, 330), True, color)
            screen.blit(ls, (panel.x + 28, y + 5))
            screen.blit(vs, (panel.right - 28 - vs.get_width(), y))
            if i < len(stats) - 1:
                pygame.draw.line(screen, (46, 60, 79), (panel.x + 28, y + 41), (panel.right - 28, y + 41))

        next_label = self._small_font.render(
            fit_text(self._small_font, f"次は {next_chapter}  {next_name}", 660), True, accent
        )
        screen.blit(next_label, (cx - next_label.get_width() // 2, 450))
        carry = self._small_font.render("HP・武器・先輩の強化を引き継いで進みます", True, TEXT_MUTED)
        screen.blit(carry, carry.get_rect(centerx=cx, y=482))

        if self._timer >= _INPUT_DELAY:
            accept = self.game.settings.key_display("ui_accept")
            footer = f"{accept}: {next_chapter}へ進む"
        else:
            footer = "クリア結果を表示しています…"
        draw_meta_footer(screen, self._small_font, footer)
