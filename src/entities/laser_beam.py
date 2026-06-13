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

# ─── アニメーション共通 ──────────────────────────────────────────
_START_DURATION = 0.15  # ビーム展開エフェクト（秒）
_END_DURATION   = 0.15  # ビーム消滅エフェクト（秒）

# ─── レベル別設定 ─────────────────────────────────────────────────
# キー: (core_w, glow_w, c_core, c_mid, c_glow, charge, fire_dur, hit_int, boss_hit_int)
# charge: チャージ時間 / fire_dur: 発射継続時間
# hit_int: 雑魚ダメージ間隔 / boss_hit_int: ボスダメージ間隔
_LEVEL_CONFIG: dict[int, tuple] = {
    1: ( 6, 18, (160,230,255), (40, 180,255), (20, 80,180),  0.40, 1.50, 0.06, 0.06),
    2: ( 6, 18, (160,230,255), (40, 180,255), (20, 80,180),  0.36, 1.60, 0.06, 0.06),
    3: (22, 52, (220,255,255), (60, 220,255), (30,120,200),  0.32, 1.70, 0.04, 0.04),
    4: (22, 52, (220,255,255), (60, 220,255), (30,120,200),  0.28, 1.80, 0.04, 0.04),
    5: (22, 52, (255,220,220), (255, 80, 60), (180, 20, 20), 0.24, 1.90, 0.027, 0.027),
    6: (22, 52, (255,220,220), (255, 80, 60), (180, 20, 20), 0.20, 2.00, 0.027, 0.027),
}

_PULSE_FREQ  = 8.0
_PULSE_AMP   = 2.0


