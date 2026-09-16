"""ポーズUI ミックスイン — GameScene に多重継承で組み込まれる。"""
from __future__ import annotations
import pygame
from src.scenes.meta_ui import (
    ACCENT_CORAL, BG, TEXT, TEXT_MUTED,
    draw_meta_footer,
    draw_pixel_cursor,
    fit_text,
)


class GameScenePauseMixin:
    """ポーズ中の入力処理と描画を担当する。"""

    _PAUSE_ITEMS = ["ゲームを再開", "設定", "タイトルへ戻る"]

    def _update_pause(self) -> None:
        inp = self.game.input  # type: ignore[attr-defined]
        if inp.is_just_pressed(pygame.K_UP):
            self._pause_cursor = (self._pause_cursor - 1) % len(self._PAUSE_ITEMS)  # type: ignore[attr-defined]
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)  # type: ignore[attr-defined]
        if inp.is_just_pressed(pygame.K_DOWN):
            self._pause_cursor = (self._pause_cursor + 1) % len(self._PAUSE_ITEMS)  # type: ignore[attr-defined]
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)  # type: ignore[attr-defined]
        if (inp.is_action_just_pressed("pause")
                or inp.is_action_just_pressed("ui_back")):  # type: ignore[attr-defined]
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)  # type: ignore[attr-defined]
            self._paused = False  # type: ignore[attr-defined]
            return
        if inp.is_action_just_pressed("ui_accept"):
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
            self._pause_font       = self.game.resources.pixelfont(26)  # type: ignore[attr-defined]
            self._pause_title_font = self.game.resources.pixelfont(34)  # type: ignore[attr-defined]

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((*BG, 200))
        screen.blit(overlay, (0, 0))

        cx = screen.get_width() // 2
        title = self._pause_title_font.render("一時停止", False, TEXT)  # type: ignore[attr-defined]
        screen.blit(title, (cx - title.get_width() // 2, 151))
        small = self.game.resources.pixelfont(16)
        for i, label in enumerate(self._PAUSE_ITEMS):
            selected = i == self._pause_cursor
            color = ACCENT_CORAL if selected else TEXT
            row = pygame.Rect(cx - 130, 243 + i * 62, 330, 52)
            if selected:
                draw_pixel_cursor(screen, row.x - 20, row.centery)
            surf = self._pause_font.render(fit_text(self._pause_font, label, row.w - 65), False, color)
            screen.blit(surf, (row.x + 10, row.centery - surf.get_height() // 2))

        notes = ["止めたところから、そのまま再開します。", "音量とキー操作を変更できます。",
                 "このプレイを終了してタイトルへ戻ります。"]
        note = small.render(notes[self._pause_cursor], False,
                            ACCENT_CORAL if self._pause_cursor == 2 else TEXT_MUTED)
        screen.blit(note, (cx - note.get_width() // 2, 448))

        accept = self.game.settings.key_display("ui_accept")  # type: ignore[attr-defined]
        back = self.game.settings.key_display("ui_back")  # type: ignore[attr-defined]
        draw_meta_footer(
            screen,
            self.game.resources.pixelfont(17),  # type: ignore[attr-defined]
            f"↑↓: 選択   {accept}: 決定   {back}: ゲームを再開",
        )
