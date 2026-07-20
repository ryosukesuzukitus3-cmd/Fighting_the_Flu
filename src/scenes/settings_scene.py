from __future__ import annotations

import pygame

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from src.core.scene import Scene
from src.managers.settings import KEY_BINDING_DISPLAY_NAMES
from src.scenes.meta_ui import (
    ACCENT_GOLD,
    TEXT,
    TEXT_MUTED,
    draw_meta_background,
    draw_meta_footer,
    draw_meta_panel,
    draw_meta_title,
    draw_selection_marker,
)


_STEP = 0.05
_VISIBLE_ROWS = 10
class SettingsScene(Scene):
    """Audio and key binding settings with a consistent keyboard UI."""

    def __init__(self, game, back_scene) -> None:
        super().__init__(game)
        self._back_scene = back_scene

    def on_enter(self) -> None:
        self._font_title = self.game.resources.pixelfont(42)
        self._font_item = self.game.resources.pixelfont(21)
        self._font_small = self.game.resources.pixelfont(17)
        self._items = [
            ("volume", "bgm_volume", "BGM音量"),
            ("volume", "se_volume", "SE音量"),
            *(("key", action, label) for action, label in KEY_BINDING_DISPLAY_NAMES.items()),
            ("reset", "reset", "キー設定を初期化"),
        ]
        self._cursor = 0
        self._scroll = 0
        self._rebinding: str | None = None
        self._rebind_error = False
        self._suppress_input_once = False

    def on_exit(self) -> None:
        self.game.settings.save()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._rebinding is None or event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self._rebinding = None
            self._rebind_error = False
            self._suppress_input_once = True
            return
        if self.game.settings.set_key_binding(self._rebinding, event.key):
            self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
            self._rebinding = None
            self._rebind_error = False
            self._suppress_input_once = True
        else:
            self._rebind_error = True

    def update(self, dt: float) -> None:
        if self._suppress_input_once:
            self._suppress_input_once = False
            return
        if self._rebinding is not None:
            return

        inp = self.game.input
        if inp.is_just_pressed(pygame.K_UP):
            self._move_cursor(-1)
        elif inp.is_just_pressed(pygame.K_DOWN):
            self._move_cursor(1)

        kind, key, _ = self._items[self._cursor]
        if kind == "volume":
            if inp.is_just_pressed(pygame.K_LEFT):
                self._change_volume(key, -_STEP)
            elif inp.is_just_pressed(pygame.K_RIGHT):
                self._change_volume(key, _STEP)

        if inp.is_action_just_pressed("ui_accept"):
            if kind == "key":
                self._rebinding = key
                self._rebind_error = False
            elif kind == "reset":
                self.game.settings.reset_key_bindings()
                self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)

        if inp.is_action_just_pressed("ui_back") or inp.is_just_pressed(pygame.K_ESCAPE):
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)
            self.game.change_scene(self._back_scene, reinit=False)

    def _move_cursor(self, delta: int) -> None:
        self._cursor = (self._cursor + delta) % len(self._items)
        if self._cursor < self._scroll:
            self._scroll = self._cursor
        elif self._cursor >= self._scroll + _VISIBLE_ROWS:
            self._scroll = self._cursor - _VISIBLE_ROWS + 1
        self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)

    def _change_volume(self, key: str, delta: float) -> None:
        old = float(self.game.settings.get(key, 0.8))
        value = max(0.0, min(1.0, old + delta))
        self.game.settings.set(key, value)
        if key == "bgm_volume":
            self.game.sound.set_bgm_volume(value)
        else:
            self.game.sound.set_se_volume(value)
        self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)

    def draw(self, screen: pygame.Surface) -> None:
        draw_meta_background(screen, accent=(150, 170, 255))
        draw_meta_title(
            screen,
            self._font_title,
            "SETTINGS",
            accent=(190, 200, 255),
            y=34,
            eyebrow="SYSTEM / CONTROL",
            eyebrow_font=self._font_small,
        )
        panel_rect = pygame.Rect(92, 116, SCREEN_WIDTH - 184, 392)
        draw_meta_panel(screen, panel_rect, accent=(150, 170, 255))

        end = min(len(self._items), self._scroll + _VISIBLE_ROWS)
        for visible_index, item_index in enumerate(range(self._scroll, end)):
            kind, key, label = self._items[item_index]
            selected = item_index == self._cursor
            y = panel_rect.y + 18 + visible_index * 35
            row = pygame.Rect(panel_rect.x + 18, y - 3, panel_rect.w - 36, 31)
            draw_selection_marker(screen, row, selected=selected, accent=(180, 195, 255))
            color = ACCENT_GOLD if selected else TEXT
            prefix = ">" if selected else " "
            text = self._font_item.render(f"{prefix} {label}", True, color)
            screen.blit(text, (row.x + 10, y))

            if kind == "volume":
                value = float(self.game.settings.get(key, 0.8))
                bar = pygame.Rect(row.right - 205, y + 5, 130, 12)
                pygame.draw.rect(screen, (42, 44, 60), bar, border_radius=4)
                pygame.draw.rect(
                    screen,
                    (100, 205, 135),
                    (bar.x, bar.y, int(bar.w * value), bar.h),
                    border_radius=4,
                )
                value_surf = self._font_item.render(f"{int(value * 100):3d}%", True, color)
                screen.blit(value_surf, (row.right - 62, y))
            elif kind == "key":
                value = self.game.settings.key_display(key)
                key_box = pygame.Rect(row.right - 125, y - 1, 105, 25)
                pygame.draw.rect(screen, (25, 28, 45), key_box, border_radius=4)
                pygame.draw.rect(screen, (120, 130, 170), key_box, 1, border_radius=4)
                value_surf = self._font_small.render(value, True, color)
                screen.blit(
                    value_surf,
                    (key_box.centerx - value_surf.get_width() // 2,
                     key_box.centery - value_surf.get_height() // 2),
                )

        if self._scroll > 0:
            up = self._font_small.render("▲", True, TEXT_MUTED)
            screen.blit(up, (panel_rect.right - 28, panel_rect.y + 10))
        if end < len(self._items):
            down = self._font_small.render("▼", True, TEXT_MUTED)
            screen.blit(down, (panel_rect.right - 28, panel_rect.bottom - 28))

        if self._rebinding is not None:
            shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 185))
            screen.blit(shade, (0, 0))
            modal = pygame.Rect(150, 225, 500, 150)
            draw_meta_panel(screen, modal, accent=ACCENT_GOLD, fill=(12, 14, 28, 245))
            prompt = self._font_item.render("割り当てるキーを押してください", True, ACCENT_GOLD)
            cancel_text = (
                "矢印・決定・戻ると競合するキーは設定できません"
                if self._rebind_error
                else "ESC: キャンセル"
            )
            cancel = self._font_small.render(cancel_text, True, TEXT_MUTED)
            screen.blit(prompt, (modal.centerx - prompt.get_width() // 2, modal.y + 40))
            screen.blit(cancel, (modal.centerx - cancel.get_width() // 2, modal.y + 91))
            footer = "キー入力を待っています"
        else:
            kind = self._items[self._cursor][0]
            accept = self.game.settings.key_display("ui_accept")
            action = ("←→: 変更" if kind == "volume"
                      else f"{accept}: キー変更" if kind == "key"
                      else f"{accept}: 実行")
            back = self.game.settings.key_display("ui_back")
            footer = f"↑↓: 選択   {action}   {back} / ESC: 戻る"
        draw_meta_footer(screen, self._font_small, footer)
