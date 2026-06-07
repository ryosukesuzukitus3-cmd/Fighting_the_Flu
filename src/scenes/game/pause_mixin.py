"""ポーズUI ミックスイン — GameScene に多重継承で組み込まれる。"""
from __future__ import annotations
import pygame


class GameScenePauseMixin:
    """ポーズ中の入力処理と描画を担当する。"""

    _PAUSE_ITEMS = ["ゲームに戻る", "設定", "タイトルへ戻る"]

    def _update_pause(self) -> None:
        # UIナビゲーションキー（↑↓ / SPACE / ENTER）はカスタマイズ対象外として固定
        inp = self.game.input  # type: ignore[attr-defined]
        if inp.is_just_pressed(pygame.K_UP):
            self._pause_cursor = (self._pause_cursor - 1) % len(self._PAUSE_ITEMS)  # type: ignore[attr-defined]
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)  # type: ignore[attr-defined]
        if inp.is_just_pressed(pygame.K_DOWN):
            self._pause_cursor = (self._pause_cursor + 1) % len(self._PAUSE_ITEMS)  # type: ignore[attr-defined]
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)  # type: ignore[attr-defined]
        if inp.is_action_just_pressed("pause"):  # type: ignore[attr-defined]
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)  # type: ignore[attr-defined]
            self._paused = False  # type: ignore[attr-defined]
            return
        if inp.is_just_pressed(pygame.K_SPACE) or inp.is_just_pressed(pygame.K_RETURN):
            self._pause_select()

    def _pause_select(self) -> None:
        self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)  # type: ignore[attr-defined]
        if self._pause_cursor == 0:  # type: ignore[attr-defined]
            self._paused = False  # type: ignore[attr-defined]
        elif self._pause_cursor == 1:  # type: ignore[attr-defined]
            from src.scenes.settings_scene import SettingsScene
            self.game.change_scene(SettingsScene(self.game, self))  # type: ignore[attr-defined]
        else:
            from src.scenes.title import TitleScene
            self.game.change_scene(TitleScene(self.game))  # type: ignore[attr-defined]

    def _draw_pause(self, screen: pygame.Surface) -> None:
        if self._pause_font is None:  # type: ignore[attr-defined]
            self._pause_font       = self.game.resources.pixelfont(30)  # type: ignore[attr-defined]
            self._pause_title_font = self.game.resources.pixelfont(46)  # type: ignore[attr-defined]

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        cx = screen.get_width() // 2
        title = self._pause_title_font.render("PAUSE", True, (255, 255, 255))  # type: ignore[attr-defined]
        screen.blit(title, (cx - title.get_width() // 2, 180))

        for i, label in enumerate(self._PAUSE_ITEMS):
            color  = (255, 255, 100) if i == self._pause_cursor else (180, 180, 180)  # type: ignore[attr-defined]
            prefix = "> " if i == self._pause_cursor else "  "  # type: ignore[attr-defined]
            surf   = self._pause_font.render(prefix + label, True, color)  # type: ignore[attr-defined]
            screen.blit(surf, (cx - surf.get_width() // 2, 280 + i * 56))
