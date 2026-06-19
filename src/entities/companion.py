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
_INVINCIBLE_TIME  = 0.8   # 被弾後無敵時間（秒）
_REVIVE_INVINCIBLE = 1.6  # 復帰直後の無敵時間（秒）
_BLINK_INTERVAL   = 0.1
_RETURN_TIME      = 24.0  # 撤退後復帰までの時間（秒・従来の3倍）
_SHOOT_COOLDOWN   = 0.5   # ショットクールダウン（秒）
_FOLLOW_OFFSET_X  = 44.0  # 澤口の左にどれだけ離れて位置取りするか
_FOLLOW_OFFSET_Y  = 30.0  # 澤口の下にどれだけ離れて位置取りするか
_FOLLOW_LERP      = 7.5    # 追従の基本追従率（澤口の speed_multiplier で増減）

# ── 支援ツリー（主人公とは別毛色＝支援重視。各系統を個別に振り分け強化）──
# 効果が Lv で伸び続けるので、ステージが進んでも腐らない（ゼロ漸近を防ぐ）。
# 4系統: HP上昇 / 解熱弾（連射） / 補給（回復アイテム射出） / マグネット（引き寄せ）
_KT_MAX_LEVEL = 3                     # 各系統の最大レベル
_HP_BY_LEVEL  = [1, 10, 30, 50]       # lv_hp 0..3 → 最大HP
# 補給: lv 0=無効, 1〜3 で回復アイテム射出間隔（秒）が短縮
_SUPPLY_INTERVAL = [0.0, 9.0, 6.5, 4.0]
# マグネット: lv 0=無効, 1〜3 で (引き寄せ半径px, 速度px/s)
_MAGNET_BY_LEVEL = [(0.0, 0.0), (150.0, 90.0), (280.0, 150.0), (9999.0, 240.0)]
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
        spawn_heal_fn: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.game      = game
        self._popup_fn = popup_fn
        self._spawn_heal_fn = spawn_heal_fn

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

        # HP / 無敵（最大HPは HP上昇系統 lv_hp で増える）
        self.hp:     int  = _HP_BY_LEVEL[0]
        self.max_hp: int  = _HP_BY_LEVEL[0]
        self._invincible_timer: float = 0.0
        self._blink_timer:      float = 0.0
        self._blink_visible:    bool  = True

        # 状態: "active" | "retired"
        self._state:        str   = "active"
        self._return_timer: float = 0.0

        # ショット
        self._shoot_cooldown: float = _SHOOT_COOLDOWN

        # 支援ツリー（4系統を個別レベルで振り分け強化）
        self.lv_hp:     int = 0   # HP上昇
        self.lv_shot:   int = 0   # 解熱弾（連射）
        self.lv_supply: int = 0   # 補給（回復アイテム射出）
        self.lv_magnet: int = 0   # マグネット（アイテム引き寄せ）
        self.stock:     int = 0   # 先輩用 強化ストック（ウェポンアイテム取得ごとに +1）
        self._supply_timer: float = 0.0

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
        enemy_bullets: pygame.sprite.Group | None = None,
        terrain: pygame.sprite.Group | None = None,
        can_fire: bool = True,
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
        new_x = self.sx + (target_x - self.sx) * k
        new_y = self.sy + (target_y - self.sy) * k

        # 画面端クランプ
        hw = self.rect.width  // 2
        hh = self.rect.height // 2
        new_x = max(float(hw), min(float(SCREEN_WIDTH  - hw), new_x))
        new_y = max(float(hh), min(float(SCREEN_HEIGHT - hh), new_y))

        # 地形（壁）を抜けないよう軸ごとにブロック（壁沿いの滑りは許可）
        self._move_with_terrain(new_x, new_y, terrain)

        # 無敵・点滅
        if self._invincible_timer > 0.0:
            self._invincible_timer -= dt
            self._blink_timer      += dt
            if self._blink_timer >= _BLINK_INTERVAL:
                self._blink_timer   = 0.0
                self._blink_visible = not self._blink_visible
        else:
            self._blink_visible = True

        # ショット（連射間隔は解熱弾Lvで短縮）
        # ボス出現演出中（alert/entering）は自機と同様に射撃を止める。
        self._shoot_cooldown = max(0.0, self._shoot_cooldown - dt)
        if can_fire and getattr(player, "fire_held", False) and self._shoot_cooldown <= 0.0:
            self._fire(player_bullets, camera)
            self._shoot_cooldown = self._shoot_interval()

        # 補給（回復アイテムを前方へ射出。Lvで頻度上昇）
        self._tick_supply(dt)

    def _move_with_terrain(
        self, new_x: float, new_y: float, terrain: pygame.sprite.Group | None
    ) -> None:
        """目標位置へ移動。地形がある場合は軸ごとに衝突をブロック（壁抜け防止）。"""
        if not terrain or len(terrain) == 0:
            self.sx, self.sy = new_x, new_y
            self.rect.center = (int(self.sx), int(self.sy))
            return
        # X 軸: 横移動だけ試し、壁にめり込むなら据え置き
        self.rect.center = (int(new_x), int(self.sy))
        if pygame.sprite.spritecollideany(self, terrain):
            new_x = self.sx
        # Y 軸: 縦移動だけ試し、壁にめり込むなら据え置き
        self.rect.center = (int(new_x), int(new_y))
        if pygame.sprite.spritecollideany(self, terrain):
            new_y = self.sy
        self.sx, self.sy = new_x, new_y
        self.rect.center = (int(self.sx), int(self.sy))

    # ── 支援ツリー（4系統）──────────────────────────────────────────
    def _shoot_interval(self) -> float:
        # 解熱弾Lvで連射が速くなる
        return max(0.16, _SHOOT_COOLDOWN - 0.10 * self.lv_shot)

    def _ways(self) -> int:
        # 最大Lvで2way（基本は連射特化）
        return 2 if self.lv_shot >= _KT_MAX_LEVEL else 1

    def _supply_interval(self) -> float:
        lv = max(0, min(self.lv_supply, _KT_MAX_LEVEL))
        return _SUPPLY_INTERVAL[lv]

    def magnet_params(self) -> tuple[float, float]:
        """アイテム引き寄せ (半径px, 速度px/s)。lv_magnet=0 なら (0,0)。"""
        lv = max(0, min(self.lv_magnet, _KT_MAX_LEVEL))
        return _MAGNET_BY_LEVEL[lv]

    def apply_upgrade(self, key: str) -> None:
        """強化UIから先輩の系統を1段上げる。"""
        if key == "kt_hp":
            self.lv_hp = min(self.lv_hp + 1, _KT_MAX_LEVEL)
            self.max_hp = _HP_BY_LEVEL[self.lv_hp]
            self.hp = self.max_hp   # HP上昇時は全回復
        elif key == "kt_shot":
            self.lv_shot = min(self.lv_shot + 1, _KT_MAX_LEVEL)
        elif key == "kt_supply":
            was_zero = self.lv_supply == 0
            self.lv_supply = min(self.lv_supply + 1, _KT_MAX_LEVEL)
            if was_zero:
                self._supply_timer = self._supply_interval()
        elif key == "kt_magnet":
            self.lv_magnet = min(self.lv_magnet + 1, _KT_MAX_LEVEL)

    def is_upgrade_available(self, key: str) -> bool:
        return {
            "kt_hp":     self.lv_hp,
            "kt_shot":   self.lv_shot,
            "kt_supply": self.lv_supply,
            "kt_magnet": self.lv_magnet,
        }.get(key, _KT_MAX_LEVEL) < _KT_MAX_LEVEL

    def upgrade_level(self, key: str) -> int:
        return {
            "kt_hp":     self.lv_hp,
            "kt_shot":   self.lv_shot,
            "kt_supply": self.lv_supply,
            "kt_magnet": self.lv_magnet,
        }.get(key, 0)

    def _tick_supply(self, dt: float) -> None:
        # 補給: 回復アイテムを前方へ射出（Lv1+。頻度はLvで上昇）
        if self.lv_supply <= 0 or self._spawn_heal_fn is None:
            return
        self._supply_timer -= dt
        if self._supply_timer <= 0.0:
            self._supply_timer = self._supply_interval()
            try:
                self._spawn_heal_fn()
            except Exception:
                pass

    def _popup(self, text: str, color: tuple[int, int, int]) -> None:
        if self._popup_fn:
            try:
                self._popup_fn(text, self.rect.centerx, self.rect.top - 6)
            except Exception:
                pass

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
            return
        ways = self._ways()  # 薬効Lvで 1→2→3 way
        if ways <= 1:
            player_bullets.add(KaronaruBullet(world_x, world_y))
        else:
            spread = 12.0
            for i in range(ways):
                off = (i - (ways - 1) / 2.0) * spread
                player_bullets.add(KaronaruBullet(world_x, world_y + off))

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
        if self._state != "active":
            return
        # スプライトは無敵中に点滅するが、HPゲージは常時表示する
        if self._blink_visible:
            surf.blit(self.image, self.rect)
        self._draw_hp_gauge(surf)

    def _draw_hp_gauge(self, surf: pygame.Surface) -> None:
        """先輩HPゲージ（スプライト上部に小バー）。"""
        if self.max_hp <= 0:
            return
        bar_w, bar_h = 34, 5
        bx = self.rect.centerx - bar_w // 2
        by = self.rect.top - 10
        ratio = max(0.0, self.hp / self.max_hp)
        pygame.draw.rect(surf, (20, 40, 25), (bx, by, bar_w, bar_h), border_radius=2)
        col = (90, 220, 120) if ratio > 0.35 else (235, 200, 70)
        pygame.draw.rect(surf, col, (bx, by, int(bar_w * ratio), bar_h), border_radius=2)
        pygame.draw.rect(surf, (180, 230, 190), (bx, by, bar_w, bar_h), 1, border_radius=2)
