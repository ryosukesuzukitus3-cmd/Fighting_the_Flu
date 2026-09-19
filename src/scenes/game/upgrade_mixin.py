"""ウェポン選択UI ミックスイン — GameScene に多重継承で組み込まれる。

2段構成: 上段=自機ウェポン / 下段=カロナール先輩の支援系統。
取得ごとに自機+1・先輩+1の在庫を別々に持ち、1回の画面で
「上段から1つ → 下段から1つ → 決定」の順に振り分ける。
"""
from __future__ import annotations
import pygame

from src.scenes.game.config import UPGRADE_SLOTS, COMPANION_SLOTS, MAIN_NEXT_NAMES
from src.scenes.meta_ui import (
    ACCENT_CORAL, ACCENT_MINT, BG, TEXT, TEXT_MUTED,
    draw_meta_footer, draw_pixel_cursor, fit_text, wrap_text,
)

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
            if w.main_at_max:
                return "(MAX)"
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

        if inp.is_action_just_pressed("ui_back"):
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
        if inp.is_action_just_pressed("ui_accept"):
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
            # An early visit to the final row must not silently skip a tree.
            if top and self._upg_top_choice is None:
                self._upg_zone = "top"
            elif bot and self._upg_bottom_choice is None:
                self._upg_zone = "bottom"
            else:
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
        self._upgrade_font = self.game.resources.pixelfont(20)
        self._upgrade_slot_font = self.game.resources.pixelfont(19)
        small = self.game.resources.pixelfont(16)
        title_font = self.game.resources.pixelfont(32)
        screen.fill(BG)
        cx = screen.get_width() // 2
        title = title_font.render("ふたりの強化", False, TEXT)
        screen.blit(title, (48, 62))
        stopped = small.render("戦闘停止中", False, TEXT_MUTED)
        screen.blit(stopped, (screen.get_width() - stopped.get_width() - 48, 77))

        steps = {"top": "自機" if self._top_available_indices() else "自機（選択なし）",
                 "bottom": "先輩" if self._bottom_available_indices() else "先輩（選択なし）",
                 "confirm": "確認"}
        x = 48
        for index, (zone, label) in enumerate(steps.items()):
            active = self._upg_zone == zone
            rendered = small.render(label, False, ACCENT_CORAL if active else TEXT_MUTED)
            screen.blit(rendered, (x, 112))
            x += rendered.get_width() + 16
            if index < len(steps) - 1:
                arrow = small.render("→", False, TEXT_MUTED)
                screen.blit(arrow, (x, 112))
                x += arrow.get_width() + 16

        ws = self.player.weapon.weapon_stock
        c = self._companion
        cs = c.stock if c is not None else 0
        top_avail = lambda i: ws > 0 and self._is_upgrade_available(UPGRADE_SLOTS[i][0])
        bot_avail = lambda i: c is not None and cs > 0 and c.is_upgrade_available(COMPANION_SLOTS[i][0])
        top_label = f"自機  ストック {ws}" + ("  /  選択済み" if self._upg_top_choice is not None else "")
        bottom_label = (f"カロナール先輩  ストック {cs}" if c is not None else
                        "カロナール先輩  離脱中" if self.game.story.karonaru_lost else "カロナール先輩  未参戦")
        if self._upg_bottom_choice is not None:
            bottom_label += "  /  選択済み"
        screen.blit(self._upgrade_font.render(top_label, False, TEXT), (48, 170))
        screen.blit(self._upgrade_font.render(bottom_label, False, TEXT), (48, 298))
        self._draw_slot_row(screen, UPGRADE_SLOTS, 211, self._upg_top_cursor,
                            self._upg_top_choice, self._upg_zone == "top",
                            self._slot_display_label, top_avail)
        self._draw_slot_row(screen, COMPANION_SLOTS, 339, self._upg_bottom_cursor,
                            self._upg_bottom_choice, self._upg_zone == "bottom",
                            self._companion_slot_label, bot_avail, dim=c is None)

        descriptions = {
            "weapon_main": "連射・弾の広がりを強化。主砲を2回強化すると追加装備が解放。",
            "speed": "移動を速くして弾や地形を避けやすくします。",
            "laser": (f"[{self.game.settings.key_display('laser')}] 押している間だけ発射。"
                      "離すと停止・冷却。隙にまとめて撃ち込む。"),
            "homing": "敵を追う弾を通常射撃に追加します。",
            "kt_hp": "先輩の耐久力を上げ、その場で回復します。",
            "kt_shot": "先輩の解熱弾を強化し、自機の体温も下がりやすくします。",
            "kt_supply": "先輩が回復アイテムを届けます。",
            "kt_magnet": "近くのアイテムを自機へ引き寄せます。",
        }
        if self._upg_zone == "top":
            key = UPGRADE_SLOTS[self._upg_top_cursor][0]
        elif self._upg_zone == "bottom":
            key = COMPANION_SLOTS[self._upg_bottom_cursor][0]
        else:
            key = None
        if key is None:
            chosen = []
            if self._upg_top_choice is not None:
                chosen.append("自機: " + self._slot_display_label(UPGRADE_SLOTS[self._upg_top_choice][0]))
            if self._upg_bottom_choice is not None:
                chosen.append("先輩: " + self._companion_slot_label(COMPANION_SLOTS[self._upg_bottom_choice][0]))
            explanation = "  /  ".join(chosen) or (
                "強化する項目を選んでください。"
                if self._top_available_indices() or self._bottom_available_indices()
                else "現在、強化できる項目はありません。在庫は残ります。")
        else:
            explanation = descriptions[key]
        for row, text in enumerate(wrap_text(small, explanation, screen.get_width() - 96)):
            detail = small.render(text, False, TEXT_MUTED)
            screen.blit(detail, (cx - detail.get_width() // 2, 419 + row * 22))
        complete = ((not self._top_available_indices() or self._upg_top_choice is not None)
                    and (not self._bottom_available_indices() or self._upg_bottom_choice is not None))
        has_choice = self._upg_top_choice is not None or self._upg_bottom_choice is not None
        label = "強化して再開" if has_choice and complete else "未選択の項目へ" if not complete else "ゲームに戻る"
        focused = self._upg_zone == "confirm"
        rendered = self._upgrade_font.render(label, False, ACCENT_CORAL if focused else ACCENT_MINT)
        target = rendered.get_rect(center=(cx, 486))
        screen.blit(rendered, target)
        if focused:
            draw_pixel_cursor(screen, target.x - 26, target.centery)
        accept = self.game.settings.key_display("ui_accept")
        back = self.game.settings.key_display("ui_back")
        action = label if focused else "選ぶ・次へ"
        draw_meta_footer(screen, small, f"←→: 項目   ↑↓: 段を移動   {accept}: {action}   {back}: 保留して閉じる")

    def _draw_slot_row(self, screen, slots, y, cursor, choice, zone_active,
                       label_fn, avail_fn, dim: bool = False) -> None:
        box_w, gap = 156, 12
        total = len(slots) * box_w + (len(slots) - 1) * gap
        sx0 = screen.get_width() // 2 - total // 2
        for i, (key, _) in enumerate(slots):
            avail   = avail_fn(i)
            focused = zone_active and i == cursor
            chosen  = choice == i
            bx = sx0 + i * (box_w + gap)
            if dim:
                tx = TEXT_MUTED
            elif focused and avail:
                tx = ACCENT_CORAL
            elif chosen:
                tx = ACCENT_MINT
            elif avail:
                tx = TEXT
            else:
                tx = TEXT_MUTED
            names = {"weapon_main": "主砲", "homing": "追尾弾", "laser": "レーザー", "speed": "移動速度",
                     "kt_hp": "先輩の耐久", "kt_shot": "解熱弾", "kt_supply": "回復補給", "kt_magnet": "引き寄せ"}
            label = names[key]
            if focused and avail:
                draw_pixel_cursor(screen, bx, y + 23)
            surf = self._upgrade_slot_font.render(fit_text(self._upgrade_slot_font, label, box_w - 20), False, tx)
            screen.blit(surf, (bx + box_w // 2 - surf.get_width() // 2,
                               y + 8))
            if chosen:
                status = "選択済み"
            elif dim:
                status = "現在は選択不可"
            elif key in {"homing", "laser"} and self.player.weapon.main_level < 2:
                status = "主砲 Lv2で解放"
            elif not avail:
                status = "最大強化" if "MAX" in label_fn(key) else "在庫なし"
            else:
                status = "次: " + label_fn(key)
            font = self.game.resources.pixelfont(14)
            detail_color = ACCENT_MINT if chosen else ACCENT_CORAL if focused and avail else TEXT_MUTED
            detail = font.render(fit_text(font, status, box_w - 12), False, detail_color)
            screen.blit(detail, (bx + box_w // 2 - detail.get_width() // 2, y + 38))
