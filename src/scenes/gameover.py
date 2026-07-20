import random
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH
from src.core.balance import PLAYER_MAX_HP
from src.story.script import GAMEOVER_LINES
from src.scenes.meta_ui import (
    TEXT,
    draw_meta_background,
    draw_meta_footer,
    draw_meta_panel,
    draw_meta_title,
    draw_selection_marker,
)


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
        self._options = (["continue"] if self._lives > 0 else []) + ["retry", "title"]
        self._cursor = 0
        if self._score > 0:
            self.game.highscore.add("---", self._score, self._stage)

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def _do_continue(self) -> None:
        """現在のステージをステージ開始時のウェポン・先輩強化状態で再スタート。"""
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
        # 先輩の強化もステージ開始時の状態で復元（死亡でリセットさせない）
        cdata = self.game.shared.stage_start_companion
        self.game.shared.carry_companion = dict(cdata) if cdata else None
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
        if inp.is_just_pressed(pygame.K_UP):
            self._cursor = (self._cursor - 1) % len(self._options)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
        elif inp.is_just_pressed(pygame.K_DOWN):
            self._cursor = (self._cursor + 1) % len(self._options)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
        elif inp.is_action_just_pressed("ui_accept"):
            self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
            choice = self._options[self._cursor]
            if choice == "continue":
                self._do_continue()
            elif choice == "retry":
                self._do_retry()
            else:
                self._do_title()
        elif inp.is_action_just_pressed("ui_back") or inp.is_just_pressed(pygame.K_ESCAPE):
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)
            self._do_title()

    def draw(self, screen: pygame.Surface) -> None:
        accent = (220, 58, 58)
        draw_meta_background(screen, accent=accent)
        cx = SCREEN_WIDTH // 2
        draw_meta_title(screen, self._title_font, "YOU DIED", accent=accent, y=72)
        panel = pygame.Rect(118, 205, 564, 300)
        draw_meta_panel(screen, panel, accent=accent)

        for i, line in enumerate(self._mono_lines):
            surf = self._mono_font.render(line, True, (180, 160, 150))
            screen.blit(surf, (cx - surf.get_width() // 2, 225 + i * 27))

        score = self._info_font.render(f"SCORE : {self._score}", True, (200, 200, 200))
        screen.blit(score, (cx - score.get_width() // 2, 295))

        labels = {
            "continue": f"有給をもう1日使う（残り{self._lives}日）",
            "retry": "ステージ1からやり直す",
            "title": "タイトルへ戻る",
        }
        y0 = 350
        for i, option in enumerate(self._options):
            selected = i == self._cursor
            rect = pygame.Rect(150, y0 + i * 45, 500, 37)
            draw_selection_marker(screen, rect, selected=selected, accent=(255, 210, 100))
            color = (255, 225, 135) if selected else TEXT
            surf = self._info_font.render(("> " if selected else "  ") + labels[option], True, color)
            screen.blit(surf, (cx - surf.get_width() // 2, rect.y + 5))

        accept = self.game.settings.key_display("ui_accept")
        back = self.game.settings.key_display("ui_back")
        draw_meta_footer(screen, self._mono_font, f"↑↓: 選択   {accept}: 決定   {back} / ESC: タイトルへ")
