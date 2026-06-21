from __future__ import annotations
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT

_INPUT_DELAY = 1.5


class StageClearScene(Scene):
    """ステージ間クリア画面。next_stage_id のゲームシーンへ遷移する。"""

    def __init__(self, game, cleared_stage: int, next_stage_id: int) -> None:
        super().__init__(game)
        self._cleared_stage = cleared_stage
        self._next_stage_id = next_stage_id

    def on_enter(self) -> None:
        self._title_font = self.game.resources.pixelfont(60)
        self._info_font  = self.game.resources.pixelfont(26)
        self._score      = self.game.shared.score
        self._timer      = 0.0
        self.game.sound.stop_bgm(fadeout_ms=600)

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        self._timer += dt
        if self._timer >= _INPUT_DELAY:
            if self.game.input.is_just_pressed(pygame.K_RETURN):
                self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
                self._advance()

    def _advance(self) -> None:
        """クリアしたステージに応じて、幕間カットシーンを挟んで次へ。"""
        from src.scenes.stage_intro_scene import StageIntroScene
        from src.scenes.cutscene_scene import CutsceneScene
        from src.story.script import (
            INTERLUDE_STAGE1_CLEAR, INTERLUDE_STAGE3_BLACKHOLE, STAGE_INTRO,
        )

        def _to_next() -> None:
            self.game.change_scene(StageIntroScene(self.game, stage_id=self._next_stage_id))

        if self._cleared_stage == 1:
            # Stage1 幕間と Stage2 開始前会話を地続きの1シーンに統合する。
            # 別シーンに分けず連結することで、間の黒フェードの切れ目を無くす
            # （PROLOGUE + STAGE_INTRO[1] と同じ手法）。完了で直接ゲーム本編へ。
            from src.scenes.game_scene import GameScene

            def _to_stage2() -> None:
                self.game.change_scene(GameScene(self.game, stage_id=self._next_stage_id))

            pages = list(INTERLUDE_STAGE1_CLEAR) + list(STAGE_INTRO[self._next_stage_id])
            self.game.change_scene(CutsceneScene(
                self.game, pages, _to_stage2, theme="dark",
                bgm_alias="music/bgm/Death_by_Glamour.mp3",
                fade_out_on_finish=False))
        elif self._cleared_stage == 3:
            # 承認欲求ブラックホール（相棒の自己犠牲）。カットシーン完了でフラグ更新。
            def _blackhole_done() -> None:
                self.game.story.karonaru_available = False
                self.game.story.karonaru_lost       = True
                self.game.story.blackhole_event_done = True
                _to_next()

            from src.scenes.blackhole_scene import BlackholeScene
            self.game.change_scene(BlackholeScene(
                self.game, INTERLUDE_STAGE3_BLACKHOLE, _blackhole_done))
        else:
            _to_next()

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((10, 20, 35))
        cx = SCREEN_WIDTH // 2

        title = self._title_font.render(f"STAGE {self._cleared_stage}  CLEAR", True, (100, 220, 255))
        screen.blit(title, (cx - title.get_width() // 2, 130))

        score = self._info_font.render(f"SCORE : {self._score}", True, (200, 200, 200))
        screen.blit(score, (cx - score.get_width() // 2, 220))

        if self._timer >= _INPUT_DELAY:
            hint = self._info_font.render(
                f"ENTER : STAGE {self._next_stage_id} へ", True, (140, 200, 140)
            )
            screen.blit(hint, (cx - hint.get_width() // 2, 300))
