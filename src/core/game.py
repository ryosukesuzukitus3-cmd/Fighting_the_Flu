from __future__ import annotations
import math
from collections.abc import Iterable
import pygame

from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE
from src.core.event_bus import EventBus
from src.core.frame_clock import frame_time
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
        self._started = False
        self._running = False
        self._closed = False
        self._fade_timer = 0.0
        self._fade_veil: pygame.Surface | None = None
        self.elapsed_time = 0.0
        self.allow_debug = True

    def start_new_run(self) -> None:
        """Reset a whole journey explicitly; entering stage 1 can also be a continue."""
        self.shared = GameState()
        self.story.begin_journey()
        self.playlog.begin_run()

    def change_scene(self, scene: Scene, reinit: bool = True) -> None:
        """シーン遷移。reinit=False のとき on_enter() を呼ばずに復帰する。"""
        self._next_scene  = scene
        self._next_reinit = reinit

    def start(self) -> None:
        """Prepare normal startup once; the first step enters the initial scene."""
        if self._closed:
            raise RuntimeError("Cannot restart a closed Game")
        if self._started:
            return
        from src.scenes.disclaimer_scene import DisclaimerScene
        if self._scene is None and self._next_scene is None:
            self.change_scene(DisclaimerScene(self))
        self._started = True
        self._running = True

    def step(
        self,
        dt: float,
        events: Iterable[pygame.event.Event] | None = None,
        allow_debug: bool = True,
    ) -> bool:
        """Run one ordinary frame. Waiting callers must not call this method.

        Explicit events replace the OS queue for this frame. Pair them with an
        InputManager(physical_input=False) for command-only input. A QUIT event
        returns False before update/draw; close() remains the caller's job.
        """
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("dt must be finite and non-negative")
        if self._closed:
            return False
        self.start()
        if not self._running:
            return False

        self.allow_debug = allow_debug
        with frame_time(self.elapsed_time + dt):
            if self._next_scene is not None:
                if self._scene is not None:
                    self._scene.on_exit()
                self._scene      = self._next_scene
                self._next_scene = None
                reinit = self._next_reinit
                self._next_reinit = True   # フラグをデフォルトにリセット
                if reinit:
                    self._scene.on_enter()
                # Resuming play/settings must reveal the existing screen immediately.
                # Narrative scenes own their fades; only menus use this short transition.
                self._fade_timer = (
                    0.35
                    if reinit and type(self._scene).__name__ in
                    {"TitleScene", "GameOverScene", "StageClearScene", "HighScoreScene"}
                    else 0.0
                )

            # Preserve transition -> pre_update -> event reading order. The
            # real-time playtest input injects events from pre_update.
            self.input.pre_update()
            frame_events = list(pygame.event.get() if events is None else events)
            if any(event.type == pygame.QUIT for event in frame_events):
                self._running = False
                return False

            self.elapsed_time += dt
            for event in frame_events:
                self.input.handle_event(event)
                self._scene.handle_event(event)

            self.input.update(dt)
            if __debug__ and allow_debug:
                from src.core.debug import handle_global_debug_input
                if handle_global_debug_input(self):
                    return True
            self._scene.update(dt)
            self._scene.draw(self.screen)

            if self._fade_timer > 0.0:
                self._fade_timer = max(0.0, self._fade_timer - dt)
                alpha = int(255 * (self._fade_timer / 0.35))
                if alpha > 0:
                    if self._fade_veil is None:
                        self._fade_veil = pygame.Surface(self.screen.get_size())
                        self._fade_veil.fill((0, 0, 0))
                    self._fade_veil.set_alpha(alpha)
                    self.screen.blit(self._fade_veil, (0, 0))

            pygame.display.flip()
        return True

    def close(self) -> None:
        """Save and release pygame once, without terminating the caller process."""
        if self._closed:
            return
        self._closed = True
        self._running = False
        try:
            self.settings.save()
        finally:
            pygame.quit()

    def run(self) -> None:
        try:
            self.start()
            while self.step(self.clock.tick(FPS) / 1000.0):
                pass
        finally:
            self.close()
