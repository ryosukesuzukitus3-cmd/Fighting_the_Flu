"""デバッグモード ミックスイン — python -O で完全除去される。

操作:
  F1        無敵トグル
  F2        ウェポンアイテムをドロップ
  F3        現在状態をコンソール出力
  F5        次ウェーブを即スキップ
  F6        ボスを即スポーン（ALERT なし）
  Ctrl+1~4  指定ステージへワープ
"""
from __future__ import annotations
import pygame
from src.core.constants import SCREEN_WIDTH


class GameSceneDebugMixin:
    """デバッグ操作と画面右上オーバーレイを担当する。"""

    def _debug_handle_input(self) -> None:
        inp  = self.game.input          # type: ignore[attr-defined]
        keys = pygame.key.get_pressed()
        ctrl = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]

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

        # Ctrl+N: ステージワープ（stage_ids() でステージ数に追従）
        if ctrl:
            from src.core.registries import stage_ids
            _STAGE_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                           pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9]
            for stage, key in zip(stage_ids(), _STAGE_KEYS):
                if inp.is_just_pressed(key):
                    print(f"[DEBUG] Warp to Stage {stage}")
                    from src.scenes.game_scene import GameScene
                    self.game.change_scene(GameScene(self.game, stage_id=stage))  # type: ignore[attr-defined]
                    return

    def _debug_draw_overlay(self, screen: pygame.Surface) -> None:
        font = self.game.resources.pixelfont(15)  # type: ignore[attr-defined]
        w    = self.player.weapon                  # type: ignore[attr-defined]

        combo_count = getattr(self, "_combo_count", 0)
        combo_timer = getattr(self, "_combo_timer", 0.0)

        lines = [
            "[ DEBUG ]",
            f"Stage {self._stage_id}  t={self._stage_elapsed:.1f}s",  # type: ignore[attr-defined]
            f"HP {self.player.hp}/{self.player.max_hp}"               # type: ignore[attr-defined]
            + ("  INV:ON" if getattr(self, "_debug_invincible", False) else ""),
            f"main={w.main_level} L{w.laser_level} H{w.homing_level} S{w.speed_level}",
            f"barrier={'Y' if w.has_barrier else 'N'}  mgt={w.magnet_level}",
            f"Enemies:{len(self.enemies)}  Items:{len(self.items)}",  # type: ignore[attr-defined]
            f"Score:{self.game.shared.score}  Kills:{self.game.shared.kill_count}",  # type: ignore[attr-defined]
            f"Combo:{combo_count}  ({combo_timer:.1f}s)",
            "F1:無敵 F2:Wドロップ F3:出力",
            "F5:次波 F6:ボス Ctrl+N:ワープ",
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
