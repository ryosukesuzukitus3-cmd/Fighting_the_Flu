"""整合性チェッカ。

コード間・ドキュメント間の反映漏れを機械的に検出する。
全検査パスで exit 0、1件でも失敗で exit 1。

使い方:
  python tools/check_consistency.py
  python tools/check_consistency.py --section enemies  # 特定セクションのみ
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()

_errors: list[str] = []
_passed: list[str] = []


def _fail(msg: str) -> None:
    _errors.append(msg)
    print(f"  FAIL  {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    _passed.append(msg)
    print(f"  OK    {msg}")


# ── 検査関数 ────────────────────────────────────────────────────────

def check_enemies() -> None:
    """敵名集合の一致"""
    print("\n[enemies]")
    from src.core.registries import ENEMY_NAMES, ENEMY_BY_NAME

    # spawner._make_enemy が全 ENEMY_NAMES を処理できるか
    from src.stages.spawner import EnemySpawner
    src = Path(ROOT, "src", "stages", "spawner.py").read_text(encoding="utf-8")
    for name in ENEMY_NAMES:
        if name not in src:
            _fail(f"spawner._make_enemy に '{name}' が未登録")
        else:
            _ok(f"spawner._make_enemy: {name}")

    # debug_stage_panel._make_enemy が全 ENEMY_NAMES を処理できるか
    panel_src = Path(ROOT, "src", "scenes", "game", "debug_stage_panel.py").read_text(encoding="utf-8")
    for name in ENEMY_NAMES:
        if name not in panel_src:
            _fail(f"debug_stage_panel._make_enemy に '{name}' が未登録")
        else:
            _ok(f"debug_stage_panel._make_enemy: {name}")

    # _SE_MAP キー → ENEMY_NAMES に含まれるか（旧ハードコードは削除済みなので確認のみ）
    # game_scene.py を読んで ENEMY_BY_NAME を使っているか確認
    gs_src = Path(ROOT, "src", "scenes", "game_scene.py").read_text(encoding="utf-8")
    if "ENEMY_BY_NAME" in gs_src:
        _ok("game_scene._on_enemy_killed: ENEMY_BY_NAME 参照OK")
    else:
        _fail("game_scene._on_enemy_killed が ENEMY_BY_NAME を使っていない")

    # balance_sheet._ENEMY_BASE のキーが ENEMY_NAMES と一致するか
    from tools import balance_sheet  # noqa: F401（ただしモジュール取得に使う）
    import importlib
    bs = importlib.import_module("tools.balance_sheet")
    bs_keys = set(bs._ENEMY_BASE.keys())
    reg_keys = set(ENEMY_NAMES)
    if bs_keys == reg_keys:
        _ok("balance_sheet._ENEMY_BASE キー == ENEMY_NAMES")
    else:
        missing = reg_keys - bs_keys
        extra   = bs_keys - reg_keys
        if missing:
            _fail(f"balance_sheet._ENEMY_BASE に不足: {sorted(missing)}")
        if extra:
            _fail(f"balance_sheet._ENEMY_BASE に余分: {sorted(extra)}")

    # stage JSON の type が ENEMY_NAMES ∪ {'Boss','Terrain'} に含まれるか
    valid_types = set(ENEMY_NAMES) | {"Boss", "Terrain"}
    for p in sorted((ROOT / "data" / "stages").glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for ev in data.get("events", []):
            t = ev.get("type", "")
            if t not in valid_types:
                _fail(f"{p.name}: 未知の type '{t}'")
    _ok("stage JSON: 全 type が ENEMY_NAMES ∪ {{'Boss','Terrain'}} に含まれる")


def check_items() -> None:
    """アイテム名集合の一致"""
    print("\n[items]")
    from src.core.registries import ITEM_NAMES

    panel_src = Path(ROOT, "src", "scenes", "game", "debug_stage_panel.py").read_text(encoding="utf-8")
    for name in ITEM_NAMES:
        if name not in panel_src:
            _fail(f"debug_stage_panel._make_item に '{name}' が未登録")
        else:
            _ok(f"debug_stage_panel._make_item: {name}")


def check_stages() -> None:
    """ステージ整合性"""
    print("\n[stages]")
    from src.core.registries import stage_ids
    from src.scenes.game.config import STAGE_NAMES, BOSS_NAMES
    from src.entities.enemies.boss import _BOSS_CONFIG

    ids = stage_ids()
    sn_keys  = set(STAGE_NAMES.keys())
    bn_keys  = set(BOSS_NAMES.keys())
    bc_keys  = set(_BOSS_CONFIG.keys())

    if set(ids) == sn_keys:
        _ok(f"stage_ids() == STAGE_NAMES.keys(): {ids}")
    else:
        _fail(f"stage_ids()={sorted(ids)} vs STAGE_NAMES.keys()={sorted(sn_keys)}")

    if set(ids) == bn_keys:
        _ok(f"stage_ids() == BOSS_NAMES.keys()")
    else:
        _fail(f"stage_ids()={sorted(ids)} vs BOSS_NAMES.keys()={sorted(bn_keys)}")

    if set(ids) == bc_keys:
        _ok(f"stage_ids() == _BOSS_CONFIG.keys()")
    else:
        _fail(f"stage_ids()={sorted(ids)} vs _BOSS_CONFIG.keys()={sorted(bc_keys)}")

    # stage JSON 必須フィールド検証
    valid_formations = {"line", "v_shape", "random", "single"}
    valid_terrain_kinds = {"wall", "rock", "debris"}
    for p in sorted((ROOT / "data" / "stages").glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for i, ev in enumerate(data.get("events", [])):
            for field in ("time", "type"):
                if field not in ev:
                    _fail(f"{p.name} events[{i}]: 必須フィールド '{field}' が欠如")
            if ev.get("type") == "Terrain":
                # 地形イベント: y/w/h/kind を要求（count/formation は不要）
                for field in ("y", "w", "h", "kind"):
                    if field not in ev:
                        _fail(f"{p.name} events[{i}](Terrain): 必須フィールド '{field}' が欠如")
                if ev.get("kind") not in valid_terrain_kinds:
                    _fail(f"{p.name} events[{i}](Terrain): 未知の kind '{ev.get('kind')}'")
            else:
                if "count" not in ev:
                    _fail(f"{p.name} events[{i}]: 必須フィールド 'count' が欠如")
                # 'y' 指定（砲台等の固定配置）がある場合は formation 省略可
                if "y" not in ev:
                    if "formation" not in ev:
                        _fail(f"{p.name} events[{i}]: 必須フィールド 'formation' が欠如")
                    elif ev.get("formation") not in valid_formations:
                        _fail(f"{p.name} events[{i}]: 未知の formation '{ev.get('formation')}'")
    _ok("stage JSON: 全イベントの必須フィールド・formation OK")


def check_boss_patterns() -> None:
    """ボスパターン: preview_boss が boss.py を参照しているか"""
    print("\n[boss_patterns]")
    pb_src = Path(ROOT, "tools", "preview_boss.py").read_text(encoding="utf-8")
    if "_BOSS_PHASE_CONFIGS" in pb_src and "boss" in pb_src:
        _ok("preview_boss._ALL_PATTERNS は boss._PHASE_CONFIGS から動的生成")
    else:
        _fail("preview_boss._ALL_PATTERNS が boss._PHASE_CONFIGS を参照していない")


def check_weapon() -> None:
    """武器段数整合"""
    print("\n[weapon]")
    from src.entities.weapon import _MAIN_LEVELS
    from src.scenes.game.config import MAIN_NEXT_NAMES

    if len(_MAIN_LEVELS) == len(MAIN_NEXT_NAMES):
        _ok(f"len(_MAIN_LEVELS)==len(MAIN_NEXT_NAMES)=={len(_MAIN_LEVELS)}")
    else:
        _fail(f"_MAIN_LEVELS({len(_MAIN_LEVELS)}) != MAIN_NEXT_NAMES({len(MAIN_NEXT_NAMES)})")


def check_story() -> None:
    """ストーリーデータ（src/story）の整合性"""
    print("\n[story]")
    from src.core.registries import stage_ids
    from src.story import script
    from src.story.speakers import SPEAKERS
    from src.story.aliases import BGM, SE

    ids = set(stage_ids())

    # 全ステージに intro/defeat ボスセリフ・ステージ前セリフが存在するか
    for name, table in (("BOSS_INTRO", script.BOSS_INTRO),
                        ("BOSS_DEFEAT", script.BOSS_DEFEAT),
                        ("STAGE_INTRO", script.STAGE_INTRO)):
        missing = ids - set(table.keys())
        if missing:
            _fail(f"{name} に未定義のステージ: {sorted(missing)}")
        else:
            _ok(f"{name}: 全ステージ {sorted(ids)} を網羅")

    # script が参照する全 speaker が SPEAKERS に登録されているか
    used: set[str] = set()
    line_groups = list(script.BOSS_INTRO.values()) + list(script.BOSS_MID.values()) \
                  + list(script.BOSS_DEFEAT.values()) \
                  + [script.BOSS_FORM3_INTRO] + list(script.FINAL_SEQ.values())
    for grp in line_groups:
        for ln in grp:
            used.add(ln.speaker)
    page_groups = ([script.PROLOGUE, script.EPILOGUE, script.CREDITS, script.POSTCREDIT,
                    script.INTERLUDE_STAGE1_CLEAR, script.INTERLUDE_STAGE3_BLACKHOLE]
                   + list(script.STAGE_INTRO.values()))
    for grp in page_groups:
        for pg in grp:
            used.add(pg.speaker)
    unknown = used - set(SPEAKERS.keys())
    if unknown:
        _fail(f"SPEAKERS に未登録の話者: {sorted(unknown)}")
    else:
        _ok(f"script の全話者 ({len(used)}種) が SPEAKERS に登録済み")

    # BGM/SE エイリアスの実ファイル存在チェック（None はダミー未用意として許容）
    assets = ROOT / "assets"
    missing_files: list[str] = []
    for alias, path in {**BGM, **SE}.items():
        if path and not (assets / path).exists():
            missing_files.append(f"{alias} -> {path}")
    if missing_files:
        _fail(f"aliases の実ファイルが見つからない: {missing_files}")
    else:
        _ok("aliases の BGM/SE 実ファイルは全て存在（None はダミー未用意）")

    # Form3 攻撃パターンが _PHASE_CONFIGS に存在するか
    from src.entities.enemies.boss import _PHASE_CONFIGS
    if "4f3" in _PHASE_CONFIGS:
        _ok("boss._PHASE_CONFIGS に '4f3'（投了王サワグチ）が存在")
    else:
        _fail("boss._PHASE_CONFIGS に '4f3' が未定義")


def check_docs() -> None:
    """design.md の AUTOGEN ブロックが最新か（gen_docs.py --check）"""
    print("\n[docs]")
    import subprocess
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_docs.py"), "--check"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        _ok("design.md AUTOGEN ブロックは最新")
    else:
        _fail(f"design.md AUTOGEN ブロックが古い:\n{result.stderr.strip()}")


# ── エントリーポイント ─────────────────────────────────────────────

_ALL_CHECKS = {
    "enemies":       check_enemies,
    "items":         check_items,
    "stages":        check_stages,
    "boss_patterns": check_boss_patterns,
    "weapon":        check_weapon,
    "story":         check_story,
    "docs":          check_docs,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="コード間整合性チェック")
    parser.add_argument("--section", choices=list(_ALL_CHECKS), default=None,
                        help="特定セクションのみ実行")
    args = parser.parse_args()

    targets = {args.section: _ALL_CHECKS[args.section]} if args.section else _ALL_CHECKS
    for fn in targets.values():
        fn()

    print(f"\n{'='*50}")
    print(f"  passed: {len(_passed)}  failed: {len(_errors)}")
    if _errors:
        print("\nFAILED:", file=sys.stderr)
        for e in _errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print("  all consistent [OK]")


if __name__ == "__main__":
    main()
