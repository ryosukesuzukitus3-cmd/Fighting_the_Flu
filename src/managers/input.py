from __future__ import annotations
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from src.managers.settings import SettingsManager


class InputManager:
    def __init__(self, settings: SettingsManager | None = None) -> None:
        self._pressed:       set[int] = set()
        self._just_pressed:  set[int] = set()
        self._just_released: set[int] = set()
        self._dt:    float = 0.0
        self._repeat_timers: dict[int, float] = {}
        self._settings = settings

    def pre_update(self) -> None:
        """フレーム先頭で just_pressed / just_released をクリア"""
        self._just_pressed.clear()
        self._just_released.clear()

    def handle_event(self, event: pygame.event.Event) -> None:
        """KEYDOWN / KEYUP イベントを受け取り押下状態を更新"""
        if event.type == pygame.KEYDOWN:
            if event.key not in self._pressed:   # OSリピートによる重複KEYDOWN を無視
                self._just_pressed.add(event.key)
            self._pressed.add(event.key)
        elif event.type == pygame.KEYUP:
            self._just_released.add(event.key)
            self._pressed.discard(event.key)
            self._repeat_timers.pop(event.key, None)

    def update(self, dt: float = 0.0) -> None:
        self._dt = dt

    # ── キー直接指定 API ─────────────────────────────────────────

    def is_pressed(self, key: int) -> bool:
        """押しっぱなし（イベント駆動 + pygame.key.get_pressed() のハイブリッド）
        KEYUP の取りこぼしによる斜め移動不能バグを防ぐ。"""
        return key in self._pressed or bool(pygame.key.get_pressed()[key])

    def is_just_pressed(self, key: int) -> bool:
        """押した瞬間のみ True"""
        return key in self._just_pressed

    def is_just_released(self, key: int) -> bool:
        """離した瞬間のみ True"""
        return key in self._just_released

    def is_held_with_repeat(
        self,
        key: int,
        initial_delay: float = 0.15,
        repeat_interval: float = 0.07,
    ) -> bool:
        """長押し時に repeat_interval 間隔で True を返す（ゲーム向け連射制御）"""
        if key not in self._pressed and not pygame.key.get_pressed()[key]:
            return False
        if key in self._just_pressed:
            self._repeat_timers[key] = initial_delay
            return True
        if key in self._repeat_timers:
            self._repeat_timers[key] -= self._dt
            if self._repeat_timers[key] <= 0:
                self._repeat_timers[key] = repeat_interval
                return True
        return False

    # ── アクション名ベース API（設定のキーバインドを参照）────────

    def _key_for(self, action: str) -> int:
        if self._settings is None:
            raise RuntimeError("InputManager: settings が未設定のためアクション名APIは使用不可")
        return self._settings.get_key(action)

    def is_action_pressed(self, action: str) -> bool:
        """アクション名で is_pressed を呼ぶ。設定のキーバインドに従う。"""
        return self.is_pressed(self._key_for(action))

    def is_action_just_pressed(self, action: str) -> bool:
        """アクション名で is_just_pressed を呼ぶ。"""
        return self.is_just_pressed(self._key_for(action))

    def is_action_held_with_repeat(self, action: str, **kwargs) -> bool:
        """アクション名で is_held_with_repeat を呼ぶ。"""
        return self.is_held_with_repeat(self._key_for(action), **kwargs)
