"""整合性テスト (pytest)。

tools/check_consistency.py と同じロジックを pytest 化。
  pytest tests/test_consistency.py
"""
from __future__ import annotations
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


# ── 敵 ──────────────────────────────────────────────────────────────

def test_spawner_handles_all_enemy_names() -> None:
    from src.core.registries import ENEMY_NAMES
    src = (ROOT / "src" / "stages" / "spawner.py").read_text(encoding="utf-8")
    missing = [n for n in ENEMY_NAMES if n not in src]
    assert not missing, f"spawner._make_enemy に未登録: {missing}"


def test_debug_panel_handles_all_enemy_names() -> None:
    from src.core.registries import ENEMY_NAMES
    src = (ROOT / "src" / "scenes" / "game" / "debug_stage_panel.py").read_text(encoding="utf-8")
    missing = [n for n in ENEMY_NAMES if n not in src]
    assert not missing, f"debug_stage_panel._make_enemy に未登録: {missing}"


def test_game_scene_uses_registry_for_se() -> None:
    src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    assert "ENEMY_BY_NAME" in src, "game_scene._on_enemy_killed が ENEMY_BY_NAME を使っていない"


def test_balance_sheet_enemy_keys_match_registry() -> None:
    from src.core.registries import ENEMY_NAMES
    import importlib
    bs = importlib.import_module("tools.balance_sheet")
    assert set(bs._ENEMY_BASE.keys()) == set(ENEMY_NAMES), (
        f"balance_sheet._ENEMY_BASE のキーが ENEMY_NAMES と一致しない\n"
        f"  missing: {set(ENEMY_NAMES) - set(bs._ENEMY_BASE.keys())}\n"
        f"  extra:   {set(bs._ENEMY_BASE.keys()) - set(ENEMY_NAMES)}"
    )


