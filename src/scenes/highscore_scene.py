from __future__ import annotations
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT


class HighScoreScene(Scene):
    def on_enter(self) -> None:
        self._font_title = self.game.resources.pixelfont(42)
        self._font_row   = self.game.resources.pixelfont(24)
        self._scores     = self.game.highscore.get_scores()

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        inp = self.game.input
        if inp.is_just_pressed(pygame.K_x):
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)
            from src.scenes.title import TitleScene
            self.game.change_scene(TitleScene(self.game))
        elif inp.is_just_pressed(pygame.K_SPACE):
            self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
            from src.scenes.title import TitleScene
            self.game.change_scene(TitleScene(self.game))

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((10, 10, 25))
        cx = SCREEN_WIDTH // 2

        title = self._font_title.render("HIGH SCORE", True, (255, 220, 60))
        screen.blit(title, (cx - title.get_width() // 2, 50))

        if not self._scores:
            empty = self._font_row.render("--- まだ記録がありません ---", True, (120, 120, 120))
            screen.blit(empty, (cx - empty.get_width() // 2, 240))
        else:
            header = self._font_row.render(
                f"{'RANK':<6}{'NAME':<16}{'SCORE':>8}  {'STAGE':>5}", True, (160, 160, 220)
            )
            screen.blit(header, (cx - 180, 130))
            pygame.draw.line(screen, (80, 80, 120), (cx - 180, 158), (cx + 180, 158))

            for idx, entry in enumerate(self._scores[:10]):
                rank  = entry.get("rank",  idx + 1)
                name  = entry.get("name",  "---")
                score = entry.get("score", 0)
                stage = entry.get("stage", 1)
                color = (255, 220, 60) if idx == 0 else (200, 200, 200)
                row   = self._font_row.render(
                    f"{rank:<6}{name:<16}{score:>8}  {'Stg' + str(stage):>5}", True, color
                )
                screen.blit(row, (cx - 180, 168 + idx * 30))

        hint = self._font_row.render("X / SPACE: タイトルへ戻る", True, (100, 100, 100))
        screen.blit(hint, (cx - hint.get_width() // 2, SCREEN_HEIGHT - 46))
