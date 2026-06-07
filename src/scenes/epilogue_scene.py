"""エンディングエピローグ（SCENE 110）。

story.EPILOGUE をカットシーンとして再生（窓辺の朝の背景）。
全ページ終了後 → GameClearScene へ。内容は src/story/script.py が SSOT。
"""
from __future__ import annotations
import pygame
from src.core.scene import Scene


class EpilogueScene(Scene):
    def on_enter(self) -> None:
        from src.scenes.cutscene_scene import CutsceneScene
        from src.story.script import EPILOGUE

        def _go_clear() -> None:
            from src.scenes.gameclear import GameClearScene
            self.game.change_scene(GameClearScene(self.game))

        self.game.change_scene(CutsceneScene(
            self.game, EPILOGUE, _go_clear,
            theme="window", stop_bgm=True,
        ))

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((0, 0, 0))
