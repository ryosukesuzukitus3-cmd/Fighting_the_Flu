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
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tools.dev_env import configure_headless_pygame, configure_utf8_stdio, text_integrity_issues

configure_utf8_stdio()
configure_headless_pygame()

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

def check_text_integrity() -> None:
    """UTF-8 と代表的な文字化け混入を検査する。"""
    print("\n[text]")
    issues = text_integrity_issues(ROOT)
    if issues:
        for issue in issues:
            _fail(issue)
    else:
        _ok("project text files are UTF-8 and mojibake-free")


def check_enemies() -> None:
    """敵名集合の一致"""
    print("\n[enemies]")
    from src.core.registries import ENEMY_NAMES
    from src.core.factories import enemy_factory_names

    factory_keys = enemy_factory_names()
    reg_keys = set(ENEMY_NAMES)
    if factory_keys == reg_keys:
        _ok("factories.enemy_factory_names() == ENEMY_NAMES")
    else:
        missing = reg_keys - factory_keys
        extra = factory_keys - reg_keys
        if missing:
            _fail(f"enemy factory に不足: {sorted(missing)}")
        if extra:
            _fail(f"enemy factory に余分: {sorted(extra)}")

    spawner_src = Path(ROOT, "src", "stages", "spawner.py").read_text(encoding="utf-8")
    panel_src = Path(ROOT, "src", "scenes", "game", "debug_stage_panel.py").read_text(encoding="utf-8")
    if "make_enemy(" in spawner_src:
        _ok("spawner._make_enemy は共通 factory を参照")
    else:
        _fail("spawner._make_enemy が共通 factory を参照していない")
    if "make_enemy(" in panel_src:
        _ok("debug_stage_panel は共通 enemy factory を参照")
    else:
        _fail("debug_stage_panel が共通 enemy factory を参照していない")

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

    # stage JSON の type が敵・ボス・地形エイリアスに含まれるか
    terrain_types = {
        "Terrain", "TerrainStrip", "solid", "platform", "gate", "breakable_gate",
        "weapon_gate", "turret_mount", "cave_section", "corridor",
        "AuthoredTerrain", "TerrainPath",
    }
    valid_types = set(ENEMY_NAMES) | {"Boss", "BossGate"} | terrain_types
    for p in sorted((ROOT / "data" / "stages").glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for ev in data.get("events", []) + data.get("world_events", []):
            t = ev.get("type", "")
            if t not in valid_types:
                _fail(f"{p.name}: 未知の type '{t}'")
        for section in ("initial_terrain", "terrain_layout", "boss_terrain"):
            for ev in data.get(section, []):
                t = ev.get("type", "")
                if t not in terrain_types:
                    _fail(f"{p.name} {section}: 未知の type '{t}'")
    _ok("stage JSON: 全 type が敵・ボス・地形エイリアスに含まれる")


def check_items() -> None:
    """アイテム名集合の一致"""
    print("\n[items]")
    from src.core.registries import ITEM_NAMES
    from src.core.registries import ITEM_DEFS
    from src.core.factories import item_factory_names, random_item_names

    factory_keys = item_factory_names()
    reg_keys = set(ITEM_NAMES)
    if factory_keys == reg_keys:
        _ok("factories.item_factory_names() == ITEM_NAMES")
    else:
        missing = reg_keys - factory_keys
        extra = factory_keys - reg_keys
        if missing:
            _fail(f"item factory に不足: {sorted(missing)}")
        if extra:
            _fail(f"item factory に余分: {sorted(extra)}")

    drop_names = {d.name for d in ITEM_DEFS if d.drop_weight > 0}
    random_names = random_item_names()
    if drop_names == random_names:
        _ok("random_item 対象 == ITEM_DEFS.drop_weight > 0")
    else:
        _fail(f"random_item 対象不一致: defs={sorted(drop_names)} factory={sorted(random_names)}")


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
    valid_boss_terrain_modes = {"replace", "preplaced"}
    valid_terrain_kinds = {"wall", "rock", "debris", "data_block", "fortress_block", "clot"}
    rect_terrain_types = {"Terrain", "solid", "platform", "gate", "breakable_gate", "weapon_gate", "turret_mount"}
    strip_terrain_types = {"TerrainStrip", "cave_section", "corridor"}
    authored_terrain_types = {"AuthoredTerrain", "TerrainPath"}
    from src.entities.terrain import TERRAIN_STRIP_THEMES
    valid_strip_themes = set(TERRAIN_STRIP_THEMES)

    def validate_terrain_event(label: str, ev: dict) -> None:
        if ev.get("type") in rect_terrain_types:
            for field in ("y", "w", "h"):
                if field not in ev:
                    _fail(f"{label}(Terrain): 必須フィールド '{field}' が欠如")
            if ev.get("kind", "wall") not in valid_terrain_kinds:
                _fail(f"{label}(Terrain): 未知の kind '{ev.get('kind')}'")
        elif ev.get("type") in authored_terrain_types:
            for field in ("top", "bottom"):
                if field not in ev:
                    _fail(f"{label}({ev.get('type')}): missing '{field}'")
                points = ev.get(field)
                if not isinstance(points, list) or len(points) < 2:
                    _fail(f"{label}({ev.get('type')}): '{field}' requires at least two points")
            if ev.get("theme", "fever_cave") not in valid_strip_themes:
                _fail(f"{label}({ev.get('type')}): unknown theme '{ev.get('theme')}'")
        elif ev.get("type") in strip_terrain_types:
            for field in ("length",):
                if field not in ev:
                    _fail(f"{label}(TerrainStrip): 必須フィールド '{field}' が欠如")
            if ev.get("theme", "fever_cave") not in valid_strip_themes:
                _fail(f"{label}(TerrainStrip): 未知の theme '{ev.get('theme')}'")
        else:
            _fail(f"{label}: terrain section only allows terrain aliases")

    for p in sorted((ROOT / "data" / "stages").glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("debug"):
            if "events" not in data:
                _fail(f"{p.name}: debug stage に events がない")
            continue
        if "stage_id" not in data:
            _fail(f"{p.name}: 必須フィールド 'stage_id' が欠如")
        else:
            try:
                expected_sid = int(p.stem.replace("stage", ""))
                if int(data["stage_id"]) != expected_sid:
                    _fail(f"{p.name}: stage_id がファイル名と不一致 ({data['stage_id']} != {expected_sid})")
            except ValueError:
                _fail(f"{p.name}: stage_id が整数ではない")
        if "bgm" not in data:
            _fail(f"{p.name}: 必須フィールド 'bgm' が欠如")
        if "events" not in data:
            _fail(f"{p.name}: 必須フィールド 'events' が欠如")
        if data.get("boss_terrain_mode", "replace") not in valid_boss_terrain_modes:
            _fail(f"{p.name}: unknown boss_terrain_mode '{data.get('boss_terrain_mode')}'")
        for i, ev in enumerate(data.get("events", [])):
            for field in ("time", "type"):
                if field not in ev:
                    _fail(f"{p.name} events[{i}]: 必須フィールド '{field}' が欠如")
            if "surface" in ev and ev.get("surface") not in {"top", "bottom"}:
                _fail(f"{p.name} events[{i}]: invalid surface '{ev.get('surface')}'")
            if ev.get("type") == "Terrain":
                # 地形イベント: y/w/h/kind を要求（count/formation は不要）
                for field in ("y", "w", "h", "kind"):
                    if field not in ev:
                        _fail(f"{p.name} events[{i}](Terrain): 必須フィールド '{field}' が欠如")
                if ev.get("kind") not in valid_terrain_kinds:
                    _fail(f"{p.name} events[{i}](Terrain): 未知の kind '{ev.get('kind')}'")
            elif ev.get("type") in authored_terrain_types:
                for field in ("theme", "top", "bottom"):
                    if field not in ev:
                        _fail(f"{p.name} events[{i}]({ev.get('type')}): missing '{field}'")
                if ev.get("theme") not in valid_strip_themes:
                    _fail(f"{p.name} events[{i}]({ev.get('type')}): unknown theme '{ev.get('theme')}'")
            elif ev.get("type") == "TerrainStrip":
                for field in ("theme", "length"):
                    if field not in ev:
                        _fail(f"{p.name} events[{i}](TerrainStrip): 必須フィールド '{field}' が欠如")
                if ev.get("theme") not in valid_strip_themes:
                    _fail(f"{p.name} events[{i}](TerrainStrip): 未知の theme '{ev.get('theme')}'")
            else:
                if "count" not in ev:
                    _fail(f"{p.name} events[{i}]: 必須フィールド 'count' が欠如")
                # 'y' 指定（砲台等の固定配置）がある場合は formation 省略可
                if "y" not in ev and "surface" not in ev:
                    if "formation" not in ev:
                        _fail(f"{p.name} events[{i}]: 必須フィールド 'formation' が欠如")
                    elif ev.get("formation") not in valid_formations:
                        _fail(f"{p.name} events[{i}]: 未知の formation '{ev.get('formation')}'")
        for i, ev in enumerate(data.get("world_events", [])):
            if "type" not in ev:
                _fail(f"{p.name} world_events[{i}]: missing 'type'")
            if "x" not in ev and "world_x" not in ev and "trigger_x" not in ev:
                _fail(f"{p.name} world_events[{i}]: missing 'x' / 'world_x' / 'trigger_x'")
            if "surface" in ev and ev.get("surface") not in {"top", "bottom"}:
                _fail(f"{p.name} world_events[{i}]: invalid surface '{ev.get('surface')}'")
        for section in ("initial_terrain", "terrain_layout", "boss_terrain"):
            for i, ev in enumerate(data.get(section, [])):
                validate_terrain_event(f"{p.name} {section}[{i}]", ev)
        if not data.get("boss_terrain"):
            _fail(f"{p.name}: boss_terrain is empty")
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

    # 全ステージに intro/defeat ボスセリフが存在するか
    for name, table in (("BOSS_INTRO", script.BOSS_INTRO),
                        ("BOSS_DEFEAT", script.BOSS_DEFEAT)):
        missing = ids - set(table.keys())
        if missing:
            _fail(f"{name} に未定義のステージ: {sorted(missing)}")
        else:
            _ok(f"{name}: 全ステージ {sorted(ids)} を網羅")

    # 物語タイムライン: 各ステージに「直前ビート」が存在するか
    intro_missing = sorted(sid for sid in ids if not script.intro_beats(sid))
    if intro_missing:
        _fail(f"STORY_BEATS に直前ビートが無いステージ: {intro_missing}")
    else:
        _ok(f"STORY_BEATS: 全ステージ {sorted(ids)} に直前ビートあり")

    # script が参照する全 speaker が SPEAKERS に登録されているか
    used: set[str] = set()
    line_groups = list(script.BOSS_INTRO.values()) + list(script.BOSS_MID.values()) \
                  + list(script.BOSS_DEFEAT.values()) \
                  + [script.BOSS_FORM3_INTRO] + list(script.FINAL_SEQ.values())
    for grp in line_groups:
        for ln in grp:
            used.add(ln.speaker)
    # 全画面会話の話者は STORY_BEATS のページから収集（プロローグ/ステージ間
    # 遷移/エピローグ/エンドロールを網羅）。
    for beat in script.STORY_BEATS:
        for pg in beat.pages:
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
    """ガイド類（design.md / CLAUDE.md / AGENTS.md）の AUTOGEN ブロックが最新か（gen_docs.py --check）"""
    print("\n[docs]")
    import subprocess
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_docs.py"), "--check"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        _ok("AUTOGEN ブロックは最新（design.md / CLAUDE.md / AGENTS.md）")
    else:
        _fail(f"AUTOGEN ブロックが古い:\n{result.stderr.strip()}")

    design = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    stale_item_terms = (
        "LaserItem", "HomingItem", "ShieldItem", "shield.py",
        "ScoreItem", "score_item.py",
        "ExtraLifeItem", "extra_life.py", "1UP",
    )
    stale = [term for term in stale_item_terms if term in design]
    if stale:
        _fail(f"design.md に削除済みアイテム記述が残っている: {stale}")
    else:
        _ok("design.md 手書きアイテム記述は現行構成に一致")

    tools_doc = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    debug_src = (ROOT / "src" / "scenes" / "game" / "debug_mixin.py").read_text(encoding="utf-8")
    if "ウェポンアイテムをドロップ" in debug_src and "ウェポンアイテムを自機前方にドロップ" in tools_doc:
        _ok("docs/tools.md: F2 デバッグ説明は実装と一致")
    else:
        _fail("docs/tools.md: F2 デバッグ説明が実装と一致していない")


# ── エントリーポイント ─────────────────────────────────────────────

_ALL_CHECKS = {
    "text":          check_text_integrity,
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
