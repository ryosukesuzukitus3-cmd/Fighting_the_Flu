"""ウェポン選択UI ミックスイン — GameScene に多重継承で組み込まれる。"""
from __future__ import annotations
import pygame

from src.scenes.game.config import UPGRADE_SLOTS, MAIN_NEXT_NAMES


class GameSceneUpgradeMixin:
    """ボス撃破後のグラディウス式ウェポン選択UIの入力・描画を担当する。"""

    def _is_upgrade_available(self, key: str) -> bool:
        w = self.player.weapon  # type: ignore[attr-defined]
        if key == "weapon_main": return not w.main_at_max
        if key == "speed":       return not w.speed_at_max
        if key == "laser":       return w.main_level >= 2 and w.laser_level < 6
        if key == "homing":      return w.main_level >= 2 and w.homing_level < 7
        if key == "magnet":      return w.magnet_level < 3
        if key == "barrier":     return not w.has_barrier
        return True

    def _slot_display_label(self, key: str) -> str:
        w = self.player.weapon  # type: ignore[attr-defined]
        if key == "weapon_main":
            idx = w.main_level
            return MAIN_NEXT_NAMES[idx] if idx < len(MAIN_NEXT_NAMES) else "(MAX)"
        if key == "speed":
            lv = w.speed_level
            return f"SPD {lv+1}" if not w.speed_at_max else "SPD MAX"
        if key == "laser":
            lv = w.laser_level
            if lv < 6: return f"LASER {lv + 1}"
            return "LSR MAX"
        if key == "homing":
            lv = w.homing_level
            if lv < 7: return f"HOMING {lv + 1}"
            return "HOM MAX"
        if key == "magnet":
            lv = w.magnet_level
            if lv == 0: return "MGT 1"
            if lv == 1: return "MGT 2"
            if lv == 2: return "MGT 3"
            return "MGT MAX"
        return {"barrier": "BARRIER"}[key]

    def _update_upgrade_ui(self) -> None:
        # UIナビゲーションキー（←→ / ENTER / X）はカスタマイズ対象外として固定
        inp = self.game.input  # type: ignore[attr-defined]
        n   = len(UPGRADE_SLOTS)
        if inp.is_just_pressed(pygame.K_LEFT):
            for _ in range(n):
                self._upgrade_cursor = (self._upgrade_cursor - 1) % n  # type: ignore[attr-defined]
                if self._is_upgrade_available(UPGRADE_SLOTS[self._upgrade_cursor][0]):  # type: ignore[attr-defined]
                    break
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)  # type: ignore[attr-defined]
        if inp.is_just_pressed(pygame.K_RIGHT):
            for _ in range(n):
                self._upgrade_cursor = (self._upgrade_cursor + 1) % n  # type: ignore[attr-defined]
                if self._is_upgrade_available(UPGRADE_SLOTS[self._upgrade_cursor][0]):  # type: ignore[attr-defined]
                    break
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)  # type: ignore[attr-defined]
        if inp.is_just_pressed(pygame.K_x):
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)  # type: ignore[attr-defined]
            self._upgrading = False  # type: ignore[attr-defined]
            return
        if inp.is_just_pressed(pygame.K_RETURN):
            key = UPGRADE_SLOTS[self._upgrade_cursor][0]  # type: ignore[attr-defined]
            if self._is_upgrade_available(key):
                self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)  # type: ignore[attr-defined]
                self.player.weapon.upgrade(key)  # type: ignore[attr-defined]
                # 在庫を1消費して閉じる（1回押下＝1選択）
                self.player.weapon.weapon_stock = max(0, self.player.weapon.weapon_stock - 1)  # type: ignore[attr-defined]
                self._upgrading = False  # type: ignore[attr-defined]

    def _draw_upgrade_ui(self, screen: pygame.Surface) -> None:
        if self._upgrade_font is None:  # type: ignore[attr-defined]
            self._upgrade_font       = self.game.resources.pixelfont(22)  # type: ignore[attr-defined]
            self._upgrade_title_font = self.game.resources.pixelfont(42)  # type: ignore[attr-defined]

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        screen.blit(overlay, (0, 0))

        cx = screen.get_width()  // 2
        cy = screen.get_height() // 2

        title = self._upgrade_title_font.render("POWER UP!", True, (255, 220, 80))  # type: ignore[attr-defined]
        screen.blit(title, (cx - title.get_width() // 2, cy - 130))

        box_w, box_h = 110, 66
        gap = 10
        total_w = len(UPGRADE_SLOTS) * box_w + (len(UPGRADE_SLOTS) - 1) * gap
        sx0 = cx - total_w // 2

        for i, (key, _) in enumerate(UPGRADE_SLOTS):
            available = self._is_upgrade_available(key)
            selected  = i == self._upgrade_cursor  # type: ignore[attr-defined]
            bx = sx0 + i * (box_w + gap)
            by = cy - 30

            if selected and available:
                bg, bd, tx = (255, 220, 80), (255, 200, 0), (20, 20, 20)
            elif available:
                bg, bd, tx = (35, 40, 60), (80, 100, 140), (200, 200, 220)
            else:
                bg, bd, tx = (25, 25, 35), (50, 50, 60), (70, 70, 80)

            pygame.draw.rect(screen, bg, (bx, by, box_w, box_h), border_radius=7)
            pygame.draw.rect(screen, bd, (bx, by, box_w, box_h), 2, border_radius=7)

            label = self._slot_display_label(key)
            surf  = self._upgrade_font.render(label, True, tx)  # type: ignore[attr-defined]
            screen.blit(surf, (bx + box_w // 2 - surf.get_width()  // 2,
                               by + box_h // 2 - surf.get_height() // 2))

        arrow_x = sx0 + self._upgrade_cursor * (box_w + gap) + box_w // 2  # type: ignore[attr-defined]
        arrow_y = cy + 52
        pygame.draw.polygon(screen, (255, 220, 80), [
            (arrow_x,      arrow_y),
            (arrow_x - 9,  arrow_y - 14),
            (arrow_x + 9,  arrow_y - 14),
        ])

        stock = self.player.weapon.weapon_stock  # type: ignore[attr-defined]
        hint = self.game.resources.pixelfont(16).render(  # type: ignore[attr-defined]
            f"←→: 選択   ENTER: 決定（在庫1消費）   X: 閉じる   （在庫 {stock}）", True, (100, 100, 120)
        )
        screen.blit(hint, (cx - hint.get_width() // 2, cy + 62))
