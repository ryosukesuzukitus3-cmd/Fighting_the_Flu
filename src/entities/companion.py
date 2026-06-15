"""カロナール先輩 — 澤口の後を追従する随伴スプライト。

台本 §6: 微解熱弾を自動発射し、被弾→撤退→復帰のサイクルを持つ。
薬効最大形態（§7）は Phase 3 で追加予定。
ダミースプライト（緑丸 + "カ" 表示）を使用。後で差し替え予定。
"""
from __future__ import annotations
import math
import random
from typing import Callable, TYPE_CHECKING
import pygame
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT

if TYPE_CHECKING:
    from src.core.game import Game
    from src.core.camera import Camera

# ── 調整パラメータ ─────────────────────────────────────────────────
_MAX_HP           = 1     # 先輩 HP は 1（被弾即撤退 / 薬効最大は落ちない）
_INVINCIBLE_TIME  = 0.8   # 被弾後無敵時間（秒）
_REVIVE_INVINCIBLE = 1.6  # 復帰直後の無敵時間（秒）
_BLINK_INTERVAL   = 0.1
_RETURN_TIME      = 24.0  # 撤退後復帰までの時間（秒・従来の3倍）
_SHOOT_COOLDOWN   = 0.5   # ショットクールダウン（秒）
_FOLLOW_OFFSET_X  = 66.0  # 澤口の左にどれだけ離れて位置取りするか
_FOLLOW_OFFSET_Y  = 46.0  # 澤口の下にどれだけ離れて位置取りするか
_FOLLOW_LERP      = 7.5    # 追従の基本追従率（澤口の speed_multiplier で増減）
_SPRITE_R         = 16    # ダミースプライト半径（px）


def _make_dummy_sprite() -> pygame.Surface:
    """ダミー緑丸スプライト（後で差し替え前提）。"""
    size = _SPRITE_R * 2 + 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(surf, (60, 190, 90), (_SPRITE_R + 1, _SPRITE_R + 1), _SPRITE_R)
    pygame.draw.circle(surf, (150, 255, 170), (_SPRITE_R + 1, _SPRITE_R + 1), _SPRITE_R, 2)
    return surf


_MAX_SPRITE_R = 24   # 薬効最大形態の半径（大型化）


def _make_max_sprite() -> pygame.Surface:
    """薬効最大形態のダミースプライト（大型・白発光・後で差し替え前提）。"""
    r = _MAX_SPRITE_R
    size = r * 2 + 8
    c = size // 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    # 白い外周グロー
    for gr, ga in ((r + 6, 40), (r + 3, 70)):
        pygame.draw.circle(surf, (255, 255, 255, ga), (c, c), gr)
    pygame.draw.circle(surf, (120, 230, 150), (c, c), r)
    pygame.draw.circle(surf, (235, 255, 240), (c, c), r, 3)
    return surf


