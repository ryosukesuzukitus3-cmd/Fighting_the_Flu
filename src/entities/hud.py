from __future__ import annotations
from typing import TYPE_CHECKING
import pygame
from src.core.frame_clock import ticks_ms
from src.scenes.meta_ui import ACCENT_CORAL, ACCENT_MINT, BG, TEXT, TEXT_MUTED, draw_pixel_cursor

if TYPE_CHECKING:
    from src.core.game import Game
    from src.entities.player import Player
    from src.entities.laser_beam import LaserBeam

HUD_BOTTOM = 88  # Reserve the top band; the combat field below remains visible.


class HUD:
    def __init__(self, game: Game) -> None:
        self._fonts = {size: game.resources.pixelfont(size) for size in (22, 18, 16, 14, 12)}
        self._font = self._fonts[18]
        self._label_font = self._fonts[14]
        self._settings = game.settings

    def _text(self, screen, text, x, y, width, color, size=16) -> None:
        """Keep labels inside their column, including long remapped key names."""
        sizes = [candidate for candidate in self._fonts if candidate <= size]
        font = self._fonts[sizes[0]]
        for candidate in sizes:
            font = self._fonts[candidate]
            if font.size(text)[0] <= width:
                break
        if font.size(text)[0] > width:
            while text and font.size(text + "…")[0] > width:
                text = text[:-1]
            text += "…"
        screen.blit(font.render(text, False, BG), (x + 1, y + 1))
        screen.blit(font.render(text, False, color), (x, y))

    @staticmethod
    def _meter(screen, rect, ratio, color, empty=BG) -> None:
        rect = pygame.Rect(rect)
        ratio = max(0.0, min(1.0, ratio))
        pygame.draw.rect(screen, empty, rect)
        fill = rect.copy()
        fill.width = int(rect.width * ratio)
        if fill.width:
            pygame.draw.rect(screen, color, fill)

    def draw(
        self,
        screen: pygame.Surface,
        player: Player,
        score: int,
        kill_count: int,
        clear_goal: int,
        boss=None,
        laser: LaserBeam | None = None,
        lives: int = 0,
        heat=None,
        companion_stock: int | None = None,
    ) -> None:
        w = player.weapon
        gap, pad = 14, 10
        col_w = (screen.get_width() - 8 - pad * 2 - gap * 2) // 3
        x1 = 4 + pad
        x2, x3 = x1 + col_w + gap, x1 + 2 * (col_w + gap)
        white, gold, muted = TEXT, (217, 192, 119), TEXT_MUTED

        # Survival leads; score and retry allowance remain secondary.
        hp = max(0, player.hp)
        ratio = player.hp / player.max_hp if player.max_hp else 0.0
        hp_color = ACCENT_MINT if ratio > 0.3 else ACCENT_CORAL
        self._text(screen, f"HP {hp}/{player.max_hp}", x1, 7, col_w - 64, white, 22)
        self._text(screen, "危険" if ratio <= 0.3 else "", x1 + col_w - 54, 12, 54, hp_color)
        self._meter(screen, (x1, 36, col_w, 12), ratio, hp_color)
        self._text(screen, f"得点 {score:,}", x1, 59, col_w - 85, muted, 14)
        self._text(screen, "再挑戦 ∞", x1 + col_w - 80, 59, 80, muted, 14)

        # Separate the main weapon, add-ons, and upgrade prompt into fixed rows.
        self._text(screen, f"メイン {w.main_type.upper()}", x2, 10, col_w - 70, white, 16)
        if w.speed_level > 0:
            self._text(screen, f"速度×{w.speed_multiplier:.1f}", x2 + col_w - 68, 12, 68, muted, 12)
        addons = []
        if w.laser_level > 0:
            addons.append(f"レーザー{w.laser_level}")
        if w.homing_level > 0:
            addons.append(f"追尾{w.homing_level}")
        if w.magnet_level > 0:
            addons.append(f"磁力{w.magnet_level}")
        if w.has_barrier:
            addons.append("防壁")
        self._text(screen, " / ".join(addons), x2, 34, col_w, muted, 14)
        has_stock = w.weapon_stock > 0 or (companion_stock or 0) > 0
        stock_color = ACCENT_CORAL if has_stock else muted
        upgrade_key = self._settings.key_display("weapon_select")
        if has_stock:
            draw_pixel_cursor(screen, x2, 68, color=ACCENT_CORAL, scale=1)
            stock = f"強化 [{upgrade_key}] ×{w.weapon_stock}"
            if companion_stock is not None:
                stock = f"強化 [{upgrade_key}] 自機{w.weapon_stock}・先輩{companion_stock}"
        else:
            stock = "強化ストック 0"
        inset = 14 if has_stock else 0
        self._text(screen, stock, x2 + inset, 58, col_w - inset, stock_color)

        # Heat and laser readiness share the right column.
        if heat is not None:
            hot = heat.overheated
            heat_color = ACCENT_CORAL if hot or heat.ratio >= 0.85 else gold if heat.ratio >= 0.6 else ACCENT_MINT
            temp = "熱暴走・冷却中" if hot else f"体温 {heat.display_temp:.1f}℃"
            self._text(screen, temp, x3, 8, col_w, ACCENT_CORAL if hot else white, 18)
            self._meter(screen, (x3, 36, col_w, 8), heat.ratio, heat_color)
        if laser is not None:
            state = laser.state
            if heat is not None and heat.overheated and state == "ready":
                label, color = "熱で停止", ACCENT_CORAL
            elif state in ("firing", "starting"):
                label, color = "発射中", ACCENT_MINT
            elif state == "ready":
                label, color = "押して発射", ACCENT_MINT
            else:
                label, color = "冷却", muted
            laser_key = self._settings.key_display("laser")
            self._text(screen, f"[{laser_key}] {label}", x3, 48, col_w - 65, color, 12)
        # ボスHPバー
        if boss is not None:
            bar_w, bar_h = 400, 18
            bx = (screen.get_width() - bar_w) // 2
            by = screen.get_height() - 36
            ratio = max(0.0, min(1.0, boss.hp / boss.max_hp)) if boss.max_hp else 0.0
            self._meter(screen, (bx, by, bar_w, bar_h), ratio, ACCENT_CORAL)
            self._text(screen, "ボスHP", bx - 84, by - 4, 76, TEXT, 18)

            # 体幹ゲージ（バトルv2）: HPバー直上。ダウン中は点滅表示に切替
            if getattr(boss, "is_stance_down", False):
                blink = (ticks_ms() // 150) % 2 == 0
                if blink:
                    self._text(screen, "反撃の隙・ダメージ増", bx + 118, by - 19, 282, ACCENT_MINT, 14)
            else:
                sr = boss.stance_ratio() if hasattr(boss, "stance_ratio") else None
                if sr is not None:
                    self._text(screen, "体幹", bx - 40, by - 23, 38, TEXT_MUTED, 12)
                    self._meter(screen, (bx, by - 9, bar_w, 6), sr, gold)
