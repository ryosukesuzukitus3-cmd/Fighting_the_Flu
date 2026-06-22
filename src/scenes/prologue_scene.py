"""プロローグ（SCENE 010）。

NEW GAME 選択直後。ストーリーフラグを初期化（カロナール先輩 同行開始）し、
物語タイムラインに沿ってステージ1の直前ビート（プロローグ＋ステージ1
ブリーフィング）を再生 → GameScene(1) へ。会話内容と並びは
src/story/script.py STORY_BEATS が SSOT、再生は story_flow が駆動する。
"""
from __future__ import annotations
import pygame
from src.core.scene import Scene


class PrologueScene(Scene):
    def on_enter(self) -> None:
        # ストーリー進行フラグを初期化（カロナール先輩 同行開始）
        self.game.story.begin_journey()

        from src.scenes.story_flow import start_stage
        start_stage(self.game, 1)

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((0, 0, 0))