class Karonaru(pygame.sprite.Sprite):
    """カロナール先輩随伴スプライト（画面座標系）。"""

    def __init__(
        self,
        game: "Game",
        popup_fn: Callable[[str, int, int], None] | None = None,
    ) -> None:
        super().__init__()
        self.game      = game
        self._popup_fn = popup_fn

        self.mode: str = "normal"   # "normal" | "max"（薬効最大）
        self.image = _make_dummy_sprite()
        self.rect  = self.image.get_rect()

        # 画面座標
        self.sx: float = -80.0
        self.sy: float = SCREEN_HEIGHT / 2.0
        self.rect.center = (int(self.sx), int(self.sy))

        # lerp 目標
        self._target_sx: float = self.sx
        self._target_sy: float = self.sy

        # HP / 無敵
        self.hp:     int  = _MAX_HP
        self.max_hp: int  = _MAX_HP
        self._invincible_timer: float = 0.0
        self._blink_timer:      float = 0.0
        self._blink_visible:    bool  = True

        # 状態: "active" | "retired"
        self._state:        str   = "active"
        self._return_timer: float = 0.0

        # ショット
        self._shoot_cooldown: float = _SHOOT_COOLDOWN

    # ── 公開プロパティ ────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self._state == "active"

    @property
    def is_invincible(self) -> bool:
        return self._invincible_timer > 0.0

    @property
    def hit_rect(self) -> pygame.Rect:
        return self.rect.inflate(-8, -8)

    # ── 更新 ─────────────────────────────────────────────────────

    def update(
        self,
        dt: float,
        player,
        player_bullets: pygame.sprite.Group,
        camera: "Camera",
        enemies: pygame.sprite.Group,
    ) -> None:
        if self._state == "retired":
            self._return_timer -= dt
            if self._return_timer <= 0.0:
                self._revive(player)
            return

        # 澤口の左下に位置取りする（軌跡なぞりは廃止。被弾しやすい正面/直線上を外す）。
        # 速度は澤口の速度（weapon.speed_multiplier）に連動して上がる。
        mult = getattr(getattr(player, "weapon", None), "speed_multiplier", 1.0)
        target_x = float(player.rect.centerx) - _FOLLOW_OFFSET_X
        target_y = float(player.rect.centery) + _FOLLOW_OFFSET_Y
        k = min(1.0, _FOLLOW_LERP * mult * dt)
        self.sx += (target_x - self.sx) * k
        self.sy += (target_y - self.sy) * k

        # 壁クランプ
        hw = self.rect.width  // 2
        hh = self.rect.height // 2
        self.sx = max(float(hw), min(float(SCREEN_WIDTH  - hw), self.sx))
        self.sy = max(float(hh), min(float(SCREEN_HEIGHT - hh), self.sy))

        self.rect.center = (int(self.sx), int(self.sy))

        # 無敵・点滅
        if self._invincible_timer > 0.0:
            self._invincible_timer -= dt
            self._blink_timer      += dt
            if self._blink_timer >= _BLINK_INTERVAL:
                self._blink_timer   = 0.0
                self._blink_visible = not self._blink_visible
        else:
            self._blink_visible = True

        # ショット
        self._shoot_cooldown = max(0.0, self._shoot_cooldown - dt)
        if getattr(player, "fire_held", False) and self._shoot_cooldown <= 0.0:
            self._fire(player_bullets, camera)
            self._shoot_cooldown = _SHOOT_COOLDOWN

    def reseed_trail(self, player, *, snap: bool = True) -> None:
        """復帰/合流時に澤口の左下へ位置を合わせる（旧・軌跡シード互換のAPI名）。"""
        if snap:
            self.sx = float(player.rect.centerx) - _FOLLOW_OFFSET_X
            self.sy = float(player.rect.centery) + _FOLLOW_OFFSET_Y
            self.rect.center = (int(self.sx), int(self.sy))

    def _fire(self, player_bullets: pygame.sprite.Group, camera: "Camera") -> None:
        from src.entities.bullets.player_bullet import KaronaruBullet, KaronaruMaxBullet
        world_x = float(self.rect.right) + camera.x
        world_y = float(self.rect.centery)
        if self.mode == "max":
            player_bullets.add(KaronaruMaxBullet(world_x, world_y))
        else:
            player_bullets.add(KaronaruBullet(world_x, world_y))

    # ── 薬効最大形態 ─────────────────────────────────────────────

    def set_max(self) -> None:
        """薬効最大形態へ移行（大型・白発光・高威力弾・撤退しない）。"""
        self.mode    = "max"
        self.image   = _make_max_sprite()
        self.rect    = self.image.get_rect(center=self.rect.center)
        self.max_hp  = 1
        self.hp      = self.max_hp
        self._state  = "active"
        self._invincible_timer = _REVIVE_INVINCIBLE
        self._blink_visible    = True

    # ── 被弾 ─────────────────────────────────────────────────────

    def take_damage(self, amount: int = 1) -> None:
        if self.is_invincible or self._state != "active":
            return
        self.hp -= amount
        self._invincible_timer = _INVINCIBLE_TIME
        self._blink_visible    = True
        self._blink_timer      = 0.0
        self.game.sound.play_se_alias("SE_KARONARU_HIT")
        if self.hp <= 0:
            if self.mode == "max":
                # 薬効最大形態は落ちない（台本「今度は落ちない」）。HP1 で踏みとどまる。
                self.hp = 1
            else:
                self._retire()

    def _retire(self) -> None:
        self._state        = "retired"
        self._return_timer = _RETURN_TIME
        self._blink_visible = True
        self.game.sound.play_se_alias("SE_KARONARU_RETIRE")

    def _revive(self, player) -> None:
        self.hp             = self.max_hp
        self._state         = "active"
        self._invincible_timer = _REVIVE_INVINCIBLE
        self._blink_visible = True
        self._blink_timer   = 0.0
        self.reseed_trail(player)

    # ── 描画 ─────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface) -> None:
        if self._state != "active" or not self._blink_visible:
            return
        surf.blit(self.image, self.rect)
        # HP 表示（緑ピップ）は廃止（先輩のHPは出さない）。
