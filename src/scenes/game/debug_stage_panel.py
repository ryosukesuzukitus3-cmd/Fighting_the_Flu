"""デバッグステージ専用パネルUI（stage_id=99 のみ使用）。
Tab: 開閉 / ← →: タブ切替 / ↑ ↓: 項目選択 / ← →: 値変更 or ENTER: スポーン・決定
"""
from __future__ import annotations
import pygame
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT

_PANEL_W  = 250
_PANEL_H  = SCREEN_HEIGHT - 40
_PANEL_X  = 8
_PANEL_Y  = 20

_TABS = ["WEAPON", "BGM", "ITEM", "ENEMY", "BOSS"]

_BGM_LIST = [
    "MEGALOVANIA.mp3",
    "決戦.mp3",
    "決戦_FF10.mp3",
    "決戦！N.mp3",
    "ビッグブリッヂの死闘.mp3",
    "戦艦ハルバード：甲板.mp3",
    "Death_by_Glamour.mp3",
    "il_vento_d'oro.mp3",
    "GREEN_HILL_ZONE.mp3",
    "Rebirth_the_edge.mp3",
    "The_world_of_spirit.mp3",
    "とげとげタルめいろ.mp3",
    "シズメシズメ.mp3",
    "ノイズ_重低音.mp3",
    "ノイズ_電気.mp3",
]

# (ラベル, フィールド名, 最小値, 最大値, bool=False)
_WEAPON_ITEMS = [
    ("main_level",   "main_level",   1, 5,    False),
    ("laser_level",  "laser_level",  0, 6,    False),
    ("homing_level", "homing_level", 0, 7,    False),
    ("speed_level",  "speed_level",  0, 5,    False),
    ("has_barrier",  "has_barrier",  0, 1,    True),
    ("magnet_level", "magnet_level", 0, 3,    False),
]

from src.core.registries import ENEMY_DEFS, ITEM_NAMES
_ENEMY_ENTRIES: list[str] = [d.name for d in ENEMY_DEFS if d.debug_spawnable]
_ITEM_ENTRIES:  list[str] = ITEM_NAMES

_BOSS_ENTRIES = ["Stage 1 Boss", "Stage 2 Boss", "Stage 3 Boss", "Stage 4 Boss"]


