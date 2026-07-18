from __future__ import annotations
import sys
import pygame

from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE
from src.core.event_bus import EventBus
from src.core.game_state import GameState
from src.core.scene import Scene
from src.managers.resource import ResourceManager
from src.managers.input import InputManager
from src.managers.sound import SoundManager
from src.managers.settings import SettingsManager
from src.managers.highscore import HighScoreManager
from src.managers.playlog import PlayLogger
from src.story.state import StoryState


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.mixer.set_num_channels(64)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()

        # マネージャー初期化
        self.event_bus  = EventBus()
        self.settings   = SettingsManager()
        self.resources  = ResourceManager()
        self.input      = InputManager(self.settings)   # キーバインドをsettingsから参照
        self.sound      = SoundManager(self.resources, self.settings)
        self.highscore  = HighScoreManager()
        self.playlog    = PlayLogger()

        # シーン間で共有するゲーム状態（型安全なdataclass）
        self.shared = GameState()

        # ストーリー進行フラグ（カロナール先輩の同行状況など）
        self.story = StoryState()

        self._scene: Scene | None = None
        self._next_scene: Scene | None = None
        self._next_reinit: bool = True

    def change_scene(self, scene: Scene, reinit: bool = True) -> None:
        """シーン遷移。reinit=False のとき on_enter() を呼ばずに復帰する。"""
        self._next_scene  = scene
        self._next_reinit = reinit

    def run(self) -> None:
        from src.scenes.disclaimer_scene import DisclaimerScene
        handle_debug_input = None
        if __debug__:
            from src.core.debug import handle_global_debug_input
            handle_debug_input = handle_global_debug_input

        # 起動時はフィクション注意書き → タイトルの順（遷移は DisclaimerScene 側）
        self.change_scene(DisclaimerScene(self))

        # 全シーン共通のフェードイン（切替の瞬間のパッと変わる感じを消す）
        _SCENE_FADE_SEC = 0.35
        fade_timer = 0.0
        fade_veil: pygame.Surface | None = None

        running = True
        while running:
            delta_time = self.clock.tick(FPS) / 1000.0

            # シーン切替
            if self._next_scene is not None:
                if self._scene is not None:
                    self._scene.on_exit()
                self._scene      = self._next_scene
                self._next_scene = None
                reinit = self._next_reinit
                self._next_reinit = True   # フラグをデフォルトにリセット
                if reinit:
                    self._scene.on_enter()
                fade_timer = _SCENE_FADE_SEC

            # フレーム先頭: just_pressed/released をクリア
            self.input.pre_update()

            # イベント処理
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self.input.handle_event(event)
                self._scene.handle_event(event)

            self.input.update(delta_time)
            if handle_debug_input is not None and handle_debug_input(self):
                continue
            self._scene.update(delta_time)
            self._scene.draw(self.screen)

            if fade_timer > 0.0:
                fade_timer = max(0.0, fade_timer - delta_time)
                alpha = int(255 * (fade_timer / _SCENE_FADE_SEC))
                if alpha > 0:
                    if fade_veil is None:
                        fade_veil = pygame.Surface(self.screen.get_size())
                        fade_veil.fill((0, 0, 0))
                    fade_veil.set_alpha(alpha)
                    self.screen.blit(fade_veil, (0, 0))

            pygame.display.flip()

        self.settings.save()  # 強制終了時も設定を必ず保存
        pygame.quit()
        sys.exit()
