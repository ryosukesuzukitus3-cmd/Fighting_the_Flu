import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.story.script import GAME_CLEAR
from src.scenes.meta_ui import draw_meta_footer, draw_meta_panel


class GameClearScene(Scene):
    def __init__(self, game, *, record_result: bool = True) -> None:
        # record_result=False はデバッグジャンプ用。ハイスコア/プレイログを汚さない。
        super().__init__(game)
        self._record_result = record_result

    def on_enter(self) -> None:
        self._title_font = self.game.resources.pixelfont(100)
        self._info_font  = self.game.resources.pixelfont(28)
        self._sub_font   = self.game.resources.pixelfont(22)
        self._next_font  = self.game.resources.pixelfont(18)
        self._score = self.game.shared.score
        stage       = self.game.shared.stage
        if self._record_result:
            self.game.highscore.add("---", self._score, stage)
            self.game.playlog.end_run(
                cleared=True,
                score=self._score,
                kill_count=self.game.shared.kill_count,
            )
        self._is_high = self._record_result and \
                        bool(self.game.highscore.get_scores()) and \
                        self.game.highscore.get_scores()[0]["score"] == self._score
        self._timer = 0.0
        self.game.sound.play_bgm("music/bgm/FFVI_勝利のファンファーレ.mp3", loops=0)
        raw = self.game.resources.image("graphic/game_clear_happyend.png")
        self._bg = pygame.transform.smoothscale(raw, (SCREEN_WIDTH, SCREEN_HEIGHT))

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        self._timer += dt
        if self._timer >= 1.5 and self.game.input.is_action_just_pressed("ui_accept"):
            self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
            self._go_credits()

    def _go_credits(self) -> None:
        """エンドロール＋用法・用量注意 → 注意書き（フィクション表記）→ タイトルへ。"""
        from src.scenes.credits_roll import CreditsRollScene
        from src.scenes.disclaimer_scene import DisclaimerScene
        from src.scenes.story_flow import credits_pages

        def _to_disclaimer() -> None:
            self.game.change_scene(DisclaimerScene(self.game))

        self.game.change_scene(CreditsRollScene(
            self.game, credits_pages(), _to_disclaimer,
        ))

    def draw(self, screen: pygame.Surface) -> None:
        screen.blit(self._bg, (0, 0))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2

        clear = self._title_font.render("治癒", True, (255, 220, 100))
        screen.blit(clear, (cx - clear.get_width() // 2, 132))

        card = pygame.Rect(70, 268, 660, 205)
        draw_meta_panel(screen, card, accent=(255, 220, 100), fill=(8, 10, 18, 150))

        sub = self._sub_font.render(GAME_CLEAR["subtitle"], True, (235, 225, 200))
        screen.blit(sub, (cx - sub.get_width() // 2, 292))

        score = self._info_font.render(f"SCORE : {self._score}", True, (200, 200, 200))
        screen.blit(score, (cx - score.get_width() // 2, 336))

        if self._is_high:
            hi = self._info_font.render("★ NEW HIGH SCORE! ★", True, (255, 220, 60))
            screen.blit(hi, (cx - hi.get_width() // 2, 376))

        nxt = self._next_font.render(GAME_CLEAR["next_preview"], True, (150, 150, 170))
        screen.blit(nxt, (cx - nxt.get_width() // 2, 420))

        if self._timer >= 1.5:
            accept = self.game.settings.key_display("ui_accept")
            draw_meta_footer(screen, self._next_font, f"{accept}: スタッフロールへ")
