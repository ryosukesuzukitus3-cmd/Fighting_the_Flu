"""デバッグモード ミックスイン — python -O で完全除去される。

操作:
  F1        無敵トグル
  F2        ウェポンアイテムをドロップ
  F3        現在状態をコンソール出力
  F4        押している間ステージ進行を早送り
  F5        次ウェーブを即スキップ
  F6        ボスを即スポーン（ALERT なし）
  F7        ウェポン状態を最大化
  Ctrl+1~9  登録済みステージへワープ
"""
from __future__ import annotations
import pygame
from src.core.constants import SCREEN_WIDTH


DEBUG_FAST_FORWARD_SCALE = 6.0
_DEBUG_MAX_UPGRADE_STEPS = 20


class GameSceneDebugMixin:
    """デバッグ操作と画面右上オーバーレイを担当する。"""

    def _debug_apply_time_scale(self, dt: float) -> float:
        inp = self.game.input  # type: ignore[attr-defined]
        scale = DEBUG_FAST_FORWARD_SCALE if inp.is_pressed(pygame.K_F4) else 1.0
        self._debug_time_scale = scale  # type: ignore[attr-defined]
        return dt * scale

    def _debug_max_weapon(self) -> None:
        w = self.player.weapon  # type: ignore[attr-defined]
        for item_type in ("weapon_main", "speed", "laser", "homing", "magnet", "barrier"):
            for _ in range(_DEBUG_MAX_UPGRADE_STEPS):
                w.upgrade(item_type)
        print(
            "[DEBUG] Weapon maxed: "
            f"main={w.main_level} laser={w.laser_level} homing={w.homing_level} "
            f"speed={w.speed_level} barrier={w.has_barrier} magnet={w.magnet_level}"
        )

    def _debug_handle_input(self) -> bool:
        inp  = self.game.input          # type: ignore[attr-defined]
        # F1: 無敵トグル
        if inp.is_just_pressed(pygame.K_F1):
            self._debug_invincible = not self._debug_invincible  # type: ignore[attr-defined]
            self.player._invincible_timer = (  # type: ignore[attr-defined]
                99999.0 if self._debug_invincible else 0.0  # type: ignore[attr-defined]
            )

        # 無敵継続
        if getattr(self, "_debug_invincible", False):
            self.player._invincible_timer = max(  # type: ignore[attr-defined]
                self.player._invincible_timer, 99999.0  # type: ignore[attr-defined]
            )

        # F2: ウェポンアイテムドロップ
        if inp.is_just_pressed(pygame.K_F2):
            from src.entities.items.weapon_item import WeaponItem
            import random
            wx, wy = self.player.muzzle_world(self.camera)  # type: ignore[attr-defined]
            self.items.add(WeaponItem(  # type: ignore[attr-defined]
                wx + random.uniform(-20, 20),
                wy + random.uniform(-20, 20),
            ))

        # F3: 状態をコンソール出力
        if inp.is_just_pressed(pygame.K_F3):
            w = self.player.weapon  # type: ignore[attr-defined]
            print(
                f"[DEBUG] Stage={self._stage_id}  "           # type: ignore[attr-defined]
                f"t={self._stage_elapsed:.1f}s  "             # type: ignore[attr-defined]
                f"HP={self.player.hp}/{self.player.max_hp}  " # type: ignore[attr-defined]
                f"Enemies={len(self.enemies)}  "              # type: ignore[attr-defined]
                f"Items={len(self.items)}  "                  # type: ignore[attr-defined]
                f"Score={self.game.shared.score}  "           # type: ignore[attr-defined]
                f"Kills={self.game.shared.kill_count}"        # type: ignore[attr-defined]
            )
            print(
                f"         Weapon: main={w.main_level} laser={w.laser_level} "
                f"homing={w.homing_level} speed={w.speed_level} "
                f"barrier={w.has_barrier} magnet={w.magnet_level}"
            )
            print(
                f"         Combo={getattr(self, '_combo_count', 0)}  "
                f"IntroState={self._boss_intro_state}"  # type: ignore[attr-defined]
            )

        # F5: 次ウェーブをスキップ（ボス演出中は無効）
        if inp.is_just_pressed(pygame.K_F5) and self._boss_intro_state == "":  # type: ignore[attr-defined]
            idx    = self.spawner._index   # type: ignore[attr-defined]
            events = self.spawner._events  # type: ignore[attr-defined]
            if idx < len(events):
                self.spawner._elapsed = events[idx]["time"] + 0.01  # type: ignore[attr-defined]
                print(f"[DEBUG] Skipped to wave {idx + 1} (t={events[idx]['time']}s)")

        # F6: ボス即スポーン（まだボスがいない場合のみ）
        if inp.is_just_pressed(pygame.K_F6):
            if self._boss is None and self._boss_intro_state == "":  # type: ignore[attr-defined]
                self._queue_boss_spawn()  # type: ignore[attr-defined]
                print("[DEBUG] Force boss spawn")

        # F7: max out the weapon state
        if inp.is_just_pressed(pygame.K_F7):
            self._debug_max_weapon()

        # Ctrl+N: stage warp. This mirrors the global handler for headless tools
        # that drive GameScene directly instead of Game.run().
        from src.core.debug import handle_global_debug_input

        return handle_global_debug_input(self.game)  # type: ignore[arg-type]

    def _debug_draw_overlay(self, screen: pygame.Surface) -> None:
        font = self.game.resources.pixelfont(15)  # type: ignore[attr-defined]
        w    = self.player.weapon                  # type: ignore[attr-defined]

        combo_count = getattr(self, "_combo_count", 0)
        combo_timer = getattr(self, "_combo_timer", 0.0)
        scale = getattr(self, "_debug_time_scale", 1.0)
        ff_label = f"  FFx{scale:.0f}" if scale > 1.0 else ""

        lines = [
            "[ DEBUG ]",
            f"Stage {self._stage_id}  t={self._stage_elapsed:.1f}s",  # type: ignore[attr-defined]
            f"HP {self.player.hp}/{self.player.max_hp}"               # type: ignore[attr-defined]
            + ("  INV:ON" if getattr(self, "_debug_invincible", False) else "") + ff_label,
            f"main={w.main_level} L{w.laser_level} H{w.homing_level} S{w.speed_level}",
            f"barrier={'Y' if w.has_barrier else 'N'}  mgt={w.magnet_level}",
            f"Enemies:{len(self.enemies)}  Items:{len(self.items)}",  # type: ignore[attr-defined]
            f"Score:{self.game.shared.score}  Kills:{self.game.shared.kill_count}",  # type: ignore[attr-defined]
            f"Combo:{combo_count}  ({combo_timer:.1f}s)",
            "F1:INV F2:Drop F3:Log F4:FF",
            "F5:Wave F6:Boss F7:MaxW Ctrl+N:Warp",
        ]

        line_h  = 17
        max_w   = max(font.size(ln)[0] for ln in lines)
        box_h   = len(lines) * line_h + 8
        overlay = pygame.Surface((max_w + 14, box_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        x0 = SCREEN_WIDTH - max_w - 20
        screen.blit(overlay, (x0 - 4, 4))

        for i, line in enumerate(lines):
            if i == 0:
                color = (255, 80, 80)
            elif i >= len(lines) - 2:
                color = (110, 110, 130)
            else:
                color = (210, 210, 210)
            surf = font.render(line, True, color)
            screen.blit(surf, (x0, 8 + i * line_h))
