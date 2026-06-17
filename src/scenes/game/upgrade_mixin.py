"""ウェポン選択UI ミックスイン — GameScene に多重継承で組み込まれる。

2段構成: 上段=自機ウェポン / 下段=カロナール先輩の支援系統。
取得ごとに自機+1・先輩+1の在庫を別々に持ち、1回の画面で
「上段から1つ → 下段から1つ → 決定」の順に振り分ける。
"""
from __future__ import annotations
import pygame

from src.scenes.game.config import UPGRADE_SLOTS, COMPANION_SLOTS, MAIN_NEXT_NAMES

_KT_MAX_LEVEL = 3   # 先輩系統の最大Lv（companion._KT_MAX_LEVEL と一致）


class GameSceneUpgradeMixin:
    """ボス撃破後／在庫使用時のウェポン選択UI（2段）の入力・描画を担当する。"""

    # ── 自機（上段）──────────────────────────────────────────────
    def _is_upgrade_available(self, key: str) -> bool:
        w = self.player.weapon  # type: ignore[attr-defined]
        if key == "weapon_main": return not w.main_at_max
        if key == "speed":       return not w.speed_at_max
        if key == "laser":       return w.main_level >= 2 and w.laser_level < 6
        if key == "homing":      return w.main_level >= 2 and w.homing_level < 7
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
            return f"LASER {lv + 1}" if lv < 6 else "LSR MAX"
        if key == "homing":
            lv = w.homing_level
            return f"HOMING {lv + 1}" if lv < 7 else "HOM MAX"
        return key

    # ── 先輩（下段）──────────────────────────────────────────────
    def _companion_slot_label(self, key: str) -> str:
        name = dict(COMPANION_SLOTS).get(key, key)
        c = self._companion  # type: ignore[attr-defined]
        if c is None:
            return name
        if not c.is_upgrade_available(key):
            return f"{name} MAX"
        return f"{name} {c.upgrade_level(key) + 1}"

    # ── 在庫・選択可能インデックス ────────────────────────────────
    def _top_available_indices(self) -> list[int]:
        if self.player.weapon.weapon_stock <= 0:  # type: ignore[attr-defined]
            return []
        return [i for i, (k, _) in enumerate(UPGRADE_SLOTS)
                if self._is_upgrade_available(k)]

    def _bottom_available_indices(self) -> list[int]:
        c = self._companion  # type: ignore[attr-defined]
        if c is None or c.stock <= 0:
            return []
        return [i for i, (k, _) in enumerate(COMPANION_SLOTS)
                if c.is_upgrade_available(k)]

    # ── 起動 ─────────────────────────────────────────────────────
    def _open_upgrade_ui(self) -> None:
        self._upgrading        = True   # type: ignore[attr-defined]
        self._upg_top_choice    = None  # type: ignore[attr-defined]
        self._upg_bottom_choice = None  # type: ignore[attr-defined]
        top = self._top_available_indices()
        bot = self._bottom_available_indices()
        self._upg_top_cursor    = top[0] if top else 0  # type: ignore[attr-defined]
        self._upg_bottom_cursor = bot[0] if bot else 0  # type: ignore[attr-defined]
        self._upg_zone = "top" if top else ("bottom" if bot else "confirm")  # type: ignore[attr-defined]
        self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.5)  # type: ignore[attr-defined]

    # ── 入力 ─────────────────────────────────────────────────────
    def _update_upgrade_ui(self) -> None:
        inp = self.game.input  # type: ignore[attr-defined]
        top = self._top_available_indices()
        bot = self._bottom_available_indices()

        if inp.is_just_pressed(pygame.K_x):
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)  # type: ignore[attr-defined]
            self._upgrading = False  # type: ignore[attr-defined]
            return

        if inp.is_just_pressed(pygame.K_LEFT):
            self._move_cursor(-1, top, bot)
        if inp.is_just_pressed(pygame.K_RIGHT):
            self._move_cursor(1, top, bot)
        if inp.is_just_pressed(pygame.K_UP):
            self._move_zone(-1, top, bot)
        if inp.is_just_pressed(pygame.K_DOWN):
            self._move_zone(1, top, bot)
        if inp.is_just_pressed(pygame.K_RETURN):
            self._confirm_zone(top, bot)

    def _move_cursor(self, delta: int, top: list[int], bot: list[int]) -> None:
        zone = self._upg_zone  # type: ignore[attr-defined]
        if zone == "top":
            indices, attr = top, "_upg_top_cursor"
        elif zone == "bottom":
            indices, attr = bot, "_upg_bottom_cursor"
        else:
            return
        if not indices:
            return
        cur = getattr(self, attr)
        pos = indices.index(cur) if cur in indices else 0
        setattr(self, attr, indices[(pos + delta) % len(indices)])
        self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)  # type: ignore[attr-defined]

    def _move_zone(self, delta: int, top: list[int], bot: list[int]) -> None:
        zones: list[str] = []
        if top: zones.append("top")
        if bot: zones.append("bottom")
        zones.append("confirm")
        cur = self._upg_zone  # type: ignore[attr-defined]
        if cur not in zones:
            self._upg_zone = zones[0]  # type: ignore[attr-defined]
            return
        self._upg_zone = zones[(zones.index(cur) + delta) % len(zones)]  # type: ignore[attr-defined]
        self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)  # type: ignore[attr-defined]

    def _confirm_zone(self, top: list[int], bot: list[int]) -> None:
        zone = self._upg_zone  # type: ignore[attr-defined]
        if zone == "top":
            if top:
                self._upg_top_choice = self._upg_top_cursor  # type: ignore[attr-defined]
                self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)  # type: ignore[attr-defined]
            self._upg_zone = "bottom" if bot else "confirm"  # type: ignore[attr-defined]
        elif zone == "bottom":
            if bot:
                self._upg_bottom_choice = self._upg_bottom_cursor  # type: ignore[attr-defined]
                self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)  # type: ignore[attr-defined]
            if self._upg_top_choice is None and top:  # type: ignore[attr-defined]
                self._upg_zone = "top"  # type: ignore[attr-defined]
            else:
                self._upg_zone = "confirm"  # type: ignore[attr-defined]
        else:  # confirm
            self._apply_upgrade_choices()

    def _apply_upgrade_choices(self) -> None:
        applied = False
        w = self.player.weapon  # type: ignore[attr-defined]
        top_choice = self._upg_top_choice      # type: ignore[attr-defined]
        bot_choice = self._upg_bottom_choice   # type: ignore[attr-defined]
        if top_choice is not None and w.weapon_stock > 0:
            key = UPGRADE_SLOTS[top_choice][0]
            if self._is_upgrade_available(key):
                w.upgrade(key)
                w.weapon_stock = max(0, w.weapon_stock - 1)
                applied = True
        c = self._companion  # type: ignore[attr-defined]
        if bot_choice is not None and c is not None and c.stock > 0:
            key = COMPANION_SLOTS[bot_choice][0]
            if c.is_upgrade_available(key):
                c.apply_upgrade(key)
                c.stock = max(0, c.stock - 1)
                applied = True
        if applied:
            self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)  # type: ignore[attr-defined]
        self._upgrading = False  # type: ignore[attr-defined]

    # ── 描画 ─────────────────────────────────────────────────────
    def _draw_upgrade_ui(self, screen: pygame.Surface) -> None:
        if self._upgrade_font is None:  # type: ignore[attr-defined]
            self._upgrade_font       = self.game.resources.pixelfont(20)  # type: ignore[attr-defined]
            self._upgrade_title_font = self.game.resources.pixelfont(42)  # type: ignore[attr-defined]
            self._upgrade_slot_font  = self.game.resources.pixelfont(18)  # type: ignore[attr-defined]
        small = self.game.resources.pixelfont(16)  # type: ignore[attr-defined]

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        cx = screen.get_width()  // 2
        cy = screen.get_height() // 2

        title = self._upgrade_title_font.render("POWER UP!", True, (255, 220, 80))  # type: ignore[attr-defined]
        screen.blit(title, (cx - title.get_width() // 2, cy - 168))

        ws = self.player.weapon.weapon_stock  # type: ignore[attr-defined]
        c  = self._companion                  # type: ignore[attr-defined]
        cs = c.stock if c is not None else 0

        # 上段: 自機
        top_avail = lambda i: ws > 0 and self._is_upgrade_available(UPGRADE_SLOTS[i][0])
        screen.blit(small.render(f"自機  (在庫 x{ws})", True, (180, 210, 255)), (cx - 258, cy - 118))
        self._draw_slot_row(
            screen, UPGRADE_SLOTS, cy - 96,
            self._upg_top_cursor, self._upg_top_choice,            # type: ignore[attr-defined]
            self._upg_zone == "top",                                # type: ignore[attr-defined]
            self._slot_display_label, top_avail,
        )

        # 下段: 先輩
        bot_avail = lambda i: (c is not None and cs > 0
                               and c.is_upgrade_available(COMPANION_SLOTS[i][0]))
        senpai_label = f"カロナール先輩  (在庫 x{cs})" if c is not None else "カロナール先輩  (未参戦)"
        screen.blit(small.render(senpai_label, True, (150, 235, 170)), (cx - 258, cy - 16))
        self._draw_slot_row(
            screen, COMPANION_SLOTS, cy + 6,
            self._upg_bottom_cursor, self._upg_bottom_choice,       # type: ignore[attr-defined]
            self._upg_zone == "bottom",                             # type: ignore[attr-defined]
            self._companion_slot_label, bot_avail,
        )

        # 決定ボタン
        btn_w, btn_h = 170, 42
        bx = cx - btn_w // 2
        by = cy + 86
        if self._upg_zone == "confirm":  # type: ignore[attr-defined]
            bg, bd, tx = (255, 220, 80), (255, 200, 0), (20, 20, 20)
        else:
            bg, bd, tx = (35, 40, 60), (80, 100, 140), (200, 200, 220)
        pygame.draw.rect(screen, bg, (bx, by, btn_w, btn_h), border_radius=8)
        pygame.draw.rect(screen, bd, (bx, by, btn_w, btn_h), 2, border_radius=8)
        dlabel = self._upgrade_font.render("決定", True, tx)  # type: ignore[attr-defined]
        screen.blit(dlabel, (bx + btn_w // 2 - dlabel.get_width() // 2,
                             by + btn_h // 2 - dlabel.get_height() // 2))

        hint = small.render(
            "↑↓:行移動   ←→:選択   ENTER:決定/送り   X:閉じる", True, (130, 130, 150))
        screen.blit(hint, (cx - hint.get_width() // 2, cy + 140))

    def _draw_slot_row(self, screen, slots, y, cursor, choice, zone_active,
                       label_fn, avail_fn) -> None:
        box_w, box_h, gap = 120, 58, 12
        total = len(slots) * box_w + (len(slots) - 1) * gap
        sx0 = screen.get_width() // 2 - total // 2
        for i, (key, _) in enumerate(slots):
            avail   = avail_fn(i)
            focused = zone_active and i == cursor
            chosen  = choice == i
            bx = sx0 + i * (box_w + gap)
            if focused and avail:
                bg, bd, tx = (255, 220, 80), (255, 200, 0), (20, 20, 20)
            elif chosen:
                bg, bd, tx = (40, 120, 70), (120, 230, 150), (235, 255, 240)
            elif avail:
                bg, bd, tx = (35, 40, 60), (80, 100, 140), (200, 200, 220)
            else:
                bg, bd, tx = (25, 25, 35), (50, 50, 60), (70, 70, 80)
            pygame.draw.rect(screen, bg, (bx, y, box_w, box_h), border_radius=7)
            pygame.draw.rect(screen, bd, (bx, y, box_w, box_h), 2, border_radius=7)
            label = label_fn(key)
            surf  = self._upgrade_slot_font.render(label, True, tx)  # type: ignore[attr-defined]
            screen.blit(surf, (bx + box_w // 2 - surf.get_width() // 2,
                               y + box_h // 2 - surf.get_height() // 2))
            if chosen:  # 選択済みマーカー（右上の緑丸）
                pygame.draw.circle(screen, (140, 240, 170), (bx + box_w - 12, y + 12), 6)
                pygame.draw.circle(screen, (20, 60, 30), (bx + box_w - 12, y + 12), 6, 2)
