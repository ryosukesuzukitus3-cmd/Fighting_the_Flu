from __future__ import annotations
import pygame
from src.core.scene import Scene
from src.scenes.meta_ui import (
    ACCENT_MINT,
    TEXT,
    TEXT_MUTED,
    draw_meta_background,
    draw_meta_footer,
    draw_meta_title,
    fit_text,
)


class HighScoreScene(Scene):
    def on_enter(self) -> None:
        self._font_title = self.game.resources.pixelfont(38)
        self._font_row   = self.game.resources.pixelfont(22)
        self._font_hint  = self.game.resources.pixelfont(18)
        self._scores     = self.game.highscore.get_scores()

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        inp = self.game.input
        if (inp.is_action_just_pressed("ui_back")
                or inp.is_action_just_pressed("ui_accept")
                or inp.is_just_pressed(pygame.K_ESCAPE)):
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)
            from src.scenes.title import TitleScene
            self.game.change_scene(TitleScene(self.game))
    def draw(self, screen: pygame.Surface) -> None:
        draw_meta_background(screen)
        draw_meta_title(screen, self._font_title, "ハイスコア", accent=TEXT, y=28)

        if not self._scores:
            for text, font, y, color in (
                ("まだ記録がありません", self._font_row, 262, TEXT),
                ("プレイを終えると、ここにスコアが残ります。", self._font_hint, 306, TEXT_MUTED),
            ):
                surface = font.render(text, False, color)
                screen.blit(surface, surface.get_rect(centerx=400, y=y))
        else:
            # Separate columns keep Japanese names and proportional glyphs aligned.
            columns = ((94, 58), (170, 180), (366, 220), (606, 100))
            for (left, width), label in zip(columns, ("順位", "名前", "スコア", "到達章")):
                surface = self._font_hint.render(label, False, TEXT_MUTED)
                x = left + width - surface.get_width() if label == "スコア" else left
                screen.blit(surface, (x, 132))
            for idx, entry in enumerate(self._scores[:10]):
                y = 174 + idx * 32
                color = ACCENT_MINT if idx == 0 else TEXT
                values = (
                    str(entry.get("rank", idx + 1)), str(entry.get("name", "---")),
                    f"{entry.get('score', 0):,}", f"第{entry.get('stage', 1)}章",
                )
                for column, ((left, width), value) in enumerate(zip(columns, values)):
                    surface = self._font_row.render(fit_text(self._font_row, value, width), False, color)
                    x = left + width - surface.get_width() if column == 2 else left
                    screen.blit(surface, (x, y))

        back = self.game.settings.key_display("ui_back")
        accept = self.game.settings.key_display("ui_accept")
        keys = " / ".join(dict.fromkeys((accept, back, "ESC")))
        draw_meta_footer(screen, self._font_hint, f"{keys}: タイトルへ戻る")
