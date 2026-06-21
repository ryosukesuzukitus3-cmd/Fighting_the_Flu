"""ボスのギミック表現を集約するミックスイン。

ボスのコンセプトFX（フォーム別シルエット／オーラ）・アーマーゲージ・
ドローンシールド等のギミック描画と、ギミックが使うタレット召喚を担当する。

固有の状態を持たない純粋な描画（＋タレット生成）なので、`GameScene` へ
mixin として合流させる（他の pause/upgrade/overlay/post_boss/debug と同様）。
描画は `self._boss` などシーン側の属性を直接参照する。
"""
from __future__ import annotations
import math
import pygame

from src.core.constants import SCREEN_HEIGHT


class GameSceneBossFxMixin:
    def _draw_boss_gimmick(self, buf: pygame.Surface) -> None:
        """Draw the current boss gimmick state."""
        b = self._boss
        if b is None:
            return
        cx, cy = b.rect.center
        r = max(b.rect.width, b.rect.height) // 2 + 10
        gimmick = b._current_gimmick() if hasattr(b, "_current_gimmick") else None
        if getattr(b, "_state", "fight") != "fight":
            return
        self._draw_boss_concept_fx(buf, b, cx, cy, r)
        if gimmick is None:
            return

        label = ""        # 頭上ラベル
        lcol  = (255, 220, 60)

        if gimmick == "shield":
            if getattr(b, "_shield_active", False):
                ring = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
                pygame.draw.circle(ring, (80, 200, 255, 90), (r + 3, r + 3), r)
                pygame.draw.circle(ring, (160, 230, 255, 220), (r + 3, r + 3), r, 3)
                buf.blit(ring, (cx - r - 3, cy - r - 3))
                label, lcol = "SHIELD", (160, 230, 255)
            else:
                label, lcol = "BREAK CHANCE!", (120, 255, 140)

        elif gimmick == "weakpoint":
            if getattr(b, "_weak_timer", 0.0) > 0:
                glow = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 60, 60, 120), (r + 3, r + 3), r, 5)
                buf.blit(glow, (cx - r - 3, cy - r - 3))
                pygame.draw.circle(buf, (255, 55, 80), (cx, cy), 18)
                pygame.draw.circle(buf, (255, 240, 220), (cx, cy), 8)
                label, lcol = "CORE EXPOSED!", (255, 90, 90)
            else:
                label, lcol = "ARMOR", (180, 190, 210)
                self._draw_armor_gauge(buf, b, cx, b.rect.top - 30)

        elif gimmick == "turrets":
            if getattr(b, "_stun_timer", 0.0) > 0:
                label, lcol = "STUN  DAMAGE UP", (255, 220, 60)
            else:
                n = b._summoned_alive() if hasattr(b, "_summoned_alive") else 0
                if n > 0:
                    label, lcol = f"DRONE SHIELD x{n}", (160, 230, 255)

        if label:
            surf = self.game.resources.pixelfont(20).render(label, True, lcol)
            buf.blit(surf, (cx - surf.get_width() // 2, b.rect.top - 26))

    def _draw_armor_gauge(self, buf: pygame.Surface, b, cx: int, y: int) -> None:
        """Draw a compact armor gauge for weakpoint gimmicks."""
        from src.entities.enemies.boss import _ARMOR_MAX
        w, h = 80, 6
        ratio = max(0.0, min(1.0, getattr(b, "_armor", 0) / _ARMOR_MAX))
        x = cx - w // 2
        pygame.draw.rect(buf, (40, 44, 54), (x, y, w, h), border_radius=2)
        pygame.draw.rect(buf, (150, 170, 200), (x, y, int(w * ratio), h), border_radius=2)
        pygame.draw.rect(buf, (90, 100, 120), (x, y, w, h), 1, border_radius=2)

    def _draw_boss_concept_fx(self, buf: pygame.Surface, b, cx: int, cy: int, r: int) -> None:
        """Draw form-specific readable boss silhouettes and danger cues."""
        stage_id = getattr(b, "_stage_id", 0)
        form2 = bool(getattr(b, "_form2", False))
        form3 = bool(getattr(b, "_form3", False))

        if form3:
            pulse = 0.5 + 0.5 * math.sin(getattr(b, "_time", 0.0) * 3.0)
            aura = pygame.Surface((r * 2 + 36, r * 2 + 36), pygame.SRCALPHA)
            pygame.draw.circle(aura, (120, 10, 70, int(50 + 55 * pulse)),
                               (r + 18, r + 18), r + 12)
            pygame.draw.circle(aura, (220, 30, 80, int(90 + 45 * pulse)),
                               (r + 18, r + 18), r + 12, 3)
            buf.blit(aura, (cx - r - 18, cy - r - 18), special_flags=pygame.BLEND_RGBA_ADD)
            return

        if stage_id == 2 and not form2:
            if getattr(b, "_weak_timer", 0.0) <= 0:
                plate = pygame.Surface((b.rect.width + 34, b.rect.height + 34), pygame.SRCALPHA)
                w, h = plate.get_size()
                col = (150, 165, 185, 135)
                pygame.draw.rect(plate, col, (4, 14, w - 8, 14), border_radius=3)
                pygame.draw.rect(plate, col, (4, h - 28, w - 8, 14), border_radius=3)
                pygame.draw.rect(plate, col, (6, 30, 16, h - 60), border_radius=3)
                pygame.draw.rect(plate, col, (w - 22, 30, 16, h - 60), border_radius=3)
                pygame.draw.rect(plate, (230, 240, 255, 110), (0, 10, w, h - 20), 2, border_radius=8)
                buf.blit(plate, (b.rect.left - 17, b.rect.top - 17))

        if stage_id == 3 and not form2:
            alive = b._summoned_alive() if hasattr(b, "_summoned_alive") else 0
            if alive > 0:
                shield = pygame.Surface((r * 2 + 16, r * 2 + 16), pygame.SRCALPHA)
                pygame.draw.circle(shield, (50, 210, 240, 62), (r + 8, r + 8), r + 4)
                pygame.draw.circle(shield, (130, 245, 255, 170), (r + 8, r + 8), r + 4, 3)
                buf.blit(shield, (cx - r - 8, cy - r - 8))
                for turret in list(getattr(b, "_summoned", [])):
                    if not turret.alive():
                        continue
                    tx, ty = turret.rect.center
                    pygame.draw.aaline(buf, (110, 235, 255), (cx, cy), (tx, ty))
                    pygame.draw.circle(buf, (170, 255, 255), (tx, ty), 8, 2)
            elif getattr(b, "_stun_timer", 0.0) > 0:
                pygame.draw.circle(buf, (255, 225, 80), (cx, cy), r + 8, 4)

        if stage_id == 4 and not form2:
            grid = pygame.Surface((178, 250), pygame.SRCALPHA)
            for x in range(0, 179, 44):
                pygame.draw.line(grid, (210, 170, 70, 55), (x, 0), (x, 249))
            for y in range(0, 251, 50):
                pygame.draw.line(grid, (210, 170, 70, 55), (0, y), (177, y))
            buf.blit(grid, (cx - grid.get_width() // 2, cy - grid.get_height() // 2))

        if form2:
            slash = pygame.Surface((r * 2 + 28, r * 2 + 28), pygame.SRCALPHA)
            pygame.draw.line(slash, (255, 45, 120, 150), (slash.get_width() - 8, 14), (18, slash.get_height() - 12), 5)
            pygame.draw.line(slash, (255, 190, 225, 110), (slash.get_width() - 40, 8), (46, slash.get_height() - 22), 2)
            buf.blit(slash, (cx - r - 14, cy - r - 14), special_flags=pygame.BLEND_RGBA_ADD)

    def _summon_boss_turrets(self, n: int) -> list:
        """Summon turrets used by boss gimmicks."""
        if self._boss_stage_id() == 3 and self._boss is not None:
            from src.entities.enemies.boss_drone import MatchingZeroDrone
            spawned = []
            for i in range(n):
                d = MatchingZeroDrone(self.game, self._boss, i, self.enemy_bullets, self.player)
                self.enemies.add(d)
                spawned.append(d)
            return spawned

        from src.entities.enemies.turret import EnemyTurret
        spawned = []
        for i in range(n):
            wx = self.camera.spawn_x(margin=-120)
            wy = 110.0 + i * (SCREEN_HEIGHT - 220.0) / max(1, n - 1) if n > 1 else SCREEN_HEIGHT / 2
            t = EnemyTurret(self.game, wx, wy, self.enemy_bullets, self.player)
            self.enemies.add(t)
            spawned.append(t)
        return spawned
