from __future__ import annotations

import pygame
from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from src.core.scene import Scene
from src.managers.settings import KEY_BINDING_DISPLAY_NAMES
from src.scenes.meta_ui import (
    ACCENT_GOLD, TEXT, TEXT_MUTED, draw_meta_background, draw_meta_footer,
    draw_meta_panel, draw_meta_title, draw_selection_marker, fit_text, wrap_text,
)

_STEP = 0.05
_CATEGORIES = ("音量", "ゲーム操作", "メニュー操作")
_ACCENT = (166, 189, 245)


class SettingsScene(Scene):
    """A keyboard-accessible category row keeps every setting in view."""

    def __init__(self, game, back_scene) -> None:
        super().__init__(game)
        self._back_scene = back_scene

    def on_enter(self) -> None:
        self._font_title = self.game.resources.pixelfont(42)
        self._font_item = self.game.resources.pixelfont(22)
        self._font_small = self.game.resources.pixelfont(18)
        self._items = [
            ("volume", "bgm_volume", "BGM音量"),
            ("volume", "se_volume", "効果音の音量"),
            *(("key", action, label) for action, label in KEY_BINDING_DISPLAY_NAMES.items()),
            ("reset", "reset", "キー設定を初期化"),
        ]
        self._groups = [[], [], []]
        for index, (kind, action, _) in enumerate(self._items):
            group = 0 if kind == "volume" else 2 if action in {"pause", "ui_accept", "ui_back", "reset"} else 1
            self._groups[group].append(index)
        self._category = 0
        self._category_focus = False
        self._cursor = self._groups[0][0]
        self._rebinding: str | None = None
        self._rebind_error = False
        self._suppress_input_once = False
        self._confirm_reset = False
        self._reset_cursor = 1
        self._notice = ""
        self._notice_timer = 0.0

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
        action = self._rebinding
        if self.game.settings.set_key_binding(action, event.key):
            self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
            self._notice = f"{self.game.settings.action_display_name(action)}を {self.game.settings.key_display(action)} に変更しました"
            self._notice_timer = 3.0
            self._rebinding = None
            self._rebind_error = False
            self._suppress_input_once = True
        else:
            self._rebind_error = True

    def _tab_available(self) -> bool:
        return pygame.K_TAB not in {self.game.settings.get_key("ui_accept"), self.game.settings.get_key("ui_back")}

    def _change_category(self, delta: int) -> None:
        self._category = (self._category + delta) % len(self._groups)
        self._cursor = self._groups[self._category][0]
        self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)

    def update(self, dt: float) -> None:
        self._notice_timer = max(0.0, self._notice_timer - dt)
        if self._suppress_input_once:
            self._suppress_input_once = False
            return
        if self._rebinding is not None:
            return
        inp = self.game.input
        back = inp.is_action_just_pressed("ui_back") or inp.is_just_pressed(pygame.K_ESCAPE)
        if self._confirm_reset:
            if back:
                self._confirm_reset = False
            elif inp.is_just_pressed(pygame.K_LEFT) or inp.is_just_pressed(pygame.K_RIGHT):
                self._reset_cursor = 1 - self._reset_cursor
            elif inp.is_action_just_pressed("ui_accept"):
                if self._reset_cursor == 0:
                    self.game.settings.reset_key_bindings()
                    self._notice = "操作キーを初期設定に戻しました"
                    self._notice_timer = 3.0
                    self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
                self._confirm_reset = False
            return
        if back:
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)
            self.game.change_scene(self._back_scene, reinit=False)
            return
        if self._tab_available() and inp.is_just_pressed(pygame.K_TAB):
            self._change_category(1)
            return
        if inp.is_just_pressed(pygame.K_UP):
            self._move_cursor(-1)
        elif inp.is_just_pressed(pygame.K_DOWN):
            self._move_cursor(1)
        if self._category_focus:
            if inp.is_just_pressed(pygame.K_LEFT):
                self._change_category(-1)
            elif inp.is_just_pressed(pygame.K_RIGHT):
                self._change_category(1)
            elif inp.is_action_just_pressed("ui_accept"):
                self._category_focus = False
                self._cursor = self._groups[self._category][0]
            return
        kind, key, _ = self._items[self._cursor]
        if kind == "volume":
            if inp.is_just_pressed(pygame.K_LEFT):
                self._change_volume(key, -_STEP)
            elif inp.is_just_pressed(pygame.K_RIGHT):
                self._change_volume(key, _STEP)
        elif inp.is_action_just_pressed("ui_accept"):
            if kind == "key":
                self._rebinding = key
                self._rebind_error = False
            elif kind == "reset":
                self._confirm_reset = True
                self._reset_cursor = 1

    def _move_cursor(self, delta: int) -> None:
        group = self._groups[self._category]
        if self._category_focus:
            self._category_focus = False
            self._cursor = group[0 if delta > 0 else -1]
        else:
            position = group.index(self._cursor) + delta
            if 0 <= position < len(group):
                self._cursor = group[position]
            else:
                self._category_focus = True
        self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)

    def _change_volume(self, key: str, delta: float) -> None:
        value = round(max(0.0, min(1.0, float(self.game.settings.get(key, 0.8)) + delta)), 2)
        self.game.settings.set(key, value)
        if key == "bgm_volume":
            self.game.sound.set_bgm_volume(value)
        else:
            self.game.sound.set_se_volume(value)
        self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)

    def draw(self, screen: pygame.Surface) -> None:
        draw_meta_background(screen, accent=_ACCENT)
        draw_meta_title(screen, self._font_title, "設定", accent=_ACCENT, y=30)
        for index, name in enumerate(_CATEGORIES):
            tab = pygame.Rect(56 + index * 232, 113, 224, 46)
            active = index == self._category
            draw_meta_panel(screen, tab, accent=_ACCENT, fill=(25, 34, 54, 235) if active else (10, 17, 30, 210))
            draw_selection_marker(screen, tab, selected=active and self._category_focus)
            text = self._font_item.render(name, True, ACCENT_GOLD if active else TEXT_MUTED)
            screen.blit(text, (tab.centerx - text.get_width() // 2, tab.centery - text.get_height() // 2))
            if active:
                pygame.draw.line(screen, ACCENT_GOLD, (tab.x + 18, tab.bottom - 1), (tab.right - 18, tab.bottom - 1), 2)
        panel = pygame.Rect(56, 174, 688, 346)
        draw_meta_panel(screen, panel, accent=_ACCENT)
        for position, index in enumerate(self._groups[self._category]):
            kind, action, label = self._items[index]
            selected = index == self._cursor and not self._category_focus
            row_h, step = (90, 112) if kind == "volume" else (36, 38)
            row = pygame.Rect(panel.x + 18, panel.y + 18 + position * step, panel.w - 36, row_h)
            draw_selection_marker(screen, row, selected=selected)
            color = ACCENT_GOLD if selected else TEXT
            text = self._font_item.render(label, True, color)
            screen.blit(text, (row.x + 18, row.y + 10 if kind == "volume" else row.centery - text.get_height() // 2))
            if kind == "volume":
                value = float(self.game.settings.get(action, 0.8))
                value_text = self._font_item.render(f"{round(value * 100)}%", True, color)
                screen.blit(value_text, (row.right - 18 - value_text.get_width(), row.y + 10))
                bar = pygame.Rect(row.x + 18, row.y + 55, row.w - 36, 12)
                pygame.draw.rect(screen, (44, 55, 76), bar, border_radius=4)
                if value > 0:
                    pygame.draw.rect(screen, (109, 220, 174), (bar.x, bar.y, round(bar.w * value), bar.h), border_radius=4)
            elif kind == "key":
                key_box = pygame.Rect(row.right - 182, row.y + 3, 164, 30)
                pygame.draw.rect(screen, (26, 37, 57), key_box, border_radius=4)
                pygame.draw.rect(screen, (81, 102, 136), key_box, 1, border_radius=4)
                value = fit_text(self._font_small, self.game.settings.key_display(action), key_box.w - 12)
                rendered = self._font_small.render(value, True, color)
                screen.blit(rendered, rendered.get_rect(center=key_box.center))
        if self._category != 1:
            note = "←→で5%ずつ調整できます。" if self._category == 0 else "ゲーム中の移動キーとは別に、メニューは矢印キーで選択します。"
            for i, line in enumerate(wrap_text(self._font_small, note, panel.w - 72)):
                rendered = self._font_small.render(line, True, TEXT_MUTED)
                screen.blit(rendered, (panel.x + 36, 442 + i * 24))
            saved = self._font_small.render("戻ると変更が保存されます。", True, TEXT_MUTED)
            screen.blit(saved, (panel.x + 36, 486))
        accept = self.game.settings.key_display("ui_accept")
        back = self.game.settings.key_display("ui_back")
        if self._category_focus:
            footer = f"←→: 分類   ↓ / {accept}: 項目へ   {back} / ESC: 戻る"
        else:
            kind = self._items[self._cursor][0]
            action = "←→: 音量" if kind == "volume" else f"{accept}: キー変更" if kind == "key" else f"{accept}: 初期化"
            category = "TAB: 分類" if self._tab_available() else "↑で分類へ"
            footer = f"↑↓: 項目   {action}   {category}   {back} / ESC: 戻る"
        if self._notice_timer > 0:
            footer = self._notice
        draw_meta_footer(screen, self._font_small, footer)
        if self._rebinding is not None or self._confirm_reset:
            self._draw_modal(screen, accept, back)

    def _draw_modal(self, screen: pygame.Surface, accept: str, back: str) -> None:
        shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        shade.fill((2, 5, 12, 210))
        screen.blit(shade, (0, 0))
        modal = pygame.Rect(116, 195, 568, 222)
        draw_meta_panel(screen, modal, accent=ACCENT_GOLD, fill=(15, 23, 41, 255))
        if self._rebinding is not None:
            name = self.game.settings.action_display_name(self._rebinding)
            current = self.game.settings.key_display(self._rebinding)
            label = self._font_item.render(f"{name}のキー変更", True, ACCENT_GOLD)
            screen.blit(label, (modal.centerx - label.get_width() // 2, modal.y + 24))
            instructions = [f"現在のキー: {current}", "新しく割り当てるキーを押してください。"]
            if self._rebind_error:
                instructions = ["このキーは設定できません。", "ESC・矢印キーや、決定・戻るとの重複を避けてください。"]
            for i, text in enumerate(instructions):
                rendered = self._font_small.render(fit_text(self._font_small, text, modal.w - 40), True, (255, 163, 151) if self._rebind_error else TEXT)
                screen.blit(rendered, (modal.centerx - rendered.get_width() // 2, modal.y + 90 + i * 36))
            draw_meta_footer(screen, self._font_small, "ESC: 変更せずに戻る")
        else:
            label = self._font_item.render("操作キーを初期設定に戻しますか？", True, ACCENT_GOLD)
            screen.blit(label, (modal.centerx - label.get_width() // 2, modal.y + 26))
            detail = self._font_small.render("すべての操作キーが初期化されます。音量は変わりません。", True, TEXT_MUTED)
            screen.blit(detail, (modal.centerx - detail.get_width() // 2, modal.y + 76))
            for i, option in enumerate(("初期化する", "やめる")):
                rect = pygame.Rect(modal.x + 30 + i * 258, modal.y + 134, 250, 52)
                draw_selection_marker(screen, rect, selected=i == self._reset_cursor)
                rendered = self._font_item.render(option, True, ACCENT_GOLD if i == self._reset_cursor else TEXT)
                screen.blit(rendered, rendered.get_rect(center=rect.center))
            draw_meta_footer(screen, self._font_small, f"←→: 選択   {accept}: 決定   {back} / ESC: やめる")
