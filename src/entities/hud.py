from __future__ import annotations
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from src.core.game import Game
    from src.entities.player import Player
    from src.entities.laser_beam import LaserBeam

HUD_BOTTOM = 88  # Reserve the top band; the combat field below remains visible.


class HUD:
    def __init__(self, game: Game) -> None:
        self._fonts = {size: game.resources.pixelfont(size) for size in (18, 16, 14, 12)}
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
        screen.blit(font.render(text, True, color), (x, y))

    @staticmethod
    def _meter(screen, rect, ratio, color, empty=(30, 30, 42)) -> None:
        rect = pygame.Rect(rect)
        ratio = max(0.0, min(1.0, ratio))
        pygame.draw.rect(screen, empty, rect, border_radius=3)
        fill = rect.copy()
        fill.width = int(rect.width * ratio)
        if fill.width:
            pygame.draw.rect(screen, color, fill, border_radius=3)
        pygame.draw.rect(screen, (135, 145, 158), rect, 1, border_radius=3)

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
        pieces: list[str] | None = None,
    ) -> None:
        w = player.weapon
        panel = pygame.Surface((screen.get_width() - 8, HUD_BOTTOM - 4), pygame.SRCALPHA)
        panel.fill((4, 7, 15, 188))
        pygame.draw.rect(panel, (224, 224, 238, 74), panel.get_rect(), 1, border_radius=6)
        screen.blit(panel, (4, 4))
        gap, pad = 14, 10
        col_w = (panel.get_width() - pad * 2 - gap * 2) // 3
        x1 = 4 + pad
        x2, x3 = x1 + col_w + gap, x1 + 2 * (col_w + gap)
        for x in (x2 - gap // 2, x3 - gap // 2):
            pygame.draw.line(screen, (55, 63, 78), (x, 14), (x, 76))
        white, gold, muted = (240, 243, 250), (255, 220, 100), (170, 184, 200)

        # Survival and progress. Zero remaining leave is useful information too.
        self._text(screen, f"SCORE {score:,}", x1, 8, col_w, white, 18)
        hp = max(0, player.hp)
        self._text(screen, f"HP {hp}/{player.max_hp}", x1, 33, 112, white)
        ratio = player.hp / player.max_hp if player.max_hp else 0.0
        hp_color = (90, 220, 135) if ratio > 0.3 else (255, 115, 75)
        self._meter(screen, (x1 + 116, 38, col_w - 116, 11), ratio, hp_color)
        self._text(screen, f"有給 {max(0, lives)}日", x1, 58, 100, (215, 181, 255))
        kills = f"撃破 {kill_count}" + (f"/{clear_goal}" if clear_goal > 0 else "")
        self._text(screen, kills, x1 + 110, 58, col_w - 110, muted)

        # Separate the main weapon, add-ons, and upgrade prompt into fixed rows.
        self._text(screen, f"武器 {w.main_type.upper()}", x2, 8, col_w - 80, gold, 18)
        self._text(screen, f"SPD×{w.speed_multiplier:.1f}", x2 + col_w - 76, 11, 76, muted, 14)
        addons = []
        if w.laser_level > 0:
            addons.append(f"LASER{w.laser_level}")
        if w.homing_level > 0:
            addons.append(f"HOMING{w.homing_level}")
        if w.magnet_level > 0:
            addons.append(f"MGT{w.magnet_level}")
        if w.has_barrier:
            addons.append("防壁")
        self._text(screen, " / ".join(addons) or "追加装備 なし", x2, 34, col_w, muted, 14)
        stock_color = gold if w.weapon_stock > 0 else muted
        upgrade_key = self._settings.key_display("weapon_select")
        self._text(screen, f"強化 [{upgrade_key}]  ×{w.weapon_stock}", x2, 58, col_w, stock_color)

        # Heat, held pieces, and laser readiness share the right column.
        if heat is not None:
            hot = heat.overheated
            heat_color = (255, 95, 65) if hot or heat.ratio >= 0.85 else (255, 200, 85) if heat.ratio >= 0.6 else (110, 220, 135)
            temp = "熱暴走" if hot else f"{heat.display_temp:.1f}℃"
            self._text(screen, f"体温 {temp}", x3, 10, 132, heat_color)
            self._meter(screen, (x3 + 138, 17, col_w - 138, 9), heat.ratio, heat_color)
        if pieces is not None:
            held = "・".join(pieces) if pieces else "なし"
            bomb_key = self._settings.key_display("bomb")
            self._text(screen, f"持駒 [{bomb_key}] {held}", x3, 34, col_w, gold)
        if laser is None:
            self._text(screen, "レーザー未装備", x3, 59, col_w, muted, 14)
        else:
            state = laser.state
            if state in ("firing", "starting"):
                label, color = "発射", (70, 225, 255)
            elif state == "charging":
                label, color = "溜め", (255, 210, 70)
            elif state == "ready":
                label, color = "準備", (110, 225, 135)
            else:
                label, color = "冷却", muted
            laser_key = self._settings.key_display("laser")
            self._text(screen, f"[{laser_key}] LASER {label}", x3, 59, col_w - 65, color, 14)
            self._meter(screen, (x3 + col_w - 60, 64, 60, 8), laser.gauge_ratio, color)

        # ボスHPバー
        if boss is not None:
            bar_w, bar_h = 400, 18
            bx = (screen.get_width() - bar_w) // 2
            by = screen.get_height() - 36
            boss_back = pygame.Surface((bar_w + 122, 48), pygame.SRCALPHA)
            boss_back.fill((4, 5, 12, 178))
            pygame.draw.rect(boss_back, (255, 255, 255, 48), boss_back.get_rect(), 1, border_radius=6)
            screen.blit(boss_back, (bx - 112, by - 19))
            ratio = max(0.0, min(1.0, boss.hp / boss.max_hp)) if boss.max_hp else 0.0
            pygame.draw.rect(screen, (80, 0, 0),   (bx, by, bar_w, bar_h), border_radius=4)
            pygame.draw.rect(screen, (220, 30, 30), (bx, by, int(bar_w * ratio), bar_h), border_radius=4)
            pygame.draw.rect(screen, (255, 255, 255), (bx, by, bar_w, bar_h), 2, border_radius=4)
            label = self._font.render("BOSS", True, (255, 255, 255))
            screen.blit(label, (bx - label.get_width() - 8, by))

            # 体幹ゲージ（バトルv2）: HPバー直上。ダウン中は点滅表示に切替
            if getattr(boss, "is_stance_down", False):
                blink = (pygame.time.get_ticks() // 150) % 2 == 0
                if blink:
                    dl = self._label_font.render("BREAK!  DAMAGE UP", True, (255, 215, 70))
                    screen.blit(dl, (bx + bar_w // 2 - dl.get_width() // 2, by - 13))
            else:
                sr = boss.stance_ratio() if hasattr(boss, "stance_ratio") else None
                if sr is not None:
                    sy_ = by - 9
                    pygame.draw.rect(screen, (35, 30, 12), (bx, sy_, bar_w, 6), border_radius=3)
                    scol = (255, 205, 80) if sr > 0.35 else (255, 120, 70)
                    pygame.draw.rect(screen, scol, (bx, sy_, int(bar_w * sr), 6), border_radius=3)
                    pygame.draw.rect(screen, (150, 130, 70), (bx, sy_, bar_w, 6), 1, border_radius=3)
