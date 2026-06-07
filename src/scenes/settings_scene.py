from __future__ import annotations
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT


_ITEMS = ["BGM音量", "SE音量"]
_STEP  = 0.05


class SettingsScene(Scene):
    """設定画面。呼び出し元シーンを back_scene として受け取り、ESCで戻る。"""

    def __init__(self, game, back_scene) -> None:
        super().__init__(game)
        self._back_scene = back_scene

    def on_enter(self) -> None:
        self._font_title = self.game.resources.pixelfont(42)
        self._font_item  = self.game.resources.pixelfont(28)
        self._cursor     = 0
        self._values     = [
            self.game.settings.get("bgm_volume", 0.8),
            self.game.settings.get("se_volume",  1.0),
        ]

    def on_exit(self) -> None:
        """設定画面を離れるときに一括保存する（毎フレームI/Oを避けるため）"""
        self.game.settings.save()

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        inp = self.game.input
        if inp.is_just_pressed(pygame.K_UP):
            self._cursor = (self._cursor - 1) % len(_ITEMS)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
        if inp.is_just_pressed(pygame.K_DOWN):
            self._cursor = (self._cursor + 1) % len(_ITEMS)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
        if inp.is_just_pressed(pygame.K_LEFT):
            self._change(-_STEP)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
        if inp.is_just_pressed(pygame.K_RIGHT):
            self._change(+_STEP)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
        if inp.is_just_pressed(pygame.K_x):
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)
            self.game.change_scene(self._back_scene, reinit=False)

    def _change(self, delta: float) -> None:
        key = "bgm_volume" if self._cursor == 0 else "se_volume"
        new_val = max(0.0, min(1.0, self._values[self._cursor] + delta))
        self._values[self._cursor] = new_val
        self.game.settings.set(key, new_val)
        if self._cursor == 0:
            self.game.sound.set_bgm_volume(new_val)
        else:
            self.game.sound.set_se_volume(new_val)

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((15, 15, 30))
        cx = SCREEN_WIDTH // 2

        title = self._font_title.render("SETTINGS", True, (200, 200, 255))
        screen.blit(title, (cx - title.get_width() // 2, 80))

        for i, label in enumerate(_ITEMS):
            y     = 220 + i * 90
            color = (255, 255, 100) if i == self._cursor else (180, 180, 180)
            arrow = "> " if i == self._cursor else "  "
            text  = self._font_item.render(f"{arrow}{label}", True, color)
            screen.blit(text, (cx - 180, y))

            # ボリュームバー
            val   = self._values[i]
            bx    = cx - 10
            pygame.draw.rect(screen, (60, 60, 60),  (bx, y + 4, 160, 18), border_radius=4)
            pygame.draw.rect(screen, (100, 200, 100), (bx, y + 4, int(160 * val), 18), border_radius=4)
            pct = self._font_item.render(f"{int(val * 100)}%", True, color)
            screen.blit(pct, (bx + 168, y))

        hint = self.game.resources.pixelfont(20).render(
            "↑↓: 選択  ←→: 変更  X: 戻る", True, (120, 120, 120)
        )
        screen.blit(hint, (cx - hint.get_width() // 2, SCREEN_HEIGHT - 50))