class DebugStagePanel:
    def __init__(self, game, game_scene) -> None:
        self._game = game
        self._gs   = game_scene
        self._open           = False
        self._tab            = 0
        self._cursor         = 0
        self._weapon_editing = False
        self._font       = game.resources.pixelfont(16)
        self._font_sm    = game.resources.pixelfont(13)
        self._font_title = game.resources.pixelfont(14)

    # ── update ────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        inp = self._game.input
        if inp.is_just_pressed(pygame.K_TAB):
            self._open = not self._open
            self._cursor = 0
            self._weapon_editing = False
            return

        if not self._open:
            return

        # タブ切替（← →）— ウェポン編集中はスキップ
        if not self._weapon_editing:
            if inp.is_just_pressed(pygame.K_LEFT):
                self._tab    = (self._tab - 1) % len(_TABS)
                self._cursor = 0
            if inp.is_just_pressed(pygame.K_RIGHT):
                self._tab    = (self._tab + 1) % len(_TABS)
                self._cursor = 0

        tab = _TABS[self._tab]
        if tab == "WEAPON":
            self._update_weapon()
        elif tab == "BGM":
            self._update_list(len(_BGM_LIST), self._select_bgm)
        elif tab == "ITEM":
            self._update_list(len(_ITEM_ENTRIES), self._spawn_item)
        elif tab == "ENEMY":
            self._update_list(len(_ENEMY_ENTRIES), self._spawn_enemy)
        elif tab == "BOSS":
            self._update_list(len(_BOSS_ENTRIES), self._spawn_boss)

    def _update_list(self, count: int, on_enter) -> None:
        inp = self._game.input
        if inp.is_just_pressed(pygame.K_UP):
            self._cursor = (self._cursor - 1) % count
        if inp.is_just_pressed(pygame.K_DOWN):
            self._cursor = (self._cursor + 1) % count
        if inp.is_just_pressed(pygame.K_RETURN):
            on_enter(self._cursor)

    def _update_weapon(self) -> None:
        inp = self._game.input

        if self._weapon_editing:
            label, field, vmin, vmax, is_bool = _WEAPON_ITEMS[self._cursor]
            weapon = self._gs.player.weapon
            cur_val = getattr(weapon, field)
            if is_bool:
                if inp.is_just_pressed(pygame.K_LEFT) or inp.is_just_pressed(pygame.K_RIGHT):
                    setattr(weapon, field, not cur_val)
            else:
                if inp.is_just_pressed(pygame.K_LEFT):
                    setattr(weapon, field, max(vmin, cur_val - 1))
                if inp.is_just_pressed(pygame.K_RIGHT):
                    setattr(weapon, field, min(vmax, cur_val + 1))
            if inp.is_just_pressed(pygame.K_RETURN):
                self._weapon_editing = False
        else:
            if inp.is_just_pressed(pygame.K_UP):
                self._cursor = (self._cursor - 1) % len(_WEAPON_ITEMS)
            if inp.is_just_pressed(pygame.K_DOWN):
                self._cursor = (self._cursor + 1) % len(_WEAPON_ITEMS)
            if inp.is_just_pressed(pygame.K_RETURN):
                self._weapon_editing = True

    # ── アクション ────────────────────────────────────────────────

    def _select_bgm(self, idx: int) -> None:
        self._game.sound.play_bgm(f"music/bgm/{_BGM_LIST[idx]}")

    def _spawn_item(self, idx: int) -> None:
        name = _ITEM_ENTRIES[idx]
        wx, wy = self._gs.player.muzzle_world(self._gs.camera)
        wx += 80
        item = _make_item(name, wx, wy)
        if item is not None:
            self._gs.items.add(item)

    def _spawn_enemy(self, idx: int) -> None:
        name = _ENEMY_ENTRIES[idx]
        world_x = self._gs.camera.spawn_x(50)
        world_y = float(SCREEN_HEIGHT // 2)
        enemy = _make_enemy(name, self._game, world_x, world_y)
        if enemy is not None:
            self._gs.enemies.add(enemy)

    def _spawn_boss(self, idx: int) -> None:
        stage_for_boss = idx + 1
        if self._gs._boss is not None:
            if self._gs._boss._stage_id == stage_for_boss:
                self._gs._on_boss_killed()  # 同じボスを再選択 → 消す
            return
        orig_id = self._gs._stage_id
        self._gs._stage_id = stage_for_boss
        self._gs.spawner._index      = len(self._gs.spawner._events)
        self._gs.spawner.boss_pending = True
        self._gs._stage_id = orig_id

    # ── draw ──────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface) -> None:
        if not self._open:
            hint = self._font_sm.render("Tab: DEBUGパネル  X: ポーズ", True, (60, 60, 80))
            screen.blit(hint, (8, SCREEN_HEIGHT - 22))
            return

        # パネル背景
        panel = pygame.Surface((_PANEL_W, _PANEL_H), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 210))
        screen.blit(panel, (_PANEL_X, _PANEL_Y))

        px = _PANEL_X + 8
        py = _PANEL_Y + 8

        # タイトル行
        title = self._font_title.render("[ DEBUG PANEL ]  Tab:閉じる", True, (255, 80, 80))
        screen.blit(title, (px, py))
        py += 20

        # タブ行
        tab_x = px
        for i, tab in enumerate(_TABS):
            color = (255, 220, 60) if i == self._tab else (120, 120, 140)
            s = self._font_sm.render(tab, True, color)
            screen.blit(s, (tab_x, py))
            tab_x += s.get_width() + 8
        py += 18

        pygame.draw.line(screen, (60, 60, 80), (px, py), (px + _PANEL_W - 16, py))
        py += 6

        # タブ別コンテンツ
        tab = _TABS[self._tab]
        if tab == "WEAPON":
            self._draw_weapon(screen, px, py)
        elif tab == "BGM":
            self._draw_list(screen, px, py, _BGM_LIST)
        elif tab == "ITEM":
            self._draw_list(screen, px, py, _ITEM_ENTRIES)
        elif tab == "ENEMY":
            self._draw_list(screen, px, py, _ENEMY_ENTRIES)
        elif tab == "BOSS":
            self._draw_list(screen, px, py, _BOSS_ENTRIES, note="ENTER: スポーン")

        # 下部ヒント
        hy = _PANEL_Y + _PANEL_H - 20
        pygame.draw.line(screen, (60, 60, 80), (px, hy - 4), (px + _PANEL_W - 16, hy - 4))
        if _TABS[self._tab] == "WEAPON" and self._weapon_editing:
            hint_str = "←→:値変更  ENTER:確定"
        elif _TABS[self._tab] == "WEAPON":
            hint_str = "↑↓:選択  ENTER:編集  ←→:タブ切替"
        else:
            hint_str = "↑↓:選択  ←→:タブ切替  ENTER:決定"
        hint = self._font_sm.render(hint_str, True, (80, 80, 100))
        screen.blit(hint, (px, hy))

    def _draw_weapon(self, screen: pygame.Surface, px: int, py: int) -> None:
        weapon = self._gs.player.weapon
        for i, (label, field, vmin, vmax, is_bool) in enumerate(_WEAPON_ITEMS):
            selected = (i == self._cursor)
            editing  = selected and self._weapon_editing
            color = (100, 255, 100) if editing else (255, 220, 60) if selected else (180, 180, 200)
            val = getattr(weapon, field)
            val_str = "ON" if (is_bool and val) else "OFF" if is_bool else str(val)
            prefix = "> " if selected else "  "
            val_display = f"[{val_str}]" if editing else val_str
            row = f"{prefix}{label:<14}: {val_display}"
            s = self._font.render(row, True, color)
            screen.blit(s, (px, py + i * 18))

    def _draw_list(self, screen: pygame.Surface, px: int, py: int,
                   entries: list, note: str = "ENTER: 実行") -> None:
        max_visible = (_PANEL_H - 90) // 18
        start = max(0, self._cursor - max_visible + 1)
        visible = entries[start: start + max_visible]
        for i, entry in enumerate(visible):
            real_i = start + i
            selected = (real_i == self._cursor)
            color = (255, 220, 60) if selected else (180, 180, 200)
            prefix = "> " if selected else "  "
            s = self._font.render(prefix + entry, True, color)
            screen.blit(s, (px, py + i * 18))
        # ノート
        note_s = self._font_sm.render(note, True, (100, 140, 100))
        screen.blit(note_s, (px, py + max_visible * 18 + 4))