def test_stage_json_enemy_types_in_registry() -> None:
    from src.core.registries import ENEMY_NAMES
    valid = set(ENEMY_NAMES) | {"Boss", "Terrain"}
    for p in sorted((ROOT / "data" / "stages").glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for ev in data.get("events", []):
            t = ev.get("type", "")
            assert t in valid, f"{p.name}: 未知の type '{t}'"


# ── アイテム ─────────────────────────────────────────────────────────

def test_debug_panel_handles_all_item_names() -> None:
    from src.core.registries import ITEM_NAMES
    src = (ROOT / "src" / "scenes" / "game" / "debug_stage_panel.py").read_text(encoding="utf-8")
    missing = [n for n in ITEM_NAMES if n not in src]
    assert not missing, f"debug_stage_panel._make_item に未登録: {missing}"


# ── ステージ ─────────────────────────────────────────────────────────

def test_stage_ids_match_stage_names_and_boss_config() -> None:
    from src.core.registries import stage_ids
    from src.scenes.game.config import STAGE_NAMES, BOSS_NAMES
    from src.entities.enemies.boss import _BOSS_CONFIG
    ids = set(stage_ids())
    assert ids == set(STAGE_NAMES.keys()), f"stage_ids vs STAGE_NAMES: {ids} vs {set(STAGE_NAMES.keys())}"
    assert ids == set(BOSS_NAMES.keys()),  f"stage_ids vs BOSS_NAMES: {ids} vs {set(BOSS_NAMES.keys())}"
    assert ids == set(_BOSS_CONFIG.keys()), f"stage_ids vs _BOSS_CONFIG: {ids} vs {set(_BOSS_CONFIG.keys())}"


def test_stage_json_required_fields() -> None:
    valid_formations = {"line", "v_shape", "random", "single"}
    valid_terrain_kinds = {"wall", "rock", "debris"}
    for p in sorted((ROOT / "data" / "stages").glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for i, ev in enumerate(data.get("events", [])):
            for field in ("time", "type"):
                assert field in ev, f"{p.name} events[{i}]: 必須フィールド '{field}' が欠如"
            if ev.get("type") == "Terrain":
                for field in ("y", "w", "h", "kind"):
                    assert field in ev, f"{p.name} events[{i}](Terrain): 必須フィールド '{field}' が欠如"
                assert ev["kind"] in valid_terrain_kinds, (
                    f"{p.name} events[{i}](Terrain): 未知の kind '{ev['kind']}'"
                )
            else:
                assert "count" in ev, f"{p.name} events[{i}]: 必須フィールド 'count' が欠如"
                # 'y' 指定（砲台等の固定配置）がある場合は formation 省略可
                if "y" not in ev:
                    assert "formation" in ev, f"{p.name} events[{i}]: 必須フィールド 'formation' が欠如"
                    assert ev["formation"] in valid_formations, (
                        f"{p.name} events[{i}]: 未知の formation '{ev['formation']}'"
                    )


# ── ボス ─────────────────────────────────────────────────────────────

def test_preview_boss_uses_boss_phase_configs() -> None:
    src = (ROOT / "tools" / "preview_boss.py").read_text(encoding="utf-8")
    assert "_BOSS_PHASE_CONFIGS" in src, "preview_boss._ALL_PATTERNS が boss._PHASE_CONFIGS を参照していない"


# ── 武器 ─────────────────────────────────────────────────────────────

def test_weapon_main_levels_count_matches_next_names() -> None:
    from src.entities.weapon import _MAIN_LEVELS
    from src.scenes.game.config import MAIN_NEXT_NAMES
    assert len(_MAIN_LEVELS) == len(MAIN_NEXT_NAMES), (
        f"_MAIN_LEVELS({len(_MAIN_LEVELS)}) != MAIN_NEXT_NAMES({len(MAIN_NEXT_NAMES)})"
    )


# ── ストーリー ───────────────────────────────────────────────────────

def test_story_tables_cover_all_stages() -> None:
    from src.core.registries import stage_ids
    from src.story import script
    ids = set(stage_ids())
    for name, table in (("BOSS_INTRO", script.BOSS_INTRO),
                        ("BOSS_DEFEAT", script.BOSS_DEFEAT),
                        ("STAGE_INTRO", script.STAGE_INTRO)):
        assert ids <= set(table.keys()), f"{name} に未定義のステージ: {ids - set(table.keys())}"


def test_story_speakers_are_registered() -> None:
    from src.story import script
    from src.story.speakers import SPEAKERS
    used: set[str] = set()
    for grp in (list(script.BOSS_INTRO.values()) + list(script.BOSS_MID.values())
                + list(script.BOSS_DEFEAT.values())
                + [script.BOSS_FORM3_INTRO] + list(script.FINAL_SEQ.values())):
        used.update(ln.speaker for ln in grp)
    page_groups = ([script.PROLOGUE, script.EPILOGUE, script.CREDITS, script.POSTCREDIT,
                    script.INTERLUDE_STAGE1_CLEAR, script.INTERLUDE_STAGE3_BLACKHOLE]
                   + list(script.STAGE_INTRO.values()))
    for grp in page_groups:
        used.update(pg.speaker for pg in grp)
    unknown = used - set(SPEAKERS.keys())
    assert not unknown, f"SPEAKERS に未登録の話者: {sorted(unknown)}"


def test_story_aliases_resolve_to_existing_files() -> None:
    from src.story.aliases import BGM, SE
    assets = ROOT / "assets"
    missing = [f"{a} -> {p}" for a, p in {**BGM, **SE}.items()
               if p and not (assets / p).exists()]
    assert not missing, f"aliases の実ファイルが見つからない: {missing}"



def test_boss_form3_phase_config_exists() -> None:
    from src.entities.enemies.boss import _PHASE_CONFIGS
    assert "4f3" in _PHASE_CONFIGS, "boss._PHASE_CONFIGS に '4f3'（投了王サワグチ）が未定義"


def test_stage_backgrounds_draw_all_stages() -> None:
    """全ステージのテーマ別背景が例外なく描画できる。"""
    from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
    from src.entities.background import ScrollingBackground
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    for sid in (0, 1, 2, 3, 4):
        bg = ScrollingBackground(sid)
        for f in range(3):
            bg.draw(surf, camera_x=f * 30.0)


# ── docs ─────────────────────────────────────────────────────────────

def test_design_md_autogen_blocks_are_current() -> None:
    import subprocess
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_docs.py"), "--check"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"design.md の AUTOGEN ブロックが古い:\n{result.stderr.strip()}"
    )
