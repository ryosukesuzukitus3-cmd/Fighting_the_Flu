"""
ステージ前モノローグシーン（全ステージ共通）。
SPACE / ENTER でページを進め、最終ページ後に GameScene へ遷移する。
セリフ内容は src/story/script.py の STAGE_INTRO が SSOT。
"""
from __future__ import annotations
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.scenes.dialogue_panel import DARK_STYLE, draw_story_panel
from src.story.script import STAGE_INTRO

_TYPEWRITER_SPEED = 30.0   # 1秒あたりの文字数
_TYPE_SE_INTERVAL = 0.045
_TYPE_SE_VOLUME = 0.16


class StageIntroScene(Scene):
    def __init__(self, game, stage_id: int) -> None:
        super().__init__(game)
        self._stage_id = stage_id

    def on_enter(self) -> None:
        self._font_name  = self.game.resources.pixelfont(20)
        self._font_body  = self.game.resources.pixelfont(26)
        self._font_hint  = self.game.resources.pixelfont(18)
        self._pages = STAGE_INTRO.get(self._stage_id, STAGE_INTRO[1])
        self._page  = 0
        self._chars = 0.0
        self._blink = 0.0
        self._type_se_cooldown = 0.0
        self._story_active  = None   # 立ち絵ハイライト用（直近に話した登場人物）
        self._story_partner = None   # その前に話した登場人物（会話相手）
        self._track_speaker()

    def _track_speaker(self) -> None:
        from src.story.speakers import is_character
        sp = self._pages[self._page].speaker
        if is_character(sp) and sp != self._story_active:
            self._story_partner = self._story_active
            self._story_active = sp

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def _total_chars(self) -> int:
        return sum(len(ln) for ln in self._pages[self._page].lines)

    def _is_text_complete(self) -> bool:
        return int(self._chars) >= self._total_chars()

    def _tick_type_sound(self, dt: float, previous_chars: int) -> None:
        self._type_se_cooldown = max(0.0, self._type_se_cooldown - dt)
        current_chars = min(int(self._chars), self._total_chars())
        if current_chars > previous_chars and self._type_se_cooldown <= 0.0:
            self.game.sound.play_se_alias("SE_TYPE", volume=_TYPE_SE_VOLUME)
            self._type_se_cooldown = _TYPE_SE_INTERVAL

    def update(self, dt: float) -> None:
        self._blink += dt
        previous_chars = min(int(self._chars), self._total_chars())
        if not self._is_text_complete():
            self._chars = min(self._chars + _TYPEWRITER_SPEED * dt, float(self._total_chars()))
        self._tick_type_sound(dt, previous_chars)

        inp = self.game.input
        # ENTER/SPACE は長押しで連続送り（他の会話シーンと挙動を揃える）
        advance = (inp.is_held_with_repeat(pygame.K_RETURN, 0.25, 0.12)
                   or inp.is_held_with_repeat(pygame.K_SPACE, 0.25, 0.12))
        if advance:
            if not self._is_text_complete():
                self._chars = float(self._total_chars() + 1)
            elif self._page < len(self._pages) - 1:
                self._page += 1
                self._chars = 0.0
                self._type_se_cooldown = 0.0
                self._track_speaker()
            else:
                self._go_game()

        if inp.is_just_pressed(pygame.K_x):
            self._go_game()

    def _go_game(self) -> None:
        from src.scenes.game_scene import GameScene
        self.game.change_scene(GameScene(self.game, stage_id=self._stage_id))

    def draw(self, screen: pygame.Surface) -> None:
        # プロローグ/幕間カットシーンと同じ暗背景に揃え、会話を地続きに見せる。
        screen.fill((8, 8, 20))

        pg = self._pages[self._page]
        is_last = self._pages[self._page].last
        from src.scenes.dialogue_panel import story_sides
        left_sp, right_sp = story_sides(self._story_active, self._story_partner)
        draw_story_panel(
            screen,
            self.game.resources,
            pg.speaker,
            pg.lines,
            left_speaker=left_sp,
            right_speaker=right_sp,
            chars=int(self._chars),
            page_index=self._page,
            total_pages=len(self._pages),
            complete=self._is_text_complete(),
            blink=self._blink,
            hint_last="SPACE: ゲーム開始   X: スキップ" if is_last else "SPACE: 次へ   X: スキップ",
            hint_next="SPACE: 次へ   X: スキップ",
            style=DARK_STYLE,
        )