# ── アイテム・敵 ファクトリ ──────────────────────────────────────

def _make_item(name: str, wx: float, wy: float):
    if name == "WeaponItem":
        from src.entities.items.weapon_item import WeaponItem
        return WeaponItem(wx, wy)
    if name == "HealItem":
        from src.entities.items.heal import HealItem
        return HealItem(wx, wy)
    if name == "ScoreItem":
        from src.entities.items.score_item import ScoreItem
        return ScoreItem(wx, wy)
    if name == "ExtraLifeItem":
        from src.entities.items.extra_life import ExtraLifeItem
        return ExtraLifeItem(wx, wy)
    return None


def _make_enemy(name: str, game, wx: float, wy: float):
    if name == "EnemyVirus":
        from src.entities.enemies.virus import EnemyVirus
        return EnemyVirus(game, wx, wy)
    if name == "EnemyTakeshi":
        from src.entities.enemies.takeshi import EnemyTakeshi
        return EnemyTakeshi(game, wx, wy)
    if name == "EnemyBroly":
        from src.entities.enemies.broly import EnemyBroly
        return EnemyBroly(game, wx, wy)
    if name == "EnemyPachemon":
        from src.entities.enemies.pachemon import EnemyPachemon
        return EnemyPachemon(game, wx, wy)
    if name == "EnemyBilly":
        from src.entities.enemies.billy import EnemyBilly
        return EnemyBilly(game, wx, wy)
    if name == "EnemyTurret":
        from src.entities.enemies.turret import EnemyTurret
        return EnemyTurret(game, wx, wy)
    return None
