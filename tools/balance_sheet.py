"""ゲームバランス数値シート。

pygame を起動せずに武器DPS・敵HP・ボス想定撃破時間を一覧表示する。

使い方:
  python tools/balance_sheet.py
  python tools/balance_sheet.py --section enemy   # 敵HPのみ
  python tools/balance_sheet.py --section weapon  # 武器DPSのみ
  python tools/balance_sheet.py --section boss    # ボス想定撃破時間のみ
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

# pygame をダミードライバで無音起動（Surface 生成を伴うモジュールのインポート対策）
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).parent.parent))

import pygame
pygame.init()

# ── ゲームモジュールのインポート ────────────────────────────────
from src.entities.laser_beam import _LEVEL_CONFIG as _LASER_CFG
from src.entities.enemies.boss import _BOSS_CONFIG, _FORM2_CONFIG
from src.entities.bullets.player_bullet import _HOMING_DAMAGE
from src.entities.weapon import _HOMING_CONFIG as _HOMING_CFG
from src.entities.weapon import _MAIN_FIRE_CONFIG as _MAIN_CFG
from src.core.registries import ENEMY_DEFS

# ── 敵基本ステータス ────────────────────────────────────────────
# src/core/registries.ENEMY_DEFS.stats から導出する。
_ENEMY_BASE: dict[str, tuple[int, float, int, float, str]] = {
    d.name: (
        d.stats.base_hp,
        d.stats.base_speed,
        d.stats.enhanced_hp,
        d.stats.enhanced_speed,
        d.stats.note,
    )
    for d in ENEMY_DEFS
    if d.stats is not None
}

# ── ユーティリティ ───────────────────────────────────────────

def _col(s: str, w: int) -> str:
    return s[:w].ljust(w)

def _sep(widths: list[int]) -> str:
    return "+" + "+".join("-" * (w + 2) for w in widths) + "+"

def _row(cells: list[str], widths: list[int]) -> str:
    return "|" + "|".join(f" {_col(c, w)} " for c, w in zip(cells, widths)) + "|"

def _header(headers: list[str], widths: list[int]) -> str:
    return _row(headers, widths)

# ── セクション1: 敵 HP テーブル ─────────────────────────────

def print_enemy_hp() -> None:
    widths  = [16, 7, 7, 26]
    headers = ["Enemy", "BaseHP", "EnhHP", "備考"]

    print("\n=== ENEMY HP TABLE ===")
    print(_sep(widths))
    print(_header(headers, widths))
    print(_sep(widths))
    for ename, (base_hp, _, enh_hp, __, note) in _ENEMY_BASE.items():
        print(_row([ename, str(base_hp), str(enh_hp), note], widths))
    print(_sep(widths))

    widths2  = [16, 10, 10]
    headers2 = ["Enemy", "BaseSpd", "EnhSpd"]
    print("\n=== ENEMY SPEED TABLE (px/s) ===")
    print(_sep(widths2))
    print(_header(headers2, widths2))
    print(_sep(widths2))
    for ename, (_, base_spd, __, enh_spd, ___) in _ENEMY_BASE.items():
        print(_row([ename, f"{base_spd:.0f}", f"{enh_spd:.0f}"], widths2))
    print(_sep(widths2))

# ── セクション2: 武器 DPS テーブル ──────────────────────────

def print_weapon_dps() -> None:
    print("\n=== LASER DPS (1ダメージ / hit_int 秒) ===")
    widths = [8, 10, 10, 10, 10, 22]
    headers = ["Lv", "hit_int", "DPS雑魚", "DPS_boss", "charge", "cool"]
    print(_sep(widths))
    print(_header(headers, widths))
    print(_sep(widths))
    for lv, cfg in _LASER_CFG.items():
        hit_int      = cfg[7]
        boss_hit_int = cfg[8]
        charge       = cfg[5]
        cool         = cfg[6]
        dps_mob  = 1.0 / hit_int
        dps_boss = 1.0 / boss_hit_int
        row = [
            f"Lv{lv}",
            f"{hit_int:.3f}s",
            f"{dps_mob:.1f}",
            f"{dps_boss:.1f}",
            f"{charge:.2f}s",
            f"{cool:.2f}s",
        ]
        print(_row(row, widths))
    print(_sep(widths))

    print(f"\n=== HOMING DPS (弾数×ダメージ({_HOMING_DAMAGE}) / cooldown) ===")
    widths2  = [8, 10, 8, 10, 20]
    headers2 = ["Lv", "cooldown", "弾数", "DPS近似", "角度"]
    print(_sep(widths2))
    print(_header(headers2, widths2))
    print(_sep(widths2))
    for lv, (cd, angles) in _HOMING_CFG.items():
        n   = len(angles)
        dps = n * _HOMING_DAMAGE / cd
        row = [
            f"Lv{lv}",
            f"{cd:.2f}s",
            str(n),
            f"{dps:.2f}",
            str(angles),
        ]
        print(_row(row, widths2))
    print(_sep(widths2))

    print("\n=== MAIN WEAPON DPS (弾数×ダメージ / cooldown) ===")
    widths3  = [10, 6, 10, 10, 8]
    headers3 = ["Type", "弾数", "ダメージ/発", "cooldown", "DPS"]
    print(_sep(widths3))
    print(_header(headers3, widths3))
    print(_sep(widths3))
    for mtype, (n, cd, dmg) in _MAIN_CFG.items():
        dps = n * dmg / cd
        print(_row([mtype, str(n), str(dmg), f"{cd:.2f}s", f"{dps:.1f}"], widths3))
    print(_sep(widths3))

# ── セクション3: ボス想定撃破時間 ────────────────────────────

def print_boss_kill_time() -> None:
    print("\n=== BOSS CONFIG ===")
    widths = [8, 6, 12, 6]
    headers = ["Stage", "Form", "HP", "Scale"]
    print(_sep(widths))
    print(_header(headers, widths))
    print(_sep(widths))
    for sid, (img, scale, hp) in _BOSS_CONFIG.items():
        print(_row([f"S{sid}", "Form1", str(hp), f"{scale:.2f}"], widths))
        if sid in _FORM2_CONFIG:
            _, sc2, hp2 = _FORM2_CONFIG[sid]
            print(_row([f"S{sid}", "Form2", str(hp2), f"{sc2:.4f}"], widths))
    print(_sep(widths))

    # 各武器レベルでのボス撃破時間（Laser / Homing のみ。メインは省略）
    print("\n=== BOSS KILL TIME (理論値, 発射後の純粋な撃破秒数) ===")
    print("  ※ チャージ時間・クールダウンは除く。連続ヒット継続を前提。")

    lv_cols  = list(_LASER_CFG.keys())     # [1..6]
    h_cols   = list(_HOMING_CFG.keys())    # [1..7]
    col_w    = 7
    label_w  = 14

    # Laser
    print(f"\n  {'':>{label_w}}  " + "  ".join(f"L{lv:<{col_w-1}}" for lv in lv_cols))
    for sid, (_, _, hp) in _BOSS_CONFIG.items():
        forms = [("Form1", hp)]
        if sid in _FORM2_CONFIG:
            forms.append(("Form2", _FORM2_CONFIG[sid][2]))
        for fname, fhp in forms:
            label = f"S{sid} {fname}"
            times = []
            for lv in lv_cols:
                dps_boss = 1.0 / _LASER_CFG[lv][8]
                t = fhp / dps_boss
                times.append(f"{t:.1f}s".ljust(col_w))
            print(f"  {label:>{label_w}}  " + "  ".join(times))

    # Homing
    print(f"\n  {'':>{label_w}}  " + "  ".join(f"H{lv:<{col_w-1}}" for lv in h_cols))
    for sid, (_, _, hp) in _BOSS_CONFIG.items():
        forms = [("Form1", hp)]
        if sid in _FORM2_CONFIG:
            forms.append(("Form2", _FORM2_CONFIG[sid][2]))
        for fname, fhp in forms:
            label = f"S{sid} {fname}"
            times = []
            for lv in h_cols:
                cd, angles = _HOMING_CFG[lv]
                dps = len(angles) * _HOMING_DAMAGE / cd
                t   = fhp / dps
                times.append(f"{t:.1f}s".ljust(col_w))
            print(f"  {label:>{label_w}}  " + "  ".join(times))

# ── エントリポイント ────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ゲームバランス数値シート")
    parser.add_argument("--section", choices=["enemy", "weapon", "boss", "all"],
                        default="all", help="表示するセクション (default: all)")
    args = parser.parse_args()

    s = args.section
    if s in ("enemy",  "all"): print_enemy_hp()
    if s in ("weapon", "all"): print_weapon_dps()
    if s in ("boss",   "all"): print_boss_kill_time()


if __name__ == "__main__":
    main()
