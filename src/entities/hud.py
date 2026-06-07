from __future__ import annotations
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from src.core.game import Game
    from src.entities.player import Player
    from src.entities.laser_beam import LaserBeam

_HP_BAR_W       = 200    # HP ゲージ幅(px)
_HP_BAR_H       = 16
_HP_COLOR       = (220, 50,  50)
_HP_COLOR_LOW   = (240, 180, 40)   # 残量わずか時の色
_HP_EMPTY_COLOR = (50,  18,  18)


class HUD:
    def __init__(self, game: Game) -> None:
        self._font       = game.resources.pixelfont(22)
        self._label_font = game.resources.pixelfont(14)

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
    ) -> None:
        # スコア
        score_surf = self._font.render(f"SCORE: {score}", True, (255, 255, 255))
        screen.blit(score_surf, (10, 10))

        # キル数 / 目標
        kill_surf = self._font.render(f"KILL: {kill_count} / {clear_goal}", True, (200, 200, 200))
        screen.blit(kill_surf, (10, 38))

        # HP（多段階ゲージ）
        hp_x, hp_y = 10, 68
        ratio = max(0.0, player.hp / player.max_hp) if player.max_hp else 0.0
        pygame.draw.rect(screen, _HP_EMPTY_COLOR, (hp_x, hp_y, _HP_BAR_W, _HP_BAR_H), border_radius=4)
        fill_col = _HP_COLOR if ratio > 0.3 else _HP_COLOR_LOW
        pygame.draw.rect(screen, fill_col,
                         (hp_x, hp_y, int(_HP_BAR_W * ratio), _HP_BAR_H), border_radius=4)
        pygame.draw.rect(screen, (200, 200, 210), (hp_x, hp_y, _HP_BAR_W, _HP_BAR_H), 1, border_radius=4)
        hp_label = self._label_font.render(f"HP {max(0, player.hp)}/{player.max_hp}", True, (255, 255, 255))
        screen.blit(hp_label, (hp_x + _HP_BAR_W + 8, hp_y + 1))

        # 残機（HP バーの下）
        if lives > 0:
            lives_surf = self._label_font.render(f"残機: {lives}", True, (160, 100, 220))
            screen.blit(lives_surf, (hp_x + _HP_BAR_W + 8, hp_y - 14))

        # 武器レベル
        w = player.weapon
        weapon_names = ["SINGLE", "RAPID1", "RAPID2", "WIDE", "WIDE+", "MEDIC"]
        weapon_text  = weapon_names[min(w.main_level, len(weapon_names) - 1)]
        addons = []
        if w.laser_level > 0:  addons.append(f"LASER{w.laser_level}")
        if w.homing_level > 0: addons.append(f"HOMING{w.homing_level}")
        if w.magnet_level > 0: addons.append(f"MGT{'◆' * w.magnet_level}")
        if w.has_barrier:     addons.append("BARRIER")
        if w.speed_level > 0: addons.append(f"SPD×{1.0 + w.speed_level * 0.2:.1f}")
        if addons:
            weapon_text += " + " + " + ".join(addons)
        weapon_surf = self._font.render(f"WEAPON: {weapon_text}", True, (255, 220, 80))
        screen.blit(weapon_surf, (10, 96))

        # ウェポンアイテム在庫（V キーで選択画面）。在庫がある間は点滅で強調。
        if w.weapon_stock > 0:
            blink = (pygame.time.get_ticks() // 400) % 2 == 0
            col = (255, 240, 120) if blink else (120, 220, 255)
            stock_surf = self._label_font.render(
                f"★ WEAPON STOCK x{w.weapon_stock}  [V で強化] ★", True, col)
            screen.blit(stock_surf, (10, 124))

        # ── レーザーチャージバー ──────────────────────────────────
        if laser is not None:
            bar_x, bar_y = 10, 152
            bar_w, bar_h = 120, 10
            ratio = laser.gauge_ratio

            # 背景
            pygame.draw.rect(screen, (30, 30, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
            # 充填
            if laser.state == "ready":
                fill_color = (60, 180, 60)           # 緑: 準備完了
            elif laser.state == "charging":
                fill_color = (255, 200, 60)          # 黄: チャージ中
            elif laser.state in ("starting", "firing"):
                fill_color = (60, 220, 255)          # 水色: 発射中
            else:
                fill_color = (30, 100, 160)          # 暗青: 終了/冷却中
            pygame.draw.rect(
                screen, fill_color,
                (bar_x, bar_y, int(bar_w * ratio), bar_h),
                border_radius=3,
            )
            # 枠
            pygame.draw.rect(screen, (80, 80, 120), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=3)

            # 状態ラベル
            if laser.state in ("firing", "starting"):
                label_txt, label_col = "LASER FIRE", (60, 220, 255)
            elif laser.state == "charging":
                label_txt, label_col = "LASER CHARGE", (255, 200, 60)
            elif laser.state == "ending":
                label_txt, label_col = "LASER END", (100, 150, 200)
            else:
                label_txt, label_col = "LASER READY", (60, 180, 60)
            label = self._label_font.render(label_txt, True, label_col)
            screen.blit(label, (bar_x + bar_w + 6, bar_y - 2))

        # ボスHPバー
        if boss is not None:
            bar_w, bar_h = 400, 18
            bx = (screen.get_width() - bar_w) // 2
            by = screen.get_height() - 36
            ratio = max(0.0, boss.hp / boss.max_hp)
            pygame.draw.rect(screen, (80, 0, 0),   (bx, by, bar_w, bar_h), border_radius=4)
            pygame.draw.rect(screen, (220, 30, 30), (bx, by, int(bar_w * ratio), bar_h), border_radius=4)
            pygame.draw.rect(screen, (255, 255, 255), (bx, by, bar_w, bar_h), 2, border_radius=4)
            label = self._font.render("BOSS", True, (255, 255, 255))
            screen.blit(label, (bx - label.get_width() - 8, by))
