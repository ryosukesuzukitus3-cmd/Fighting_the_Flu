import random
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH
from src.core.balance import PLAYER_MAX_HP
from src.story.script import GAMEOVER_LINES
from src.scenes.meta_ui import (
    ACCENT_CORAL,
    TEXT,
    TEXT_MUTED,
    draw_meta_background,
    draw_meta_footer,
    draw_meta_title,
    draw_pixel_cursor,
    fit_text,
    wrap_text,
)


class GameOverScene(Scene):
    def on_enter(self) -> None:
        self._title_font = self.game.resources.pixelfont(46)
        self._info_font  = self.game.resources.pixelfont(24)
        self._mono_font  = self.game.resources.pixelfont(20)
        self._hint_font  = self.game.resources.pixelfont(18)
        # 台本 §8 のプールからランダムに 1 セット選ぶ
        self._mono_lines = random.choice(GAMEOVER_LINES) if GAMEOVER_LINES else ["力尽きた…"]
        self._score = self.game.shared.score
        self._stage = self.game.shared.stage
        self._lives = self.game.shared.lives
        self._options = ["continue", "retry", "title"]
        self._cursor = 0
        if self._score > 0:
            self.game.highscore.add("---", self._score, self._stage)

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def _do_continue(self) -> None:
        """Restore the last rest point without a retry limit or reward duplication."""
        import copy
        shared = self.game.shared
        cp = shared.checkpoint
        self.game.playlog.begin_run()
        if cp and cp["stage"] == self._stage:
            self.game.story.restore(cp["story"])
            shared.carry_hp = PLAYER_MAX_HP
            shared.carry_weapon = copy.deepcopy(cp["weapon"])
            shared.carry_companion = copy.deepcopy(cp["companion"])
            shared.score, shared.kill_count = cp["score"], cp["kills"]
            shared.support_pickups = cp["support_pickups"]
            shared.resume_checkpoint = True
        else:
            if shared.stage_start_story:
                self.game.story.restore(shared.stage_start_story)
            shared.carry_hp = PLAYER_MAX_HP
            shared.carry_weapon = copy.deepcopy(shared.stage_start_weapon)
            shared.carry_companion = copy.deepcopy(shared.stage_start_companion)
        from src.scenes.game_scene import GameScene
        self.game.change_scene(GameScene(self.game, stage_id=self._stage))

    def _do_retry(self) -> None:
        """ステージ1からやり直し（残機リセット）。"""
        self.game.start_new_run()
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
        accent = ACCENT_CORAL
        draw_meta_background(screen)
        cx = SCREEN_WIDTH // 2
        draw_meta_title(screen, self._title_font, "力尽きた…", accent=accent, y=24)
        y = 112
        for line in self._mono_lines:
            for part in wrap_text(self._mono_font, line, 660):
                surf = self._mono_font.render(part, False, TEXT_MUTED)
                screen.blit(surf, surf.get_rect(centerx=cx, y=y))
                y += 27

        label = self._hint_font.render(f"第{self._stage}章まで到達", False, TEXT_MUTED)
        screen.blit(label, (94, 210))
        score = self._info_font.render(
            fit_text(self._info_font, f"スコア {self._score:,}", 400), False, TEXT,
        )
        screen.blit(score, score.get_rect(right=706, y=205))
        life_text = f"再挑戦 {self.game.shared.deaths}回 / 回数制限なし"
        life = self._hint_font.render(fit_text(self._hint_font, life_text, 612), False, accent)
        screen.blit(life, (94, 247))
        labels = {
            "continue": "直前の休息地点から再挑戦",
            "retry": "最初からやり直す",
            "title": "タイトルへ戻る",
        }
        details = {
            "continue": "HP全回復・休息地点の強化で再開",
            "retry": "スコア・強化を初期状態にして第一章へ",
            "title": "このプレイを終えてタイトルへ",
        }
        for i, option in enumerate(self._options):
            selected = i == self._cursor
            rect = pygame.Rect(86, 284 + i * 72, 628, 66)
            color = ACCENT_CORAL if selected else TEXT
            surf = self._info_font.render(labels[option], False, color)
            screen.blit(surf, (108, rect.y + 3))
            if selected:
                draw_pixel_cursor(screen, 86, rect.y + 3 + surf.get_height() // 2)
            detail = self._hint_font.render(fit_text(self._hint_font, details[option], 584), False, TEXT_MUTED)
            screen.blit(detail, (108, rect.y + 36))

        accept = self.game.settings.key_display("ui_accept")
        back = self.game.settings.key_display("ui_back")
        back_keys = " / ".join(dict.fromkeys((back, "ESC")))
        draw_meta_footer(screen, self._hint_font, f"↑↓: 選択   {accept}: 決定   {back_keys}: タイトルへ")
