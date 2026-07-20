from __future__ import annotations
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH
from src.scenes.meta_ui import (
    TEXT,
    draw_meta_background,
    draw_meta_footer,
    draw_meta_panel,
    draw_meta_title,
)


class HighScoreScene(Scene):
    def on_enter(self) -> None:
        self._font_title = self.game.resources.pixelfont(42)
        self._font_row   = self.game.resources.pixelfont(24)
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
        accent = (255, 220, 80)
        draw_meta_background(screen, accent=accent)
        cx = SCREEN_WIDTH // 2
        draw_meta_title(screen, self._font_title, "HIGH SCORE", accent=accent, y=36)
        panel = pygame.Rect(150, 112, 500, 400)
        draw_meta_panel(screen, panel, accent=accent)

        if not self._scores:
            empty = self._font_row.render("--- まだ記録がありません ---", True, (120, 120, 120))
            screen.blit(empty, (cx - empty.get_width() // 2, 275))
        else:
            header = self._font_row.render(
                f"{'RANK':<6}{'NAME':<16}{'SCORE':>8}  {'STAGE':>5}", True, (160, 160, 220)
            )
            screen.blit(header, (cx - 180, 137))
            pygame.draw.line(screen, (110, 110, 150), (cx - 180, 165), (cx + 180, 165))

            for idx, entry in enumerate(self._scores[:10]):
                rank  = entry.get("rank",  idx + 1)
                name  = entry.get("name",  "---")
                score = entry.get("score", 0)
                stage = entry.get("stage", 1)
                color = accent if idx == 0 else TEXT
                row   = self._font_row.render(
                    f"{rank:<6}{name:<16}{score:>8}  {'Stg' + str(stage):>5}", True, color
                )
                screen.blit(row, (cx - 180, 175 + idx * 30))

        back = self.game.settings.key_display("ui_back")
        accept = self.game.settings.key_display("ui_accept")
        draw_meta_footer(screen, self._font_hint, f"{back} / {accept} / ESC: タイトルへ戻る")
