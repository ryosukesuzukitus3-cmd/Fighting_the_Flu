from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.entities.weapon import Weapon


def _trim_and_scale(surf: pygame.Surface, scale: float) -> pygame.Surface:
    """透明ピクセルをトリミングしてscale倍にリサイズ"""
    mask   = pygame.mask.from_surface(surf)
    rects  = mask.get_bounding_rects()
    if not rects:
        return surf
    bounding = rects[0].unionall(rects)
    trimmed  = surf.subsurface(bounding).copy()
    new_w = max(1, int(trimmed.get_width()  * scale))
    new_h = max(1, int(trimmed.get_height() * scale))
    return pygame.transform.smoothscale(trimmed, (new_w, new_h))

if TYPE_CHECKING:
    from src.core.game import Game
    from src.core.camera import Camera

from src.core.balance import PLAYER_MAX_HP, PLAYER_INVINCIBLE

_SPEED           = 280.0
_MAX_HP          = PLAYER_MAX_HP   # 多段階 HP ゲージ（最大100）
_INVINCIBLE_TIME = PLAYER_INVINCIBLE
_BLINK_INTERVAL  = 0.1


class Player(pygame.sprite.Sprite):
    def __init__(self, game: Game) -> None:
        super().__init__()
        self.game   = game
        raw = game.resources.image("graphic/sawaguchi_49_64.png")
        self.image  = _trim_and_scale(raw, scale=0.486)
        self.rect   = self.image.get_rect()
        self.weapon = Weapon()

        self._entry_target_sx: float = 120.0
        self.sx: float = -float(self.rect.width + 20)   # 画面外左から入場
        self.sy: float = SCREEN_HEIGHT / 2 - self.rect.height / 2
        self.rect.topleft = (int(self.sx), int(self.sy))
        self._entering: bool = True

        self.hp:     int   = _MAX_HP
        self.max_hp: int   = _MAX_HP
        self._invincible_timer: float = 0.0
        self._blink_timer:      float = 0.0
        self._blink_visible:    bool  = True

        self._cooldown:       float = 0.0
        self.shoot_requested: bool  = False
        self.fire_held:       bool  = False
        self.laser_fire_held: bool  = False   # レーザー用: SPACE長押し状態

    @property
    def is_invincible(self) -> bool:
        return self._invincible_timer > 0.0

    @property
    def hit_rect(self) -> pygame.Rect:
        """当たり判定用の少し小さいRect（見た目より10%小さい）"""
        r = self.rect
        return r.inflate(-int(r.width * 0.1), -int(r.height * 0.1))

    def take_damage(self, amount: int = 1) -> None:
        # HP ゲージ制：被弾は HP を amount 分削るのみ（毎回のウェポン降格は廃止）。
        if self.is_invincible:
            return
        self.hp -= amount
        self._invincible_timer = _INVINCIBLE_TIME
        self._blink_visible    = True
        self._blink_timer      = 0.0

    def restore_state(self, hp: int, weapon_snapshot: dict) -> None:
        """ステージ引き継ぎ: HP とウェポン状態を復元"""
        self.hp = max(1, min(hp, self.max_hp))
        self.weapon.restore(weapon_snapshot)

    def update(self, dt: float) -> None:
        # ── 入場アニメーション（画面左外から右へスライドイン）──────
        if self._entering:
            self.sx += 300.0 * dt
            if self.sx >= self._entry_target_sx:
                self.sx = self._entry_target_sx
                self._entering = False
            self.rect.topleft = (int(self.sx), int(self.sy))
            self._cooldown = max(0.0, self._cooldown - dt)
            self.shoot_requested = False
            self.fire_held = False
            self.laser_fire_held = False
            return

        inp = self.game.input
        dx = dy = 0.0

        if inp.is_action_pressed("move_left"):  dx -= 1.0
        if inp.is_action_pressed("move_right"): dx += 1.0
        if inp.is_action_pressed("move_up"):    dy -= 1.0
        if inp.is_action_pressed("move_down"):  dy += 1.0

        if dx != 0.0 and dy != 0.0:
            dx *= math.sqrt(0.5)
            dy *= math.sqrt(0.5)

        spd = _SPEED * self.weapon.speed_multiplier
        new_sx = max(0.0, min(SCREEN_WIDTH  - self.rect.width,  self.sx + dx * spd * dt))
        new_sy = max(0.0, min(SCREEN_HEIGHT - self.rect.height, self.sy + dy * spd * dt))

        # 斜め入力中に一方の軸が壁でブロックされた場合、
        # もう一方の軸をフル速度に戻す（壁際で速度が落ちるのを防ぐ）
        if dx != 0.0 and dy != 0.0:
            if new_sx == self.sx:  # 水平方向が壁でブロック
                new_sy = max(0.0, min(SCREEN_HEIGHT - self.rect.height,
                                      self.sy + math.copysign(1.0, dy) * spd * dt))
            elif new_sy == self.sy:  # 垂直方向が壁でブロック
                new_sx = max(0.0, min(SCREEN_WIDTH - self.rect.width,
                                      self.sx + math.copysign(1.0, dx) * spd * dt))

        self.sx = new_sx
        self.sy = new_sy
        self.rect.topleft = (int(self.sx), int(self.sy))

        if self._invincible_timer > 0.0:
            self._invincible_timer -= dt
            self._blink_timer += dt
            if self._blink_timer >= _BLINK_INTERVAL:
                self._blink_timer   = 0.0
                self._blink_visible = not self._blink_visible
        else:
            self._blink_visible = True

        self._cooldown = max(0.0, self._cooldown - dt)
        self.weapon._homing_timer = max(0.0, self.weapon._homing_timer - dt)
        self.shoot_requested = False

        # 射撃（長押し連射）・レーザー保持判定（レーザーはVキー専用）
        self.fire_held = inp.is_action_pressed("fire")
        self.laser_fire_held = inp.is_pressed(pygame.K_SPACE)
        if self.fire_held and self._cooldown <= 0.0:
            self.shoot_requested = True
            self._cooldown = self.weapon.shoot_cooldown

    def muzzle_world(self, camera: Camera) -> tuple[float, float]:
        wx = camera.to_world_x(self.sx + self.rect.width)
        wy = self.sy + self.rect.height / 2
        return wx, wy

    def muzzle_screen(self) -> tuple[float, float]:
        """レーザー描画用スクリーン座標マズル位置"""
        return self.sx + self.rect.width, self.sy + self.rect.height / 2

    def draw(self, screen: pygame.Surface) -> None:
        if self._blink_visible:
            screen.blit(self.image, self.rect)
        if self.weapon.has_barrier:
            cx = int(self.sx + self.rect.width  / 2)
            cy = int(self.sy + self.rect.height / 2)
            r  = max(self.rect.width, self.rect.height) // 2 + 10
            pygame.draw.circle(screen, (80, 200, 255), (cx, cy), r, 2)
