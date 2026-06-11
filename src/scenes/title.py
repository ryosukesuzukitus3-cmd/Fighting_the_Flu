import random
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.story.script import TITLE_IDLE


_MENU = ["ゲームスタート", "チュートリアル", "ハイスコア", "統計", "設定"]

_IDLE_DELAY  = 6.0   # 無操作からアイドルテキスト表示までの秒数
_IDLE_ROTATE = 5.0   # アイドルテキストの切替間隔


class TitleScene(Scene):
    def on_enter(self) -> None:
        self._title_font = self.game.resources.pixelfont(64)
        self._menu_font  = self.game.resources.pixelfont(28)
        self._idle_font  = self.game.resources.pixelfont(20)
        self._cursor     = 0
        self._idle_timer = 0.0
        self._idle_index = random.randrange(len(TITLE_IDLE)) if TITLE_IDLE else 0
        # サブメニューから戻った場合はBGMを再起動しない
        self.game.sound.play_bgm_if_new("music/bgm/The_Final_Battle_short.mp3")

    def on_exit(self) -> None:
        pass  # BGMはサブメニューでも継続させる（ゲーム開始時にgame_sceneが停止する）

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        inp = self.game.input
        moved = False
        if inp.is_just_pressed(pygame.K_UP):
            self._cursor = (self._cursor - 1) % len(_MENU)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
            moved = True
        if inp.is_just_pressed(pygame.K_DOWN):
            self._cursor = (self._cursor + 1) % len(_MENU)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
            moved = True
        if inp.is_just_pressed(pygame.K_SPACE) or inp.is_just_pressed(pygame.K_RETURN):
            self._select()
            moved = True

        # アイドルテキスト: 一定時間ごとに切替（操作でリセット）
        if moved:
            self._idle_timer = 0.0
        else:
            prev = self._idle_timer
            self._idle_timer += dt
            if TITLE_IDLE and prev < _IDLE_DELAY <= self._idle_timer:
                self._idle_index = random.randrange(len(TITLE_IDLE))
            elif self._idle_timer >= _IDLE_DELAY + _IDLE_ROTATE:
                self._idle_timer = _IDLE_DELAY
                self._idle_index = (self._idle_index + 1) % len(TITLE_IDLE)
        if inp.is_just_pressed(pygame.K_d):
            from src.scenes.game_scene import GameScene
            self.game.change_scene(GameScene(self.game, stage_id=99))

    def _select(self) -> None:
        self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
        if self._cursor == 0:
            from src.scenes.prologue_scene import PrologueScene
            self.game.change_scene(PrologueScene(self.game))
        elif self._cursor == 1:
            from src.scenes.tutorial_scene import TutorialScene
            self.game.change_scene(TutorialScene(self.game))
        elif self._cursor == 2:
            from src.scenes.highscore_scene import HighScoreScene
            self.game.change_scene(HighScoreScene(self.game))
        elif self._cursor == 3:
            from src.scenes.stats_scene import StatsScene
            self.game.change_scene(StatsScene(self.game))
        elif self._cursor == 4:
            from src.scenes.settings_scene import SettingsScene
            self.game.change_scene(SettingsScene(self.game, self))

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((20, 20, 20))
        cx = SCREEN_WIDTH // 2

        title = self._title_font.render("インフルとの死闘", True, (180, 70, 30))
        screen.blit(title, (cx - title.get_width() // 2, 140))

        for i, label in enumerate(_MENU):
            color  = (255, 255, 100) if i == self._cursor else (180, 180, 180)
            prefix = "> " if i == self._cursor else "  "
            surf   = self._menu_font.render(prefix + label, True, color)
            screen.blit(surf, (cx - surf.get_width() // 2, 280 + i * 46))

        # アイドルテキスト（無操作時に点滅表示）
        if TITLE_IDLE and self._idle_timer >= _IDLE_DELAY:
            idle = self._idle_font.render(TITLE_IDLE[self._idle_index], True, (120, 110, 90))
            screen.blit(idle, (cx - idle.get_width() // 2, SCREEN_HEIGHT - 78))

        hint = self.game.resources.pixelfont(18).render(
            "↑↓: 選択   SPACE / ENTER: 決定", True, (80, 80, 80)
        )
        screen.blit(hint, (cx - hint.get_width() // 2, SCREEN_HEIGHT - 36))

        dbg = self.game.resources.pixelfont(14).render("D : デバッグステージ", True, (55, 55, 70))
        screen.blit(dbg, (SCREEN_WIDTH - dbg.get_width() - 12, SCREEN_HEIGHT - 26))
