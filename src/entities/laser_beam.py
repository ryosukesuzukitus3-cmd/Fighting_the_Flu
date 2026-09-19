"""
連続レーザービームの状態管理・描画・当たり判定。
Weapon.laser_level > 0 のとき、GameScene が LaserBeam インスタンスを
管理して毎フレーム update / draw / hit_check を呼ぶ。
"""
from __future__ import annotations
import math
import random
import pygame
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.core.balance import STANCE_LASER_TICK
from src.entities.terrain_query import iter_collidable_terrain

# ─── アニメーション共通 ──────────────────────────────────────────
_START_DURATION = 0.08  # ビーム展開エフェクト（秒）
_END_DURATION   = 0.12  # ビーム消滅エフェクト（秒）

# ─── レベル別設定 ─────────────────────────────────────────────────
# (core width, glow width, colors x3, enemy hit interval, boss hit interval)
# Heat is the only firing limit. Every level improves width or sustained damage.
_LEVEL_CONFIG: dict[int, tuple] = {
    1: ( 8, 18, (160,230,255), (40,180,255), (20,80,180), .08, .12),
    2: (12, 24, (175,235,255), (40,180,255), (20,80,180), .07, .10),
    3: (18, 34, (220,255,255), (60,220,255), (30,120,200), .06, .08),
    4: (22, 40, (220,255,255), (60,220,255), (30,120,200), .05, .07),
    5: (26, 46, (255,220,220), (255,80,60), (180,20,20), .045, .06),
    6: (30, 52, (255,220,220), (255,80,60), (180,20,20), .04, .05),
}

_PULSE_FREQ  = 8.0
_PULSE_AMP   = 2.0


