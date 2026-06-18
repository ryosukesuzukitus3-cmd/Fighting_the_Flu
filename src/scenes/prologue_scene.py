"""プロローグ（SCENE 010）。

NEW GAME 選択直後。ストーリーフラグを初期化し、カロナール先輩の同行開始を
記録してから、プロローグ＋ステージ1開始前の会話を1つの連続したカットシーン
として再生 → GameScene(1) へ。両者は同じ発熱夢の地続きなので途中で区切らない。
"""
from __future__ import annotations
import pygame
from src.core.scene import Scene


class PrologueScene(Scene):
    def on_enter(self) -> None:
        # ストーリー進行フラグを初期化（カロナール先輩 同行開始）
        self.game.story.begin_journey()

        from src.scenes.cutscene_scene import CutsceneScene
        from src.story.script import PROLOGUE, STAGE_INTRO

        def _go_game() -> None:
            from src.scenes.game_scene import GameScene
            self.game.change_scene(GameScene(self.game, stage_id=1))

        # プロローグとステージ1開始前の会話を地続きの1シーンに統合する。
        # 黒フェードは挟まず、最終ページで（他ステージ同様）即ゲーム本編へ。
        pages = list(PROLOGUE) + list(STAGE_INTRO[1])
        self.game.change_scene(CutsceneScene(
            self.game, pages, _go_game,
            theme="dark", stop_bgm=True, fade_out_on_finish=False,
        ))

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((0, 0, 0))
