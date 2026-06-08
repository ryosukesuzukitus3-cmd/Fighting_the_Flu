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
        from src.story.script import INTERLUDE_STAGE1_CLEAR, INTERLUDE_STAGE3_BLACKHOLE

        def _to_next() -> None:
            self.game.change_scene(StageIntroScene(self.game, stage_id=self._next_stage_id))

        if self._cleared_stage == 1:
            self.game.change_scene(CutsceneScene(
                self.game, INTERLUDE_STAGE1_CLEAR, _to_next, theme="dark",
                bgm_alias="music/bgm/Death_by_Glamour.mp3"))
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
