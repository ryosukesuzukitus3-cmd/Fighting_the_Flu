"""起動時の注意書きシーン（フィクション表記）。

ゲーム起動直後、タイトル画面の前に一度だけ表示する。
文言の SSOT は src/story/script.py > BOOT_DISCLAIMER。
フェードイン → 保持（キー入力でスキップ可）→ フェードアウト → タイトルへ。
"""
from __future__ import annotations
import pygame

from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.story.script import BOOT_DISCLAIMER

_FADE_IN  = 0.7   # 秒
_HOLD     = 3.4   # 秒（フェードイン後の保持）
_FADE_OUT = 0.7   # 秒


class DisclaimerScene(Scene):
    def on_enter(self) -> None:
        self._font_body  = self.game.resources.pixelfont(22)
        self._timer      = 0.0
        self._leave_t    = -1.0   # 負＝まだ退場していない

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        self._timer += dt
        inp = self.game.input
        skip = (inp.is_action_just_pressed("ui_accept")
                or inp.is_action_just_pressed("ui_back")
                or inp.is_just_pressed(pygame.K_ESCAPE))
        if self._leave_t < 0 and (self._timer >= _FADE_IN + _HOLD or skip):
            self._leave_t = 0.0
        if self._leave_t >= 0:
            self._leave_t += dt
            if self._leave_t >= _FADE_OUT:
                from src.scenes.title import TitleScene
                self.game.change_scene(TitleScene(self.game))

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((8, 8, 12))
        if self._leave_t >= 0:
            alpha = max(0, int(255 * (1.0 - self._leave_t / _FADE_OUT)))
        else:
            alpha = min(255, int(255 * (self._timer / _FADE_IN)))

        line_h = self._font_body.get_linesize() + 10
        total_h = line_h * len(BOOT_DISCLAIMER)
        y = (SCREEN_HEIGHT - total_h) // 2
        for line in BOOT_DISCLAIMER:
            surf = self._font_body.render(line, True, (215, 210, 200))
            surf.set_alpha(alpha)
            screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, y))
            y += line_h