class LaserBeam:
    """状態機械: ready → starting → firing → ending → ready"""

    def __init__(self) -> None:
        self.state:       str   = "ready"
        self.laser_level: int   = 1   # 外部から毎フレーム設定
        self._timer:      float = 0.0
        self._time:       float = 0.0
        self._hit_timers:     dict[int, float] = {}
        self._boss_hit_timer: float = 0.0
        self._beam_progress:  float = 0.0   # ビーム長 0.0〜1.0
        self._width_progress: float = 0.0   # ビーム幅 0.0〜1.0（starting/ending でアニメ）
        self._terrain_block_x: float | None = None
        self._terrain_hit_timer: float = 0.0
        self.terrain_hit: tuple[object, float, float] | None = None
        self.boss_was_hit: bool = False
        self.boss_killed: bool = False
        self.boss_form2_transition: bool = False
        self.boss_form3_transition: bool = False

    # ── パブリックAPI ──────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self.state in ("starting", "firing")

    @property
    def is_visible(self) -> bool:
        return self.state in ("starting", "firing", "ending")

    def _cfg(self) -> tuple:
        return _LEVEL_CONFIG.get(self.laser_level, _LEVEL_CONFIG[1])

    def update(self, dt: float, fire_held: bool) -> tuple[bool, bool]:
        """Hold to fire; release stops damage immediately, leaving a short fade."""
        self._time += dt
        just_fired = just_ended = False
        if not fire_held and self.is_active:
            self.state = "ending"
            self._timer = _END_DURATION
            just_ended = True
        elif fire_held and self.state in ("ready", "ending"):
            self.state = "starting"
            self._timer = _START_DURATION
            self._beam_progress = self._width_progress = 0.0
            just_fired = True
        if self.state == "starting":
            self._timer = max(0.0, self._timer - dt)
            self._beam_progress = self._width_progress = 1 - self._timer / _START_DURATION
            if self._timer <= 0:
                self.state = "firing"
        elif self.state == "ending":
            self._timer = max(0.0, self._timer - dt)
            self._width_progress = self._timer / _END_DURATION
            if self._timer <= 0:
                self.state = "ready"
                self._beam_progress = self._width_progress = 0.0
        # Preserve hit cooldowns across release/repress: tapping cannot add DPS.
        for key in list(self._hit_timers):
            self._hit_timers[key] = max(0.0, self._hit_timers[key] - dt)
            if self._hit_timers[key] == 0:
                del self._hit_timers[key]
        self._boss_hit_timer = max(0.0, self._boss_hit_timer - dt)
        self._terrain_hit_timer = max(0.0, self._terrain_hit_timer - dt)
        if not self.is_active:
            self._terrain_block_x = None
            self.terrain_hit = None
        return just_fired, just_ended

    def hit_check(
        self,
        enemies: pygame.sprite.Group,
        boss,
        muzzle_sx: float,
        muzzle_sy: float,
        terrain: pygame.sprite.Group | None = None,
    ) -> tuple:
        self._terrain_block_x = None
        self.terrain_hit = None
        self.boss_was_hit = False
        self.boss_killed = False
        self.boss_form2_transition = False
        self.boss_form3_transition = False
        if not self.is_active:
            return [], False, False

        cfg    = self._cfg()
        core_w     = cfg[0]
        hit_int    = cfg[5]
        boss_hit_int = cfg[6]

        killed    = []
        had_hit   = False
        beam_right = muzzle_sx + (SCREEN_WIDTH - muzzle_sx) * self._beam_progress
        pulse  = _PULSE_AMP * math.sin(2 * math.pi * _PULSE_FREQ * self._time)
        half_w = (core_w // 2) + abs(pulse) + 4
        if terrain is not None:
            block = self._terrain_block(terrain, muzzle_sx, muzzle_sy, half_w, beam_right)
            if block is not None:
                ter, block_x = block
                beam_right = max(muzzle_sx, block_x)
                self._terrain_block_x = beam_right
                self.terrain_hit = (ter, beam_right, muzzle_sy)

        beam_rect = pygame.Rect(
            int(muzzle_sx), int(muzzle_sy - half_w),
            int(beam_right - muzzle_sx), int(half_w * 2),
        )

        for enemy in list(enemies):
            if beam_rect.colliderect(enemy.rect):
                eid = id(enemy)
                if self._hit_timers.get(eid, 0.0) <= 0:
                    self._hit_timers[eid] = hit_int
                    had_hit = True
                    damage_fn = getattr(enemy, "take_laser_damage", enemy.take_damage)
                    if damage_fn(1):
                        killed.append(enemy)

        if boss is not None and self._boss_hit_timer <= 0:
            if beam_rect.colliderect(boss.rect):
                self._boss_hit_timer = boss_hit_int
                feedback = not getattr(boss, "suppresses_hit_feedback", lambda: False)()
                was_form2 = bool(getattr(boss, "_form2", False))
                was_form3 = bool(getattr(boss, "_form3", False))
                self.boss_was_hit = True
                # レーザーは体幹ブレイカー（HP 1/tick に対し体幹は大きく削る）
                self.boss_killed = bool(boss.take_damage(1, stance=STANCE_LASER_TICK))
                self.boss_form2_transition = (
                    not was_form2 and bool(getattr(boss, "_form2", False))
                )
                self.boss_form3_transition = (
                    not was_form3 and bool(getattr(boss, "_form3", False))
                )
                if feedback:
                    had_hit = True

        return killed, had_hit, self.boss_killed

    def _terrain_block(
        self,
        terrain: pygame.sprite.Group,
        muzzle_sx: float,
        muzzle_sy: float,
        half_w: float,
        beam_right: float,
    ):
        nearest = None
        nearest_x = beam_right
        y0 = muzzle_sy - half_w
        y1 = muzzle_sy + half_w
        for ter in iter_collidable_terrain(terrain):
            rect = ter.rect
            if rect.right < muzzle_sx or rect.left > beam_right:
                continue
            if rect.bottom < y0 or rect.top > y1:
                continue
            hit_x = rect.left if rect.left >= muzzle_sx else rect.right
            if muzzle_sx <= hit_x <= nearest_x:
                nearest = ter
                nearest_x = float(hit_x)
        if nearest is None:
            return None
        return nearest, nearest_x

    def draw(self, screen: pygame.Surface, muzzle_sx: float, muzzle_sy: float) -> None:
        cfg = self._cfg()
        core_base, glow_base, c_core, c_mid, c_glow = cfg[0], cfg[1], cfg[2], cfg[3], cfg[4]

        if not self.is_visible or self._beam_progress <= 0:
            return

        pulse = _PULSE_AMP * math.sin(2 * math.pi * _PULSE_FREQ * self._time)
        # 幅を width_progress でスケール（starting: 0→1、ending: 1→0）
        w_scale = self._width_progress
        w_core  = max(2, int((core_base + pulse) * w_scale))
        w_glow  = max(4, int((glow_base + pulse * 1.5) * w_scale))

        beam_right = muzzle_sx + (SCREEN_WIDTH - muzzle_sx) * self._beam_progress
        if self._terrain_block_x is not None:
            beam_right = min(beam_right, self._terrain_block_x)
        x0, y0 = int(muzzle_sx), int(muzzle_sy)
        x1     = int(beam_right)

        # グロウ
        glow_surf = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
        pygame.draw.line(glow_surf, (*c_glow, 70), (x0, y0), (x1, y0), w_glow)
        screen.blit(glow_surf, (0, 0))
        # 中間色
        pygame.draw.line(screen, c_mid,  (x0, y0), (x1, y0), max(2, w_core - 2))
        # コア
        pygame.draw.line(screen, c_core, (x0, y0), (x1, y0), max(1, w_core // 2))

        # 発射開始: マズルフラッシュ
        if self.state == "starting":
            flash_alpha = int(200 * (1.0 - self._beam_progress))
            flash_r = int(32 * (1.0 - self._beam_progress / 2))
            if flash_r > 0:
                flash = pygame.Surface((flash_r * 2, flash_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(flash, (*c_core, flash_alpha), (flash_r, flash_r), flash_r)
                screen.blit(flash, (x0 - flash_r, y0 - flash_r))
