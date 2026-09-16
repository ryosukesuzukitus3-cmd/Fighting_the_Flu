"""ポーズUI ミックスイン — GameScene に多重継承で組み込まれる。"""
from __future__ import annotations
import pygame
from src.scenes.meta_ui import (
    ACCENT_GOLD,
    draw_meta_footer,
    draw_meta_panel,
    draw_selection_marker,
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
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        cx = screen.get_width() // 2
        panel = pygame.Rect(cx - 230, 128, 460, 370)
        draw_meta_panel(screen, panel, accent=ACCENT_GOLD, fill=(8, 15, 29, 245))
        title = self._pause_title_font.render("一時停止", True, (240, 243, 250))  # type: ignore[attr-defined]
        screen.blit(title, (cx - title.get_width() // 2, 151))
        small = self.game.resources.pixelfont(16)
        caption = small.render("落ち着いて準備できます。戦闘は停止中です。", True, (175, 188, 205))
        screen.blit(caption, (cx - caption.get_width() // 2, 202))

        for i, label in enumerate(self._PAUSE_ITEMS):
            selected = i == self._pause_cursor
            color = ACCENT_GOLD if selected else (210, 218, 230)
            row = pygame.Rect(panel.x + 36, 243 + i * 62, panel.w - 72, 52)
            draw_selection_marker(screen, row, selected=selected, accent=ACCENT_GOLD)
            if selected:
                pygame.draw.polygon(screen, ACCENT_GOLD, [(row.x + 14, row.centery - 6),
                                                        (row.x + 22, row.centery),
                                                        (row.x + 14, row.centery + 6)])
            surf = self._pause_font.render(fit_text(self._pause_font, label, row.w - 65), True, color)
            screen.blit(surf, (row.x + 40, row.centery - surf.get_height() // 2))

        notes = ["止めたところから、そのまま再開します。", "音量とキー操作を変更できます。",
                 "このプレイを終了してタイトルへ戻ります。"]
        note = small.render(notes[self._pause_cursor], True,
                            (245, 155, 155) if self._pause_cursor == 2 else (175, 188, 205))
        screen.blit(note, (cx - note.get_width() // 2, 448))

        accept = self.game.settings.key_display("ui_accept")  # type: ignore[attr-defined]
        back = self.game.settings.key_display("ui_back")  # type: ignore[attr-defined]
        draw_meta_footer(
            screen,
            self.game.resources.pixelfont(17),  # type: ignore[attr-defined]
            f"↑↓: 選択   {accept}: 決定   {back}: ゲームを再開",
        )
