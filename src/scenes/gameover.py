import random
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.core.balance import PLAYER_MAX_HP
from src.story.script import GAMEOVER_LINES


class GameOverScene(Scene):
    def on_enter(self) -> None:
        self._title_font = self.game.resources.pixelfont(90)
        self._info_font  = self.game.resources.pixelfont(30)
        self._mono_font  = self.game.resources.pixelfont(22)
        # 台本 §8 のプールからランダムに 1 セット選ぶ
        self._mono_lines = random.choice(GAMEOVER_LINES) if GAMEOVER_LINES else ["力尽きた…"]
        self._score = self.game.shared.score
        self._stage = self.game.shared.stage
        self._lives = self.game.shared.lives
        if self._score > 0:
            self.game.highscore.add("---", self._score, self._stage)

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def _do_continue(self) -> None:
        """現在のステージをステージ開始時のウェポン状態で再スタート。"""
        self.game.shared.lives -= 1
        stage = self._stage
        wdata = self.game.shared.stage_start_weapon
        # HP は最大100制。コンティニューは全回復（残機消費が十分なペナルティ）。
        if wdata is not None:
            self.game.shared.carry_hp     = PLAYER_MAX_HP
            self.game.shared.carry_weapon = wdata
        else:
            self.game.shared.carry_hp     = PLAYER_MAX_HP
            self.game.shared.carry_weapon = None
        from src.scenes.game_scene import GameScene
        self.game.change_scene(GameScene(self.game, stage_id=stage))

    def _do_retry(self) -> None:
        """ステージ1からやり直し（残機リセット）。"""
        from src.scenes.game_scene import GameScene
        self.game.change_scene(GameScene(self.game, stage_id=1))

    def _do_title(self) -> None:
        from src.scenes.title import TitleScene
        self.game.change_scene(TitleScene(self.game))

    def update(self, dt: float) -> None:
        inp = self.game.input
        if self._lives > 0 and inp.is_just_pressed(pygame.K_RETURN):
            self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
            self._do_continue()
        if inp.is_just_pressed(pygame.K_r):
            self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
            self._do_retry()
        if inp.is_just_pressed(pygame.K_x):
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)
            self._do_title()

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((20, 20, 20))
        cx = SCREEN_WIDTH // 2

        died = self._title_font.render("YOU DIED", True, (150, 10, 10))
        screen.blit(died, (cx - died.get_width() // 2, 160))

        for i, line in enumerate(self._mono_lines):
            surf = self._mono_font.render(line, True, (180, 160, 150))
            screen.blit(surf, (cx - surf.get_width() // 2, 285 + i * 30))

        score = self._info_font.render(f"SCORE : {self._score}", True, (200, 200, 200))
        screen.blit(score, (cx - score.get_width() // 2, 360))

        y = 415
        if self._lives > 0:
            cont = self._info_font.render(
                f"ENTER : コンティニュー  (残機 {self._lives})", True, (100, 255, 150)
            )
            screen.blit(cont, (cx - cont.get_width() // 2, y))
            y += 36

        retry = self._info_font.render("R : ステージ1からやり直し", True, (200, 180, 100))
        screen.blit(retry, (cx - retry.get_width() // 2, y))

        title = self._info_font.render("X : タイトルへ", True, (140, 140, 140))
        screen.blit(title, (cx - title.get_width() // 2, y + 36))
