import random
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH
from src.core.balance import PLAYER_MAX_HP
from src.story.script import GAMEOVER_LINES
from src.scenes.meta_ui import (
    ACCENT_GOLD,
    TEXT,
    TEXT_MUTED,
    draw_meta_background,
    draw_meta_footer,
    draw_meta_panel,
    draw_meta_title,
    draw_selection_marker,
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
        self._options = (["continue"] if self._lives > 0 else []) + ["retry", "title"]
        self._cursor = 0
        if self._score > 0:
            self.game.highscore.add("---", self._score, self._stage)

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def _do_continue(self) -> None:
        """現在のステージをステージ開始時のウェポン・先輩強化状態で再スタート。"""
        if self.game.shared.lives <= 0:
            return
        self.game.shared.lives -= 1
        self.game.playlog.begin_run()
        if self.game.shared.stage_start_story is not None:
            self.game.story.restore(self.game.shared.stage_start_story)
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
        accent = (241, 145, 139)
        draw_meta_background(screen, accent=accent)
        cx = SCREEN_WIDTH // 2
        draw_meta_title(screen, self._title_font, "力尽きた…", accent=accent, y=24)
        y = 112
        for line in self._mono_lines:
            for part in wrap_text(self._mono_font, line, 660):
                surf = self._mono_font.render(part, True, TEXT_MUTED)
                screen.blit(surf, surf.get_rect(centerx=cx, y=y))
                y += 27

        panel = pygame.Rect(70, 190, 660, 110 + len(self._options) * 72)
        draw_meta_panel(screen, panel, accent=accent)
        label = self._hint_font.render(f"第{self._stage}章まで到達", True, TEXT_MUTED)
        screen.blit(label, (94, 210))
        score = self._info_font.render(
            fit_text(self._info_font, f"スコア {self._score:,}", 400), True, TEXT,
        )
        screen.blit(score, score.get_rect(right=706, y=205))
        life_text = f"残り有給 {self._lives}日" if self._lives else "有給は残っていません"
        life = self._hint_font.render(fit_text(self._hint_font, life_text, 612), True, accent)
        screen.blit(life, (94, 247))
        labels = {
            "continue": "有給を1日使って続ける",
            "retry": "最初からやり直す",
            "title": "タイトルへ戻る",
        }
        details = {
            "continue": "今の章をHP全回復・章開始時の強化で再開",
            "retry": "スコア・強化・有給を初期状態にして第一章へ",
            "title": "このプレイを終えてタイトルへ",
        }
        for i, option in enumerate(self._options):
            selected = i == self._cursor
            rect = pygame.Rect(86, 284 + i * 72, 628, 66)
            draw_selection_marker(screen, rect, selected=selected, accent=ACCENT_GOLD)
            color = ACCENT_GOLD if selected else TEXT
            surf = self._info_font.render(labels[option], True, color)
            screen.blit(surf, (108, rect.y + 3))
            detail = self._hint_font.render(fit_text(self._hint_font, details[option], 584), True, TEXT_MUTED)
            screen.blit(detail, (108, rect.y + 36))

        accept = self.game.settings.key_display("ui_accept")
        back = self.game.settings.key_display("ui_back")
        back_keys = " / ".join(dict.fromkeys((back, "ESC")))
        draw_meta_footer(screen, self._hint_font, f"↑↓: 選択   {accept}: 決定   {back_keys}: タイトルへ")