class LaserBeam:
    """状態機械: ready → charging → starting → firing → ending → ready"""

    def __init__(self) -> None:
        self.state:       str   = "ready"
        self.laser_level: int   = 1   # 外部から毎フレーム設定
        self._timer:      float = 0.0
        self._time:       float = 0.0
        self._hit_timers:     dict[int, float] = {}
        self._boss_hit_timer: float = 0.0
        self._beam_progress:  float = 0.0   # ビーム長 0.0〜1.0
        self._width_progress: float = 0.0   # ビーム幅 0.0〜1.0（starting/ending でアニメ）
        self._gauge:          float = 0.0   # チャージゲージ 0.0(空)〜1.0(満タン)
        self._prev_fire_held: bool  = False  # 前フレームの fire_held（エッジ検出用）
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

    @property
    def is_charging(self) -> bool:
        return self.state == "charging"

    def _cfg(self) -> tuple:
        return _LEVEL_CONFIG.get(self.laser_level, _LEVEL_CONFIG[1])

    @property
    def charge_ratio(self) -> float:
        """チャージ進捗 0.0→1.0（_gauge の値を返す）"""
        return self._gauge

    @property
    def cooldown_ratio(self) -> float:
        """後方互換用: クール廃止につき常に 1.0"""
        return 1.0

    @property
    def gauge_ratio(self) -> float:
        """HUD 用ゲージ比率 0.0-1.0
        ready:                    1.0
        charging/starting/firing: ゲージ残量
        ending:                   0.0
        """
        if self.state == "ready":
            return 1.0
        if self.state in ("charging", "starting", "firing"):
            return self._gauge
        return 0.0  # ending

    def update(self, dt: float, fire_held: bool) -> tuple[bool, bool]:
        """
        Returns: (just_fired, just_ended) — SE / shake タイミング用
        just_fired: チャージ完了してビーム発射した瞬間
        """
        self._time  += dt
        just_fired  = False
        just_ended  = False

        cfg        = self._cfg()
        charge_dur = cfg[5]
        fire_dur   = cfg[6]

        # エッジ検出
        just_released = not fire_held and self._prev_fire_held
        just_pressed  = fire_held and not self._prev_fire_held

        if self.state == "ready":
            if fire_held:
                self.state  = "charging"
                self._gauge = 0.0

        elif self.state == "charging":
            if fire_held:
                self._gauge = min(1.0, self._gauge + dt / charge_dur)
            elif just_released:          # Vを離した → 発射
                self.state           = "starting"
                self._timer          = _START_DURATION
                self._beam_progress  = 0.0
                self._width_progress = 0.0
                just_fired           = True

        elif self.state == "starting":
            self._timer -= dt
            t = max(0.0, self._timer / _START_DURATION)
            self._beam_progress  = 1.0 - t
            self._width_progress = 1.0 - t   # だんだん太く
            if self._timer <= 0:
                self.state           = "firing"
                self._beam_progress  = 1.0
                self._width_progress = 1.0

        elif self.state == "firing":
            self._gauge = max(0.0, self._gauge - dt / fire_dur)
            if self._gauge <= 0 or just_pressed:   # ゲージ切れ or Vを再押下
                self.state  = "ending"
                self._timer = _END_DURATION
                just_ended  = True

        elif self.state == "ending":
            self._timer -= dt
            t = max(0.0, self._timer / _END_DURATION)
            self._width_progress = t   # だんだん細く（長さは変えない）
            if self._timer <= 0:
                self.state           = "ready"
                self._beam_progress  = 0.0
                self._width_progress = 0.0
                self._gauge          = 0.0
                self._hit_timers.clear()

        for k in list(self._hit_timers):
            self._hit_timers[k] -= dt
            if self._hit_timers[k] < 0:
                self._hit_timers[k] = 0.0
        self._boss_hit_timer = max(0.0, self._boss_hit_timer - dt)
        self._terrain_hit_timer = max(0.0, self._terrain_hit_timer - dt)
        if not self.is_active:
            self._terrain_block_x = None
            self.terrain_hit = None

        self._prev_fire_held = fire_held
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
        hit_int    = cfg[7]
        boss_hit_int = cfg[8]

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
                self.boss_killed = bool(boss.take_damage(1))
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
        for ter in terrain:
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

        # チャージ中エフェクト（ビームなし）
        if self.is_charging:
            r = self.charge_ratio
            self._draw_charge_effect(screen, muzzle_sx, muzzle_sy, r, c_core)
            return

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

    def _draw_charge_effect(
        self, screen: pygame.Surface,
        mx: float, my: float,
        ratio: float,
        c_core: tuple,
    ) -> None:
        """チャージエフェクト: 収束（充電中）→ 回転リング+脈動グロウ（完了）"""
        if ratio >= 1.0:
            # ── 完了: 金白色の高速回転リング + 脈動グロウ ──
            c_full = (255, 240, 160)
            pulse  = math.sin(self._time * 12.0)

            # 内リング (12粒, 高速回転)
            n_inner, ring_r = 12, 22
            for i in range(n_inner):
                angle = self._time * 10.0 + i * (6.2832 / n_inner)
                px = mx + math.cos(angle) * ring_r
                py = my + math.sin(angle) * ring_r
                r  = 3
                s  = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*c_full, 220), (r + 1, r + 1), r)
                screen.blit(s, (int(px) - r, int(py) - r))

            # 外リング (6粒, 逆回転)
            n_outer, outer_r = 6, 36
            for i in range(n_outer):
                angle = -self._time * 6.0 + i * (6.2832 / n_outer)
                px = mx + math.cos(angle) * outer_r
                py = my + math.sin(angle) * outer_r
                r  = 2
                s  = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*c_full, 160), (r + 1, r + 1), r)
                screen.blit(s, (int(px) - r, int(py) - r))

            # 脈動する中心グロウ
            glow_r = int(16 + 6 * pulse)
            gs = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(
                gs, (*c_full, int(160 + 40 * abs(pulse))),
                (glow_r + 1, glow_r + 1), glow_r,
            )
            screen.blit(gs, (int(mx) - glow_r, int(my) - glow_r))

            # 輪郭リング（hollow circle, 脈動）
            ring_surf = pygame.Surface((outer_r * 2 + 4, outer_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(
                ring_surf, (*c_full, int(80 + 40 * abs(pulse))),
                (outer_r + 2, outer_r + 2), outer_r, 1,
            )
            screen.blit(ring_surf, (int(mx) - outer_r - 2, int(my) - outer_r - 2))

        else:
            # ── 充電中: 粒子がマズルに収束 ──
            n = int(12 * ratio) + 3
            for i in range(n):
                angle = self._time * 4.0 + i * (6.2832 / n)
                dist  = max(4, int(40 * (1.0 - ratio)))
                px    = mx + math.cos(angle) * dist
                py    = my + math.sin(angle) * dist
                r     = max(1, int(4 * ratio))
                alpha = int(180 * ratio)
                s     = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*c_core, alpha), (r + 1, r + 1), r)
                screen.blit(s, (int(px) - r, int(py) - r))

            # 中心グロウ
            glow_r = max(2, int(20 * ratio))
            gs = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*c_core, int(100 * ratio)), (glow_r + 1, glow_r + 1), glow_r)
            screen.blit(gs, (int(mx) - glow_r, int(my) - glow_r))
