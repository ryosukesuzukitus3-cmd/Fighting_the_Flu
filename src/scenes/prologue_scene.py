"""プロローグ（SCENE 010）。

NEW GAME 選択直後。ストーリーフラグを初期化し、カロナール先輩の同行開始を
記録してから、プロローグのカットシーンを再生 → StageIntroScene(1) へ。
"""
from __future__ import annotations
import pygame
from src.core.scene import Scene


class PrologueScene(Scene):
    def on_enter(self) -> None:
        # ストーリー進行フラグを初期化（カロナール先輩 同行開始）
        self.game.story.begin_journey()

        from src.scenes.cutscene_scene import CutsceneScene
        from src.scenes.stage_intro_scene import StageIntroScene
        from src.story.script import PROLOGUE

        def _go_stage1() -> None:
            self.game.change_scene(StageIntroScene(self.game, stage_id=1))

        self.game.change_scene(CutsceneScene(
            self.game, PROLOGUE, _go_stage1,
            theme="dark", stop_bgm=True,
        ))

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((0, 0, 0))
