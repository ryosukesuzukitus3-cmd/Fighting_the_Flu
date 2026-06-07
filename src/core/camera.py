import random
from src.core.constants import SCREEN_WIDTH


class Camera:
    def __init__(self, scroll_speed: float = 80.0) -> None:
        self.x: float = 0.0          # ワールド座標の左端（ここが画面左端に対応）
        self.scroll_speed = scroll_speed
        self._shake: float = 0.0     # 残りシェイク強度 (px)

    def shake(self, intensity: float = 8.0) -> None:
        """画面シェイクを追加（既存値より大きい場合のみ上書き）"""
        self._shake = max(self._shake, intensity)

    @property
    def shake_offset(self) -> tuple[int, int]:
        if self._shake <= 0:
            return (0, 0)
        r = int(self._shake)
        return (random.randint(-r, r), random.randint(-r, r))

    def update(self, dt: float) -> None:
        self.x += self.scroll_speed * dt
        if self._shake > 0:
            self._shake = max(0.0, self._shake - 60.0 * dt)

    def to_screen_x(self, world_x: float) -> float:
        return world_x - self.x

    def to_world_x(self, screen_x: float) -> float:
        return screen_x + self.x

    def spawn_x(self, margin: float = 50.0) -> float:
        """敵スポーン用: 画面右端のワールドX座標"""
        return self.x + SCREEN_WIDTH + margin

    def is_off_left(self, world_x: float, width: float = 0.0) -> bool:
        """エンティティが画面左端より外に出たか"""
        return world_x + width < self.x
