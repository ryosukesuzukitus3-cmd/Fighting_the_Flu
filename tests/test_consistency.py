"""整合性テスト (pytest)。

tools/check_consistency.py と同じロジックを pytest 化。
  pytest tests/test_consistency.py
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()


# ── 敵 ──────────────────────────────────────────────────────────────

def test_enemy_factory_handles_all_enemy_names() -> None:
    from src.core.registries import ENEMY_NAMES
    from src.core.factories import enemy_factory_names
    assert enemy_factory_names() == set(ENEMY_NAMES)


def test_spawner_and_debug_panel_use_enemy_factory() -> None:
    spawner_src = (ROOT / "src" / "stages" / "spawner.py").read_text(encoding="utf-8")
    panel_src = (ROOT / "src" / "scenes" / "game" / "debug_stage_panel.py").read_text(encoding="utf-8")
    assert "make_enemy(" in spawner_src
    assert "make_enemy(" in panel_src


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
    terrain_types = {
        "Terrain", "TerrainStrip", "TerrainPieces", "solid", "platform", "gate", "breakable_gate",
        "weapon_gate", "turret_mount", "cave_section", "corridor",
        "AuthoredTerrain", "TerrainPath",
    }
    valid = set(ENEMY_NAMES) | {"Boss", "BossGate"} | terrain_types
    for p in sorted((ROOT / "data" / "stages").glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for ev in data.get("events", []) + data.get("world_events", []):
            t = ev.get("type", "")
            assert t in valid, f"{p.name}: 未知の type '{t}'"
        for section in ("initial_terrain", "terrain_layout", "boss_terrain"):
            for ev in data.get(section, []):
                t = ev.get("type", "")
                assert t in terrain_types, (
                    f"{p.name} {section}: 未知の type '{t}'"
                )


# ── アイテム ─────────────────────────────────────────────────────────

def test_debug_panel_handles_all_item_names() -> None:
    from src.core.registries import ITEM_NAMES
    from src.core.factories import item_factory_names
    assert item_factory_names() == set(ITEM_NAMES)


def test_random_item_pool_matches_item_drop_weights() -> None:
    from src.core.registries import ITEM_DEFS
    from src.core.factories import random_item_names
    weights = {d.name: d.drop_weight for d in ITEM_DEFS}

    assert random_item_names() == {d.name for d in ITEM_DEFS if d.drop_weight > 0}
    assert weights["WeaponItem"] == 0
    assert random_item_names() == {"HealItem"}


def test_extra_life_item_is_retired() -> None:
    from src.core.registries import ITEM_NAMES
    from src.core.factories import item_factory_names, random_item_names

    assert "ExtraLifeItem" not in ITEM_NAMES
    assert "ExtraLifeItem" not in item_factory_names()
    assert "ExtraLifeItem" not in random_item_names()
    assert not (ROOT / "src" / "entities" / "items" / "extra_life.py").exists()
    game_src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    assert "extra_life" not in game_src


def test_item_pickup_sounds_are_split_by_item_type() -> None:
    from src.story.aliases import SE

    assert SE["SE_ITEM_WEAPON"] == "music/se/item_weapon_pickup.wav"
    assert SE["SE_ITEM_HEAL"] == "music/se/item_heal_pickup.wav"
    assert SE["SE_HEAL"] == SE["SE_ITEM_HEAL"]
    game_src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    post_boss_src = (ROOT / "src" / "scenes" / "game" / "post_boss_mixin.py").read_text(encoding="utf-8")
    assert "def _play_item_pickup_sound" in game_src
    assert "_play_item_pickup_sound(item)" in post_boss_src


def test_billy_reward_matches_design_doc() -> None:
    game_src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    design = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")

    assert "WeaponItem×1 + HealItem×4" in design
    assert "if etype == \"EnemyBilly\"" in game_src
    assert "self._add_weapon_drop(" in game_src
    assert "for _ in range(4):" in game_src
    assert "for _ in range(8):" not in game_src


# ── ステージ ─────────────────────────────────────────────────────────

def test_weapon_items_are_fixed_rewards_not_random_drops() -> None:
    game_src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    spawner_src = (ROOT / "src" / "stages" / "spawner.py").read_text(encoding="utf-8")
    terrain_src = (ROOT / "src" / "entities" / "terrain.py").read_text(encoding="utf-8")

    assert "def _add_weapon_drop" in game_src
    assert "def _add_fixed_item_drop" in game_src
    assert "def _add_random_item_drop" in game_src
    assert "self._weapon_drops_spawned" not in game_src
    assert "weapon_drop_limit" not in game_src
    assert "setattr(enemy, \"fixed_drop\"" in spawner_src
    assert "fixed_drop: str | None = None" in terrain_src
    assert "\"weapon_gate\"" in spawner_src
    assert "def _draw_reward_core" in terrain_src


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
    valid_boss_terrain_modes = {"replace", "preplaced"}
    valid_terrain_kinds = {"wall", "rock", "debris", "data_block", "fortress_block", "clot"}
    valid_surface_anchors = {"floor", "ceiling"}
    rect_terrain_types = {"Terrain", "solid", "platform", "gate", "breakable_gate", "weapon_gate", "turret_mount"}
    strip_terrain_types = {"TerrainStrip", "cave_section", "corridor"}
    authored_terrain_types = {"AuthoredTerrain", "TerrainPath"}
    piece_terrain_types = {"TerrainPieces"}
    from src.core.registries import ITEM_NAMES
    from src.core.terrain_composer import (
        TERRAIN_COMPOSER_RENDERERS,
        is_terrain_composer_renderer,
        load_composer_catalog,
        resolve_composer_paths,
        terrain_material_catalog_for_kind,
    )
    from src.entities.terrain import TERRAIN_STRIP_THEMES
    valid_strip_themes = set(TERRAIN_STRIP_THEMES)

    def assert_composer_catalog(section: str, i: int, ev: dict, *, required: bool = False):
        renderer = ev.get("renderer")
        if renderer is None:
            assert not required, f"{section}[{i}]: missing terrain composer renderer"
            return None
        assert is_terrain_composer_renderer(renderer), (
            f"{section}[{i}]: unknown terrain composer renderer '{renderer}'; "
            f"expected one of {sorted(TERRAIN_COMPOSER_RENDERERS)}"
        )
        try:
            rects_path, _mask_dir = resolve_composer_paths(ev)
            return load_composer_catalog(rects_path)
        except (OSError, TypeError, ValueError) as exc:
            raise AssertionError(f"{section}[{i}]: invalid terrain composer catalog: {exc}") from exc

    def assert_material_catalog(section: str, i: int, ev: dict) -> None:
        if "material_role" not in ev and "material_asset" not in ev:
            return
        material = terrain_material_catalog_for_kind(ev.get("kind", "wall"))
        assert material is not None, (
            f"{section}[{i}](Terrain): kind '{ev.get('kind', 'wall')}' has no material catalog"
        )
        try:
            catalog = load_composer_catalog(material.rects_path)
        except (OSError, TypeError, ValueError) as exc:
            raise AssertionError(f"{section}[{i}](Terrain): invalid material catalog: {exc}") from exc
        if "material_role" in ev:
            assert ev["material_role"] in catalog.roles, (
                f"{section}[{i}](Terrain): invalid material_role '{ev['material_role']}'"
            )
        if "material_asset" in ev:
            assert ev["material_asset"] in catalog.assets, (
                f"{section}[{i}](Terrain): invalid material_asset '{ev['material_asset']}'"
            )

    def assert_terrain_event(section: str, i: int, ev: dict) -> None:
        assert ev.get("type") in rect_terrain_types | strip_terrain_types | authored_terrain_types | piece_terrain_types, (
            f"{section}[{i}]: terrain section only allows terrain aliases"
        )
        if "fixed_drop" in ev:
            assert ev["fixed_drop"] in ITEM_NAMES, (
                f"{section}[{i}]: unknown fixed_drop '{ev['fixed_drop']}'"
            )
        if ev.get("type") in rect_terrain_types:
            for field in ("y", "w", "h"):
                assert field in ev, f"{section}[{i}](Terrain): missing '{field}'"
            assert ev.get("kind", "wall") in valid_terrain_kinds, (
                f"{section}[{i}](Terrain): unknown kind '{ev.get('kind', 'wall')}'"
            )
            if "surface_anchor" in ev:
                assert ev["surface_anchor"] in valid_surface_anchors, (
                    f"{section}[{i}](Terrain): invalid surface_anchor '{ev['surface_anchor']}'"
                )
            assert_material_catalog(section, i, ev)
        elif ev.get("type") in piece_terrain_types:
            assert isinstance(ev.get("pieces"), list), f"{section}[{i}](TerrainPieces): missing 'pieces'"
            catalog = assert_composer_catalog(section, i, ev, required=True)
            valid_collisions = {"auto", "none", "surface", "rect"}
            for piece_index, piece in enumerate(ev.get("pieces", [])):
                assert isinstance(piece, dict), (
                    f"{section}[{i}](TerrainPieces).pieces[{piece_index}]: must be an object"
                )
                assert catalog is not None and piece.get("asset") in catalog.assets, (
                    f"{section}[{i}](TerrainPieces).pieces[{piece_index}]: unknown asset '{piece.get('asset')}'"
                )
                if "role" in piece:
                    assert piece["role"] in catalog.roles, (
                        f"{section}[{i}](TerrainPieces).pieces[{piece_index}]: unknown role '{piece['role']}'"
                    )
                assert "x" in piece and "y" in piece, (
                    f"{section}[{i}](TerrainPieces).pieces[{piece_index}]: missing x/y"
                )
                assert piece.get("collision", "auto") in valid_collisions, (
                    f"{section}[{i}](TerrainPieces).pieces[{piece_index}]: invalid collision"
                )
        else:
            required = ("top", "bottom") if ev.get("type") in authored_terrain_types else ("length",)
            for field in required:
                assert field in ev, f"{section}[{i}]({ev.get('type')}): missing '{field}'"
            assert ev.get("theme", "fever_cave") in valid_strip_themes, (
                f"{section}[{i}]({ev.get('type')}): unknown theme '{ev.get('theme', 'fever_cave')}'"
            )
            if "renderer" in ev:
                assert_composer_catalog(section, i, ev)
            if ev.get("type") in authored_terrain_types:
                for boundary in ("top", "bottom"):
                    points = ev.get(boundary)
                    assert isinstance(points, list) and len(points) >= 2, (
                        f"{section}[{i}]({ev.get('type')}): '{boundary}' requires at least two points"
                    )

    for p in sorted((ROOT / "data" / "stages").glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("debug"):
            assert "events" in data, f"{p.name}: debug stage に events がない"
            continue
        assert "stage_id" in data, f"{p.name}: 必須フィールド 'stage_id' が欠如"
        assert int(data["stage_id"]) == int(p.stem.replace("stage", "")), (
            f"{p.name}: stage_id がファイル名と不一致"
        )
        assert "bgm" in data, f"{p.name}: 必須フィールド 'bgm' が欠如"
        assert "events" in data, f"{p.name}: 必須フィールド 'events' が欠如"
        assert data.get("boss_terrain_mode", "replace") in valid_boss_terrain_modes, (
            f"{p.name}: unknown boss_terrain_mode '{data.get('boss_terrain_mode')}'"
        )
        for i, ev in enumerate(data.get("events", [])):
            if "fixed_drop" in ev:
                assert ev["fixed_drop"] in ITEM_NAMES, (
                    f"{p.name} events[{i}]: unknown fixed_drop '{ev['fixed_drop']}'"
                )
            for field in ("time", "type"):
                assert field in ev, f"{p.name} events[{i}]: 必須フィールド '{field}' が欠如"
            if "surface" in ev:
                assert ev["surface"] in {"top", "bottom"}, (
                    f"{p.name} events[{i}]: invalid surface '{ev['surface']}'"
                )
            if ev.get("type") in rect_terrain_types | strip_terrain_types | authored_terrain_types | piece_terrain_types:
                assert_terrain_event(f"{p.name} events", i, ev)
                if ev.get("type") in rect_terrain_types:
                    assert "kind" in ev, f"{p.name} events[{i}](Terrain): missing 'kind'"
            else:
                assert "count" in ev, f"{p.name} events[{i}]: 必須フィールド 'count' が欠如"
                # 'y' 指定（砲台等の固定配置）がある場合は formation 省略可
                if "y" not in ev and "surface" not in ev:
                    assert "formation" in ev, f"{p.name} events[{i}]: 必須フィールド 'formation' が欠如"
                    assert ev["formation"] in valid_formations, (
                        f"{p.name} events[{i}]: 未知の formation '{ev['formation']}'"
                    )
        for i, ev in enumerate(data.get("world_events", [])):
            if "fixed_drop" in ev:
                assert ev["fixed_drop"] in ITEM_NAMES, (
                    f"{p.name} world_events[{i}]: unknown fixed_drop '{ev['fixed_drop']}'"
                )
            assert "type" in ev, f"{p.name} world_events[{i}]: missing 'type'"
            assert ("x" in ev or "world_x" in ev or "trigger_x" in ev), (
                f"{p.name} world_events[{i}]: missing 'x' / 'world_x' / 'trigger_x'"
            )
            if "surface" in ev:
                assert ev["surface"] in {"top", "bottom"}, (
                    f"{p.name} world_events[{i}]: invalid surface '{ev['surface']}'"
                )
            if ev.get("type") in rect_terrain_types | strip_terrain_types | authored_terrain_types | piece_terrain_types:
                assert_terrain_event(f"{p.name} world_events", i, ev)
        for section in ("initial_terrain", "terrain_layout", "boss_terrain"):
            for i, ev in enumerate(data.get(section, [])):
                assert_terrain_event(f"{p.name} {section}", i, ev)


# ── ボス ─────────────────────────────────────────────────────────────

def test_terrain_composer_renderer_aliases_are_supported() -> None:
    from src.core.terrain_composer import (
        TERRAIN_COMPOSER_RENDERERS,
        is_terrain_composer_renderer,
        resolve_composer_paths,
    )

    assert TERRAIN_COMPOSER_RENDERERS == frozenset({"terrain_composer", "stage3_composer"})
    assert is_terrain_composer_renderer("terrain_composer")
    assert is_terrain_composer_renderer("stage3_composer")
    assert not is_terrain_composer_renderer("unknown_composer")
    assert not is_terrain_composer_renderer(None)
    with pytest.raises(ValueError, match="requires composer_rects"):
        resolve_composer_paths({"renderer": "terrain_composer"})
    legacy_rects, legacy_masks = resolve_composer_paths({"renderer": "stage3_composer"})
    assert legacy_rects == (ROOT / "tools" / "stage3_terrain_rects.json").resolve()
    assert legacy_masks == (ROOT / "tools" / "stage3_terrain_alpha_masks").resolve()


def test_terrain_composer_catalog_follows_event_rects() -> None:
    from src.core.terrain_composer import load_composer_catalog, resolve_composer_paths

    stage2 = json.loads((ROOT / "data" / "stages" / "stage2.json").read_text(encoding="utf-8"))
    stage3 = json.loads((ROOT / "data" / "stages" / "stage3.json").read_text(encoding="utf-8"))
    stage2_rects, _stage2_masks = resolve_composer_paths(stage2["terrain_layout"][0])
    stage3_rects, _stage3_masks = resolve_composer_paths(stage3["terrain_layout"][0])
    stage2_catalog = load_composer_catalog(stage2_rects)
    stage3_catalog = load_composer_catalog(stage3_rects)

    assert stage2_rects == (ROOT / "tools" / "stage2_terrain_rects.json").resolve()
    assert stage3_rects == (ROOT / "tools" / "stage3_terrain_rects.json").resolve()
    assert "block_square:11" in stage2_catalog.assets
    assert "block_square:11" not in stage3_catalog.assets


def test_terrain_composer_catalog_rejects_unknown_path_and_asset(tmp_path) -> None:
    from src.core.terrain_composer import load_composer_catalog

    with pytest.raises((OSError, ValueError)):
        load_composer_catalog(tmp_path / "missing_terrain_rects.json")

    stage2_catalog = load_composer_catalog(ROOT / "tools" / "stage2_terrain_rects.json")
    assert "unknown_group:1" not in stage2_catalog.assets


def test_stage_terrain_profile_resolution_rejects_unknown_and_conflicting_stage(tmp_path) -> None:
    from tools.stage_terrain_profiles import resolve_stage_terrain_profile

    stage4_path = tmp_path / "stage4.json"
    stage4_path.write_text('{"stage_id": 4}', encoding="utf-8")
    with pytest.raises(ValueError, match="no terrain tooling profile"):
        resolve_stage_terrain_profile(stage_json=stage4_path)

    stage3_path = ROOT / "data" / "stages" / "stage3.json"
    with pytest.raises(ValueError, match="conflicts"):
        resolve_stage_terrain_profile(stage_id=2, stage_json=stage3_path)


def test_stage1_terrain_profile_and_catalog_use_dedicated_assets() -> None:
    from src.core.constants import SCREEN_WIDTH
    from src.core.terrain_composer import load_composer_catalog
    from tools.stage_designer import StageDesigner
    from tools.stage_terrain_profiles import STAGE_TERRAIN_PROFILES, resolve_stage_terrain_profile

    profile = STAGE_TERRAIN_PROFILES[1]
    layout = json.loads(profile.stage_json.read_text(encoding="utf-8"))["terrain_layout"][0]
    catalog = load_composer_catalog(profile.rects)
    required_roles = {
        "floor_surface",
        "ceiling_surface",
        "body_fill",
        "fixed_floor_block",
        "fixed_ceiling_block",
        "turret_mount",
        "breakable_block",
    }

    assert resolve_stage_terrain_profile(stage_id=1) is profile
    assert profile.stage_json == ROOT / "data" / "stages" / "stage1.json"
    assert profile.rects == ROOT / "tools" / "stage1_terrain_rects.json"
    assert profile.mask_dir == ROOT / "tools" / "stage1_terrain_alpha_masks"
    assert profile.background == ROOT / "assets" / "graphic" / "stage1_fever_corridor_bg.png"
    assert profile.terrain_kind == "clot"
    assert profile.fallback_rects is None
    assert profile.fallback_mask_dir is None
    assert profile.preview_camera_xs[0] == 0
    assert tuple(sorted(set(profile.preview_camera_xs))) == profile.preview_camera_xs
    assert profile.preview_camera_xs[-1] <= layout["length"] - SCREEN_WIDTH
    assert ROOT / layout["composer_rects"] == profile.rects
    assert ROOT / layout["composer_mask_dir"] == profile.mask_dir
    assert required_roles <= catalog.roles
    assert catalog.assets

    designer = StageDesigner.__new__(StageDesigner)
    designer.profile = profile
    designer.rects_path = profile.rects
    designer.mask_dir = profile.mask_dir
    designer._composer_piece_cache_key = None
    designer._composer_piece_cache = None
    palette = designer._composer_pieces()
    palette_assets = {
        role: {f"{piece.group}:{piece.index + 1}" for piece in pieces}
        for role, pieces in palette.items()
    }
    assert designer._piece_roles(palette)[:3] == ["floor_surface", "ceiling_surface", "body_fill"]
    assert all(designer._piece_palette_options(role, palette) for role in required_roles)
    palette_asset_ids = {asset for assets in palette_assets.values() for asset in assets}
    for piece in layout["pieces"]:
        assert piece["role"] in catalog.roles
        assert piece["asset"] in catalog.assets
        # Stage1's author may deliberately use a clot block in a different
        # visual role; the asset must stay selectable, but need not belong to
        # the role it was assigned in the layout.
        assert piece["asset"] in palette_asset_ids


def test_stage_composer_report_rejects_custom_stage_json(tmp_path) -> None:
    from tools import stage3_composer_report
    from tools.stage_terrain_profiles import STAGE_TERRAIN_PROFILES

    custom_stage = tmp_path / "stage2.json"
    custom_stage.write_text(
        (ROOT / "data" / "stages" / "stage2.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="runtime canonical data"):
        stage3_composer_report._require_runtime_stage_path(
            custom_stage,
            STAGE_TERRAIN_PROFILES[2],
        )


def test_stage_json_bgm_files_exist() -> None:
    bgm_dir = ROOT / "assets" / "music" / "bgm"
    for p in sorted((ROOT / "data" / "stages").glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        bgm = data.get("bgm", "")
        if not bgm:
            continue
        assert (bgm_dir / bgm).exists(), f"{p.name}: missing BGM file '{bgm}'"


def test_stage_supports_world_layout_fields() -> None:
    from src.stages.stage import Stage

    stage = Stage(object(), 1)
    stage2 = Stage(object(), 2)
    stage3 = Stage(object(), 3)
    stage4 = Stage(object(), 4)
    stage1_data = json.loads((ROOT / "data" / "stages" / "stage1.json").read_text(encoding="utf-8"))

    assert stage.initial_terrain == []
    assert stage.terrain_layout
    assert stage.terrain_layout[0]["type"] == "TerrainPieces"
    assert stage.random_drop_scale == stage1_data["random_drop_scale"]
    assert stage2.initial_terrain == []
    assert stage2.terrain_layout
    assert stage2.random_drop_scale < 1.0
    assert stage3.initial_terrain == []
    assert stage3.terrain_layout
    assert stage3.terrain_layout[0]["type"] == "TerrainPieces"
    assert stage3.random_drop_scale < 1.0
    assert stage4.initial_terrain == []
    assert stage4.terrain_layout
    assert stage4.random_drop_scale < 1.0
    assert any(ev["type"].startswith("Enemy") for ev in stage.world_events)
    assert all(ev.get("type", "").startswith("Enemy") is False for ev in stage.events)


def test_random_item_drops_use_stage_scale() -> None:
    src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")

    assert "def _random_drop_chance" in src
    assert "self._random_drop_chance(float(getattr(ter, \"drop_chance\", 0.0)))" in src
    assert "chance = self._random_drop_chance(getattr(enemy, \"drop_chance\"" in src


def test_stage1_uses_authored_blood_cell_setpieces() -> None:
    data = json.loads((ROOT / "data" / "stages" / "stage1.json").read_text(encoding="utf-8"))
    layout = data["terrain_layout"][0]
    world_events = data["world_events"]

    assert layout["type"] == "TerrainPieces"
    assert layout["theme"] == "fever_cave"
    assert layout["renderer"] == "terrain_composer"
    assert layout["length"] >= 11000
    assert len(layout["pieces"]) >= 300
    assert 0.0 < data["random_drop_scale"] < 1.0
    assert "weapon_drop_limit" not in data
    assert any(ev.get("type", "").startswith("Enemy") for ev in world_events)
    assert any(ev.get("type") == "Boss" and ev.get("x") for ev in world_events)
    gate_events = [ev for ev in world_events if ev.get("type") in {"breakable_gate", "weapon_gate"}]
    assert gate_events
    assert all(ev.get("kind") == "clot" and int(ev.get("hp", 0)) > 0 for ev in gate_events)
    boss_gate = next(ev for ev in world_events if ev["type"] == "BossGate")
    assert boss_gate["trigger_x"] < next(ev["x"] for ev in world_events if ev["type"] == "Boss")
    assert data["events"] == []


def test_stage1_uses_explicit_composer_pieces_and_keeps_boss_strip_fallback() -> None:
    from src.core.terrain_composer import load_composer_catalog
    from src.entities.stage3_composer_terrain import load_stage3_composer_pieces

    data = json.loads((ROOT / "data" / "stages" / "stage1.json").read_text(encoding="utf-8"))
    layout = data["terrain_layout"][0]
    boss_strip = data["boss_terrain"][0]
    catalog = load_composer_catalog(ROOT / "tools" / "stage1_terrain_rects.json")
    pieces = load_stage3_composer_pieces(
        ROOT / "tools" / "stage1_terrain_rects.json",
        mask_dir=ROOT / "tools" / "stage1_terrain_alpha_masks",
    )
    fixed_clots = [
        event
        for event in [*data["boss_terrain"], *data["world_events"]]
        if event.get("kind") == "clot"
    ]

    assert layout["type"] == "TerrainPieces"
    assert layout["renderer"] == "terrain_composer"
    assert layout["composer_rects"] == "tools/stage1_terrain_rects.json"
    assert layout["composer_mask_dir"] == "tools/stage1_terrain_alpha_masks"
    assert len(layout["pieces"]) >= 300
    assert "top" not in layout
    assert "bottom" not in layout

    surface_pieces = [piece for piece in layout["pieces"] if piece["collision"] == "surface"]
    rect_pieces = [piece for piece in layout["pieces"] if piece["collision"] == "rect"]
    body_pieces = [piece for piece in layout["pieces"] if piece["role"] == "body_fill"]
    assert surface_pieces
    assert rect_pieces
    assert body_pieces
    assert {piece["side"] for piece in surface_pieces} == {"top", "bottom"}
    assert all(piece["collision"] in {"auto", "none", "rect"} for piece in body_pieces)
    assert {piece["side"] for piece in rect_pieces} <= {"top", "bottom"}

    assert boss_strip["type"] == "TerrainStrip"
    assert boss_strip["renderer"] == "terrain_composer"
    assert boss_strip["composer_rects"] == "tools/stage1_terrain_rects.json"
    assert boss_strip["composer_mask_dir"] == "tools/stage1_terrain_alpha_masks"
    assert boss_strip["composer_collision_mode"] == "source"
    assert "pieces" not in boss_strip

    assert fixed_clots
    for event in fixed_clots:
        role = event.get("material_role")
        asset = event.get("material_asset")
        assert role in catalog.roles
        assert asset in catalog.assets
        assert asset in {f"{piece.group}:{piece.index + 1}" for piece in pieces[role]}


def test_stage1_preplaces_boss_room_before_boss_alert() -> None:
    from src.core.constants import SCREEN_WIDTH
    from src.stages.stage import Stage

    data = json.loads((ROOT / "data" / "stages" / "stage1.json").read_text(encoding="utf-8"))
    boss_events = [ev for ev in data["world_events"] if ev["type"] == "Boss"]
    boss_gates = [ev for ev in data["world_events"] if ev["type"] == "BossGate"]
    boss_x = boss_events[0]["x"]
    gate_x = boss_gates[0]["trigger_x"]
    stage = Stage(object(), 1)

    assert stage.boss_terrain_mode == "preplaced"
    assert data["terrain_layout"][0]["length"] >= boss_x + 800
    assert len(boss_gates) == 1
    assert boss_gates[0]["trigger_x"] < boss_x
    assert boss_gates[0]["lock_camera_x"] + SCREEN_WIDTH <= boss_x
    assert boss_gates[0]["player_limit_x"] <= boss_x
    assert boss_x - SCREEN_WIDTH - boss_gates[0]["lock_camera_x"] <= SCREEN_WIDTH
    assert boss_events[0].get("preload", 80) == 0


def test_stage2_uses_authored_cyber_setpieces() -> None:
    from src.core.constants import SCREEN_WIDTH
    from src.stages.stage import Stage

    data = json.loads((ROOT / "data" / "stages" / "stage2.json").read_text(encoding="utf-8"))
    layout = data["terrain_layout"][0]
    world_events = data["world_events"]
    turrets = [ev for ev in world_events if ev["type"] == "EnemyTurret"]
    mounts = [ev for ev in world_events if ev["type"] == "turret_mount"]
    gates = [ev for ev in world_events if ev["type"] in {"breakable_gate", "weapon_gate"}]
    reward_gates = [ev for ev in world_events if ev["type"] == "weapon_gate"]
    minibosses = [
        ev for ev in world_events
        if ev["type"] in {"EnemyCoughSprayer", "EnemySporeSplitter"}
    ]
    fixed_weapon_events = [ev for ev in world_events if ev.get("fixed_drop") == "WeaponItem"]
    boss_x = next(ev["x"] for ev in world_events if ev["type"] == "Boss")
    boss_gate = next(ev for ev in world_events if ev["type"] == "BossGate")
    boss_room_blocks = [
        ev for ev in world_events
        if ev.get("kind") in {"debris", "data_block"} and ev.get("x", 0) >= boss_gate["trigger_x"]
    ]
    first_boss_room_x = min(ev["x"] for ev in boss_room_blocks)
    stage = Stage(object(), 2)

    assert data.get("initial_terrain", []) == []
    assert data["events"] == []
    assert data["boss_terrain_mode"] == "preplaced"
    assert 0.0 < data["random_drop_scale"] < 1.0
    assert layout["type"] == "TerrainStrip"
    assert layout["theme"] == "meme_static"
    assert layout["renderer"] == "terrain_composer"
    assert layout["composer_rects"] == "tools/stage2_terrain_rects.json"
    assert layout["composer_mask_dir"] == "tools/stage2_terrain_alpha_masks"
    assert layout["length"] >= boss_x + 800
    assert layout["breakable_drop_chance"] <= 0.05
    assert len(world_events) >= 40
    assert sum(int(ev.get("count", 1)) for ev in turrets) >= 5
    assert len(mounts) >= 4
    assert {ev.get("surface") for ev in turrets} >= {"top", "bottom"}
    assert len(gates) >= 3
    assert len(reward_gates) == 1
    assert all(ev.get("fixed_drop") == "WeaponItem" for ev in minibosses)
    assert [ev["type"] for ev in fixed_weapon_events].count("EnemyCoughSprayer") == 2
    assert [ev["type"] for ev in fixed_weapon_events].count("EnemySporeSplitter") == 1
    assert any(ev["type"] == "EnemyBilly" for ev in world_events)
    assert boss_gate["lock_camera_x"] + SCREEN_WIDTH <= first_boss_room_x
    assert boss_gate["player_limit_x"] <= first_boss_room_x
    assert boss_x - SCREEN_WIDTH - boss_gate["lock_camera_x"] <= 500
    assert stage.boss_terrain_mode == "preplaced"


def test_stage3_uses_explicit_labor_fortress_pieces() -> None:
    from src.core.constants import SCREEN_WIDTH
    from src.stages.stage import Stage

    data = json.loads((ROOT / "data" / "stages" / "stage3.json").read_text(encoding="utf-8"))
    layout = data["terrain_layout"][0]
    world_events = data["world_events"]
    turrets = [ev for ev in world_events if ev["type"] == "EnemyTurret"]
    mounts = [ev for ev in world_events if ev["type"] == "turret_mount"]
    gates = [ev for ev in world_events if ev["type"] in {"breakable_gate", "weapon_gate"}]
    reward_gates = [ev for ev in world_events if ev["type"] == "weapon_gate"]
    breakable_blocks = [
        ev for ev in world_events
        if ev.get("kind") == "fortress_block"
        and (ev.get("destructible") or ev["type"] in {"breakable_gate", "weapon_gate"})
    ]
    minibosses = [
        ev for ev in world_events
        if ev["type"] in {"EnemyCoughSprayer", "EnemySporeSplitter"}
    ]
    fixed_weapon_events = [ev for ev in world_events if ev.get("fixed_drop") == "WeaponItem"]
    boss_x = next(ev["x"] for ev in world_events if ev["type"] == "Boss")
    boss_gate = next(ev for ev in world_events if ev["type"] == "BossGate")
    boss_room_blocks = [
        ev for ev in world_events
        if ev.get("kind") in {"wall", "rock", "fortress_block"} and ev.get("x", 0) >= boss_gate["trigger_x"]
    ]
    # 9963291のチューニングでボス部屋の装飾ブロックは撤去され、部屋自体がノークラッター化された。
    # 装飾が存在する場合のみカメラロック/移動制限のクリアランスを検証する。
    first_boss_room_x = min((ev["x"] for ev in boss_room_blocks), default=None)
    stage = Stage(object(), 3)

    assert data.get("initial_terrain", []) == []
    assert data["events"] == []
    assert data["boss_terrain_mode"] == "preplaced"
    assert 0.0 < data["random_drop_scale"] < 1.0
    pieces = layout["pieces"]
    surface_pieces = [piece for piece in pieces if piece.get("collision") == "surface"]
    body_pieces = [piece for piece in pieces if piece.get("role") == "body_fill"]
    rect_collision_pieces = [piece for piece in pieces if piece.get("collision") == "rect"]

    assert layout["type"] == "TerrainPieces"
    assert layout["theme"] == "fortress"
    assert layout["renderer"] == "terrain_composer"
    assert "top" not in layout
    assert "bottom" not in layout
    assert len(pieces) >= 100
    assert len(surface_pieces) >= 60
    assert body_pieces
    assert rect_collision_pieces
    assert {piece.get("side") for piece in surface_pieces} >= {"top", "bottom"}
    assert layout["length"] >= boss_x + 800
    assert len(world_events) >= 40
    assert sum(int(ev.get("count", 1)) for ev in turrets) >= 10
    # turret_mount装飾は本チューニングで全廃止され、turretはcomposer地形のsurfaceへ直接吸着する方式に統一された。
    assert mounts == []
    assert {ev.get("surface") for ev in turrets} >= {"top", "bottom"}
    assert len(gates) >= 3
    assert len(reward_gates) == 1
    assert all(ev.get("fixed_drop") == "WeaponItem" for ev in minibosses)
    # ミニボス構成が再編され、CoughSprayerは1体・SporeSplitterは今回の区間には未配置になった。
    assert [ev["type"] for ev in fixed_weapon_events].count("EnemyCoughSprayer") == 1
    assert [ev["type"] for ev in fixed_weapon_events].count("EnemySporeSplitter") == 0
    # EnemyBillyの単独遭遇はこのチューニングでステージ3から削除された。
    assert [(ev["w"], ev["h"], ev["hp"]) for ev in breakable_blocks] == [
        (150, 94, 12),
        (150, 94, 12),
        (105, 246, 36),
        (105, 246, 36),
        (107, 168, 44),
        (123, 288, 48),
    ]
    assert max(ev.get("hp", 0) for ev in gates) >= 48
    for mount in mounts:
        mount_center = mount["x"] + mount["w"] / 2
        assert any(
            abs(ev["x"] - mount_center) <= 220
            for ev in turrets
        ), f"turret_mount at x={mount['x']} should have nearby turrets"
    # 隣接して並ぶ破壊可能ゲート（例: x=2942/3048の二重扉）は1つの障害物クラスタとして扱い、
    # クラスタ全体の近傍に守備役の敵がいるかを確認する。
    guard_types = {"EnemyTurret", "EnemyCrawler", "EnemyCoughSprayer", "EnemyBroly"}
    gate_clusters: list[list[dict]] = []
    for gate in sorted(gates, key=lambda g: g["x"]):
        if gate_clusters and gate["x"] - gate_clusters[-1][-1]["x"] <= 150:
            gate_clusters[-1].append(gate)
        else:
            gate_clusters.append([gate])
    for cluster in gate_clusters:
        lo = min(g["x"] for g in cluster) - 300
        hi = max(g["x"] for g in cluster) + 360
        assert any(
            ev["type"] in guard_types and lo <= ev.get("x", -9999) <= hi
            for ev in world_events
        ), f"gate cluster near x={[g['x'] for g in cluster]} should be part of a combat setpiece"
    # turretは「y固定の浮遊配置」からsurface吸着方式へ変わったため、高度条件はsurface方向で代替する。
    assert any(ev["type"] == "EnemyTurret" and ev.get("surface") == "bottom" and 3140 <= ev["x"] <= 3450 for ev in turrets)
    assert any(ev["type"] == "EnemyTurret" and ev.get("surface") == "top" and 5400 <= ev["x"] <= 5650 for ev in turrets)
    assert any(ev["type"] == "EnemyCrawler" and 7000 <= ev["x"] <= 7150 for ev in world_events)
    if first_boss_room_x is not None:
        assert boss_gate["lock_camera_x"] + SCREEN_WIDTH <= first_boss_room_x
        assert boss_gate["player_limit_x"] <= first_boss_room_x
    assert boss_x - SCREEN_WIDTH - boss_gate["lock_camera_x"] <= 500
    assert stage.boss_terrain_mode == "preplaced"


def test_stage3_piece_route_has_deliberate_chokes_and_arenas() -> None:
    from src.entities.stage3_composer_terrain import build_stage3_piece_layout, load_stage3_composer_pieces

    data = json.loads((ROOT / "data" / "stages" / "stage3.json").read_text(encoding="utf-8"))
    layout = data["terrain_layout"][0]
    composer_layout = build_stage3_piece_layout(layout, load_stage3_composer_pieces(), start_x=int(layout.get("x", 0)))

    def surface_y_at(x: float, side: str) -> float:
        candidates = [
            run.y
            for run in composer_layout.collision_runs
            if run.side == side and run.x0 <= x <= run.x1
        ]
        assert candidates, f"missing {side} surface near x={x}"
        return float(min(candidates) if side == "bottom" else max(candidates))

    def gap_at(x: float) -> float:
        return surface_y_at(x, "bottom") - surface_y_at(x, "top")

    assert gap_at(1200) >= 400
    assert gap_at(3300) <= 360
    assert gap_at(6100) >= 460
    assert gap_at(7300) <= 415
    assert gap_at(7650) >= 470


def test_stage3_ceiling_attackers_keep_clearance_from_hud() -> None:
    data = json.loads((ROOT / "data" / "stages" / "stage3.json").read_text(encoding="utf-8"))
    world_events = data["world_events"]
    ceiling_fliers = [
        ev for ev in world_events
        if ev["type"] == "EnemyPachemon" and ev.get("surface") == "top"
    ]
    # 9963291のチューニングでボス直前のTakeshi集団はx=7006/7048付近へ圧縮され、
    # 固定"y"の代わりに実座標である"anchor_y"で高さを指定するようになった。
    final_takeshi = [
        ev for ev in world_events
        if ev["type"] == "EnemyTakeshi" and ev.get("x", 0) >= 6900
    ]

    assert ceiling_fliers
    assert all(ev.get("surface_offset", 0) >= 130 for ev in ceiling_fliers)
    assert final_takeshi
    assert all(ev.get("anchor_y", 0) >= 180 for ev in final_takeshi)


def test_stage4_uses_authored_shogi_void_setpieces() -> None:
    from src.core.constants import SCREEN_WIDTH
    from src.stages.stage import Stage

    data = json.loads((ROOT / "data" / "stages" / "stage4.json").read_text(encoding="utf-8"))
    layout = data["terrain_layout"][0]
    world_events = data["world_events"]
    turrets = [ev for ev in world_events if ev["type"] == "EnemyTurret"]
    mounts = [ev for ev in world_events if ev["type"] == "turret_mount"]
    gates = [ev for ev in world_events if ev["type"] in {"breakable_gate", "weapon_gate"}]
    reward_gates = [ev for ev in world_events if ev["type"] == "weapon_gate"]
    minibosses = [
        ev for ev in world_events
        if ev["type"] in {"EnemyCoughSprayer", "EnemySporeSplitter"}
    ]
    fixed_weapon_events = [ev for ev in world_events if ev.get("fixed_drop") == "WeaponItem"]
    boss_x = next(ev["x"] for ev in world_events if ev["type"] == "Boss")
    boss_gate = next(ev for ev in world_events if ev["type"] == "BossGate")
    boss_room_blocks = [
        ev for ev in world_events
        if ev.get("kind") == "rock" and ev.get("x", 0) >= boss_gate["trigger_x"]
    ]
    first_boss_room_x = min(ev["x"] for ev in boss_room_blocks)
    stage = Stage(object(), 4)

    assert data.get("initial_terrain", []) == []
    assert data["events"] == []
    assert data["boss_terrain_mode"] == "preplaced"
    assert 0.0 < data["random_drop_scale"] < 1.0
    assert layout["type"] == "TerrainStrip"
    assert layout["theme"] == "shogi_void"
    assert layout["profile"] == "ceiling"
    assert layout["length"] >= boss_x + 800
    assert layout["breakable_drop_chance"] <= 0.04
    assert len(world_events) >= 45
    assert sum(int(ev.get("count", 1)) for ev in turrets) >= 15
    assert len(mounts) >= 3
    assert {ev.get("surface") for ev in turrets} >= {"top", "bottom"}
    assert len(gates) >= 3
    assert len(reward_gates) == 1
    assert all(ev.get("fixed_drop") == "WeaponItem" for ev in minibosses)
    assert [ev["type"] for ev in fixed_weapon_events].count("EnemyCoughSprayer") == 2
    assert [ev["type"] for ev in fixed_weapon_events].count("EnemySporeSplitter") == 2
    assert any(ev["type"] == "EnemyBilly" for ev in world_events)
    assert max(ev.get("hp", 0) for ev in gates) >= 26
    assert boss_gate["lock_camera_x"] + SCREEN_WIDTH <= first_boss_room_x
    assert boss_gate["player_limit_x"] <= first_boss_room_x
    assert boss_x - SCREEN_WIDTH - boss_gate["lock_camera_x"] <= 500
    assert stage.boss_terrain_mode == "preplaced"


def test_world_event_boss_gate_does_not_spawn_boss_until_boss_event() -> None:
    from src.core.camera import Camera
    from src.stages.spawner import EnemySpawner

    camera = Camera()
    camera.x = 6850.0
    spawner = EnemySpawner(
        game=object(),
        enemies=pygame.sprite.Group(),
        enemy_bullets=pygame.sprite.Group(),
        events=[],
        world_events=[
            {"type": "BossGate", "trigger_x": 7650, "lock_camera_x": 6850, "player_limit_x": 7650},
            {"type": "Boss", "x": 8100, "count": 1, "formation": "single", "preload": 0},
        ],
        player=object(),
    )

    spawner.update(1.0 / 60.0, camera)

    assert spawner.boss_gate_pending is True
    assert spawner.boss_gate_event is not None
    assert spawner.boss_gate_event["lock_camera_x"] == 6850
    assert spawner.boss_pending is False

    spawner.clear_boss_gate()
    camera.x = 7300.0
    spawner.update(1.0 / 60.0, camera)

    assert spawner.boss_gate_pending is False
    assert spawner.boss_pending is True


def test_world_event_turret_spawns_at_authored_x_on_surface() -> None:
    from src.core.camera import Camera
    from src.entities.terrain import make_terrain_strip
    from src.stages.spawner import EnemySpawner

    camera = Camera()
    camera.x = 119.0
    terrain = pygame.sprite.Group(*make_terrain_strip(
        900,
        length=320,
        segment_w=64,
        seed=8,
        gap_min=380,
        gap_max=380,
    ))
    enemies = pygame.sprite.Group()
    spawner = EnemySpawner(
        game=object(),
        enemies=enemies,
        enemy_bullets=pygame.sprite.Group(),
        events=[],
        world_events=[
            {"type": "EnemyTurret", "x": 1000, "count": 1, "surface": "bottom", "surface_offset": 24}
        ],
        player=object(),
        terrain=terrain,
    )

    spawner.update(1.0 / 60.0, camera)
    assert len(enemies) == 0

    camera.x = 121.0
    spawner.update(1.0 / 60.0, camera)
    turret = next(iter(enemies))
    surface_y = spawner._surface_y_at(1000, "bottom")
    assert type(turret).__name__ == "EnemyTurret"
    assert turret.world_x == 1000
    assert surface_y is not None
    assert turret.world_y == surface_y - 24


def test_world_event_surface_can_use_authored_terrain_block() -> None:
    from src.core.camera import Camera
    from src.entities.terrain import Terrain
    from src.stages.spawner import EnemySpawner

    camera = Camera()
    camera.x = 121.0
    terrain = pygame.sprite.Group(Terrain(940, 420, 160, 36, "wall"))
    enemies = pygame.sprite.Group()
    spawner = EnemySpawner(
        game=object(),
        enemies=enemies,
        enemy_bullets=pygame.sprite.Group(),
        events=[],
        world_events=[
            {"type": "EnemyTurret", "x": 1000, "count": 1, "surface": "bottom", "surface_offset": 24}
        ],
        player=object(),
        terrain=terrain,
    )

    spawner.update(1.0 / 60.0, camera)
    turret = next(iter(enemies))

    assert spawner._surface_y_at(1000, "bottom") == 420
    assert turret.world_x == 1000
    assert turret.world_y == 396


def test_world_event_anchor_y_preserves_authored_formation_position() -> None:
    from src.core.camera import Camera
    from src.stages.spawner import EnemySpawner

    camera = Camera()
    spawner = EnemySpawner(
        game=object(),
        enemies=pygame.sprite.Group(),
        enemy_bullets=pygame.sprite.Group(),
        events=[],
        world_events=[],
        player=object(),
        terrain=pygame.sprite.Group(),
    )

    positions = spawner._world_positions(
        {"type": "EnemyVirus", "x": 1000, "count": 3, "formation": "line", "anchor_y": 300},
        3,
        "bottom",
        camera,
        offset=20,
        step=56,
    )

    assert positions == [(1000, 256), (1056, 300), (1112, 344)]


def test_world_event_fixed_drop_metadata_reaches_spawned_objects() -> None:
    from src.core.camera import Camera
    from src.stages.spawner import EnemySpawner

    camera = Camera()
    camera.x = 130.0
    enemies = pygame.sprite.Group()
    terrain = pygame.sprite.Group()
    spawner = EnemySpawner(
        game=object(),
        enemies=enemies,
        enemy_bullets=pygame.sprite.Group(),
        events=[],
        world_events=[
            {
                "type": "EnemyTurret",
                "x": 1000,
                "count": 1,
                "surface": "bottom",
                "fixed_drop": "WeaponItem",
            },
            {
                "type": "weapon_gate",
                "x": 1010,
                "y": 92,
                "w": 80,
                "h": 120,
                "kind": "clot",
            },
        ],
        player=object(),
        terrain=terrain,
    )

    spawner.update(1.0 / 60.0, camera)
    enemy = next(iter(enemies))
    gate = next(iter(terrain))

    assert getattr(enemy, "fixed_drop", None) == "WeaponItem"
    assert gate.fixed_drop == "WeaponItem"


def test_regular_stages_define_boss_terrain() -> None:
    for p in sorted((ROOT / "data" / "stages").glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("debug"):
            continue
        assert data.get("boss_terrain"), f"{p.name}: boss_terrain is empty"


def test_boss_terrain_replaces_stage_terrain() -> None:
    src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    assert "def _replace_boss_terrain" in src
    assert "def _prepare_boss_terrain" in src
    assert "self.terrain.empty()" in src
    assert "preplaced_here" in src
    assert 'boss_stage.boss_terrain_mode == "preplaced"' in src
    assert "self._prepare_boss_terrain(self._active_boss_stage_id)" in src


def test_debug_boss_spawn_forwards_selected_stage() -> None:
    scene_src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    spawner_src = (ROOT / "src" / "stages" / "spawner.py").read_text(encoding="utf-8")
    panel_src = (ROOT / "src" / "scenes" / "game" / "debug_stage_panel.py").read_text(encoding="utf-8")

    assert "def confirm_spawn_boss(self, stage_id: int | None = None)" in spawner_src
    assert "confirm_spawn_boss(stage_id=self._boss_stage_id())" in scene_src
    assert "_queue_boss_spawn(stage_for_boss)" in panel_src


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
                        ("BOSS_DEFEAT", script.BOSS_DEFEAT)):
        assert ids <= set(table.keys()), f"{name} に未定義のステージ: {ids - set(table.keys())}"
    # 物語タイムライン: 各ステージに直前ビートがあること
    missing = {sid for sid in ids if not script.intro_beats(sid)}
    assert not missing, f"STORY_BEATS に直前ビートが無いステージ: {sorted(missing)}"


def test_story_speakers_are_registered() -> None:
    from src.story import script
    from src.story.speakers import SPEAKERS
    used: set[str] = set()
    for grp in (list(script.BOSS_INTRO.values()) + list(script.BOSS_MID.values())
                + list(script.BOSS_DEFEAT.values())
                + [script.BOSS_FORM3_INTRO] + list(script.FINAL_SEQ.values())
                + list(script.TUTORIAL.values())
                + [script.BILLY_SPAWN_BARKS, script.BILLY_KILL_BARKS,
                   script.SAKURA_LAST_WORDS, script.OVERHEAT_BARKS]):
        used.update(ln.speaker for ln in grp)
    # 全画面会話の話者は STORY_BEATS のページから収集する。
    for beat in script.STORY_BEATS:
        used.update(pg.speaker for pg in beat.pages)
    unknown = used - set(SPEAKERS.keys())
    assert not unknown, f"SPEAKERS に未登録の話者: {sorted(unknown)}"


def test_story_flow_resolves_scene_types() -> None:
    """ビート種別 → 再生シーンの対応（cutscene=CutsceneScene / blackhole=BlackholeScene）。"""
    from src.scenes.story_flow import _scene_for_beat
    from src.scenes.cutscene_scene import CutsceneScene
    from src.scenes.blackhole_scene import BlackholeScene
    from src.story.script import story_beat
    cb = lambda: None  # noqa: E731
    assert isinstance(_scene_for_beat(None, story_beat("1->2"), cb), CutsceneScene)
    assert isinstance(_scene_for_beat(None, story_beat("3->4"), cb), BlackholeScene)


def test_story_flow_chains_beats_and_runs_finish_hook(monkeypatch) -> None:
    """play_beats が複数ビートを順に再生し、on_finish フック（karonaru_lost）を
    適用してから最後に on_done を呼ぶ（ステージ4直前: ブラックホール→将棋導入）。"""
    from src.scenes import story_flow
    from src.story.script import intro_beats

    class _FakeStory:
        karonaru_available = True
        karonaru_lost = False
        blackhole_event_done = False

    class _FakeGame:
        def __init__(self) -> None:
            self.story = _FakeStory()
            self.played: list[str] = []

        def change_scene(self, scene) -> None:
            key, on_complete = scene
            self.played.append(key)
            on_complete()  # 即完了して次のビートへ

    # 実シーン生成を「(キー, 完了コールバック) を返す」スタブに差し替える。
    monkeypatch.setattr(story_flow, "_scene_for_beat",
                        lambda game, beat, on_complete: (beat.key, on_complete))

    game = _FakeGame()
    done: list[str] = []
    story_flow.play_beats(game, intro_beats(4), lambda: done.append("launch"))

    assert game.played == ["3->4", "3->4_void"]
    assert done == ["launch"]
    assert game.story.karonaru_lost is True
    assert game.story.karonaru_available is False
    assert game.story.blackhole_event_done is True


def test_story_aliases_resolve_to_existing_files() -> None:
    from src.story.aliases import BGM, SE
    assets = ROOT / "assets"
    missing = [f"{a} -> {p}" for a, p in {**BGM, **SE}.items()
               if p and not (assets / p).exists()]
    assert not missing, f"aliases の実ファイルが見つからない: {missing}"



def test_boss_form3_phase_config_exists() -> None:
    from src.entities.enemies.boss import _PHASE_CONFIGS
    assert "4f3" in _PHASE_CONFIGS, "boss._PHASE_CONFIGS に '4f3'（頑固王サワグチ）が未定義"


def test_stage_backgrounds_draw_all_stages() -> None:
    """全ステージのテーマ別背景が例外なく描画できる。"""
    from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
    from src.entities.background import ScrollingBackground
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    for sid in (0, 1, 2, 3, 4):
        bg = ScrollingBackground(sid)
        for f in range(3):
            bg.draw(surf, camera_x=f * 30.0)


def test_stage1_background_uses_dedicated_image_and_keeps_procedural_layers() -> None:
    from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH
    from src.entities.background import ScrollingBackground, _STAGE1_BG_PATH

    assert _STAGE1_BG_PATH == ROOT / "assets" / "graphic" / "stage1_fever_corridor_bg.png"
    assert _STAGE1_BG_PATH.exists()

    bg = ScrollingBackground(1)
    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    assert bg._stage1_bg is None
    bg.draw(surface, camera_x=0.0)
    first_frame = pygame.image.tobytes(surface, "RGB")
    cached_background = bg._stage1_bg
    bg.draw(surface, camera_x=60.0)

    assert bg._stage1_bg is not None
    assert bg._stage1_bg.get_height() == SCREEN_HEIGHT
    assert bg._stage1_bg is cached_background
    assert pygame.image.tobytes(surface, "RGB") != first_frame
    assert bg._stage1_far_cells
    assert bg._stage1_near_cells
    assert bg._stage1_membranes


# ── docs ─────────────────────────────────────────────────────────────

def test_stage3_background_loop_uses_fade_in_tile_edge() -> None:
    from src.entities.background import ScrollingBackground

    bg = ScrollingBackground(3)
    source = pygame.Surface((16, 4), pygame.SRCALPHA)
    source.fill((120, 140, 150, 255))
    strip = bg._stage3_backdrop_blend_strip(source, 12)

    assert strip.get_at((0, 0)).a == 0
    assert strip.get_at((11, 0)).a >= 250


def test_terrain_strip_can_spawn_breakable_segments() -> None:
    from src.core.constants import SCREEN_HEIGHT
    from src.entities.terrain import make_terrain_strip

    segments = make_terrain_strip(
        0,
        length=512,
        segment_w=64,
        seed=3,
        breakable_chance=1.0,
        breakable_hp=2,
    )
    breakables = [s for s in segments if getattr(s, "destructible", False)]
    assert breakables
    assert all(
        (target.y > 0 if target.side == "top" else target.y + target.rect.height < SCREEN_HEIGHT)
        for target in breakables
    )

    target = breakables[0]
    assert target.take_damage(1) is False
    assert target.hp == 1
    assert target.take_damage(1) is True


def test_authored_terrain_points_generate_corridor_segments() -> None:
    from src.entities.terrain import make_terrain_segments_from_event

    event = {
        "type": "AuthoredTerrain",
        "theme": "fortress",
        "segment_w": 100,
        "min_gap": 220,
        "top": [[0, 40], [500, 100], [1000, 60]],
        "bottom": [[0, 520], [500, 440], [1000, 500]],
    }
    segments = make_terrain_segments_from_event(event, 0, default_seed=3)
    top = [s for s in segments if s.side == "top"]
    bottom = [s for s in segments if s.side == "bottom"]

    assert top
    assert bottom
    assert len({s.world_x for s in top}) == len({s.world_x for s in bottom})
    assert min(s.y for s in bottom) - max(s.rect.height for s in top) >= 220


def test_stage3_composer_terrain_splits_visual_and_collision_sprites() -> None:
    from src.entities.stage3_composer_terrain import make_stage3_composer_terrain
    from src.entities.terrain import make_terrain_strip

    segments = make_terrain_strip(
        -100,
        length=640,
        theme="fortress",
        profile="mountain",
        segment_w=48,
        seed=303,
        gap_min=292,
        gap_max=390,
        center_y=292,
        center_wave=118,
        top_min=28,
        bottom_min=34,
        irregularity=58,
    )
    sprites = make_stage3_composer_terrain(segments)
    visuals = [sprite for sprite in sprites if getattr(sprite, "terrain_visual_only", False)]
    collisions = [sprite for sprite in sprites if not getattr(sprite, "terrain_visual_only", False)]

    assert len(visuals) == 1
    assert collisions
    assert {getattr(sprite, "side", "") for sprite in collisions} >= {"top", "bottom"}
    assert all(
        getattr(sprite, "surface_y", None) is not None
        for sprite in collisions
        if getattr(sprite, "side", "") in {"top", "bottom"}
    )


def test_stage1_explicit_pieces_build_surface_and_rect_collision() -> None:
    from src.core.camera import Camera
    from src.entities.stage3_composer_terrain import (
        Stage3ComposerCollisionBlock,
        Stage3ComposerCollisionRectBlock,
        Stage3ComposerPieceVisualLayer,
        Stage3ComposerVisualLayer,
        build_stage3_piece_layout,
        load_stage3_composer_pieces,
    )
    from src.stages.spawner import EnemySpawner

    layout = json.loads((ROOT / "data" / "stages" / "stage1.json").read_text(encoding="utf-8"))["terrain_layout"][0]
    camera = Camera()
    pieces = load_stage3_composer_pieces(
        ROOT / layout["composer_rects"],
        mask_dir=ROOT / layout["composer_mask_dir"],
    )
    expected = build_stage3_piece_layout(
        layout,
        pieces,
        start_x=int(layout.get("x", 0)),
        collision_step=int(layout["composer_collision_step"]),
        collision_tolerance=int(layout["composer_collision_tolerance"]),
    )
    terrain = pygame.sprite.Group()
    spawner = EnemySpawner(
        game=object(),
        enemies=pygame.sprite.Group(),
        enemy_bullets=pygame.sprite.Group(),
        events=[],
        player=object(),
        stage_id=1,
        terrain=terrain,
    )

    spawner.spawn_terrain_events([layout], camera)

    visuals = [sprite for sprite in terrain if isinstance(sprite, Stage3ComposerVisualLayer)]
    piece_visuals = [sprite for sprite in terrain if isinstance(sprite, Stage3ComposerPieceVisualLayer)]
    surface_collisions = [sprite for sprite in terrain if isinstance(sprite, Stage3ComposerCollisionBlock)]
    rect_collisions = [sprite for sprite in terrain if isinstance(sprite, Stage3ComposerCollisionRectBlock)]

    assert len(visuals) == 1
    assert len(surface_collisions) == len(expected.collision_runs)
    assert len(rect_collisions) == len(expected.collision_rects)
    assert {sprite.side for sprite in surface_collisions} == {"top", "bottom"}
    assert all(sprite.surface_y is not None for sprite in surface_collisions)
    assert rect_collisions
    placement_state = lambda placement: (
        placement.asset,
        placement.role,
        placement.collision,
        placement.side,
        placement.x,
        placement.y,
        placement.clip,
    )
    # The base layer remains a single cheap backdrop.  Pieces are independent
    # visual sprites so authored draw_order can interleave with breakable
    # world-event Terrain without changing collision blocks.
    assert visuals[0].layout.placements == ()
    assert len(piece_visuals) == len(expected.placements)
    assert [placement_state(sprite.placement) for sprite in piece_visuals] == [
        placement_state(value) for value in expected.placements
    ]


def test_stage3_composer_floor_props_are_collidable() -> None:
    from src.entities.stage3_composer_terrain import (
        build_stage3_piece_layout,
        load_stage3_composer_pieces,
        make_stage3_composer_terrain_from_pieces,
    )

    stage3 = json.loads((ROOT / "data" / "stages" / "stage3.json").read_text(encoding="utf-8"))
    layout = stage3["terrain_layout"][0]
    composer_layout = build_stage3_piece_layout(
        layout,
        load_stage3_composer_pieces(),
        start_x=int(layout.get("x", 0)),
    )
    sprites = make_stage3_composer_terrain_from_pieces(layout, start_x=int(layout.get("x", 0)))
    prop_blocks = [
        sprite
        for sprite in sprites
        if not getattr(sprite, "terrain_visual_only", False)
        and getattr(sprite, "side", "") == ""
    ]

    assert any(placement.role == "floor_prop" for placement in composer_layout.placements)
    assert composer_layout.collision_rects
    assert prop_blocks
    assert all(block.rect.width > 0 and block.rect.height > 0 for block in prop_blocks)


def test_stage3_piece_layout_generates_surface_collision_from_explicit_blocks() -> None:
    from src.entities.stage3_composer_terrain import build_stage3_piece_layout, load_stage3_composer_pieces

    stage3 = json.loads((ROOT / "data" / "stages" / "stage3.json").read_text(encoding="utf-8"))
    layout = stage3["terrain_layout"][0]
    composer_layout = build_stage3_piece_layout(
        layout,
        load_stage3_composer_pieces(),
        start_x=int(layout.get("x", 0)),
    )

    assert layout["type"] == "TerrainPieces"
    assert composer_layout.placements
    assert {run.side for run in composer_layout.collision_runs} >= {"top", "bottom"}
    assert all(placement.asset for placement in composer_layout.placements)


def test_stage3_composer_body_fill_uses_uncut_rect_pieces() -> None:
    from src.entities.stage3_composer_terrain import build_stage3_composer_layout, load_stage3_composer_pieces
    from src.entities.terrain import make_terrain_strip

    pieces = load_stage3_composer_pieces()
    source_sizes = {piece.image.get_size() for piece in pieces.get("body_fill", [])}
    assert source_sizes
    assert [(piece.group, piece.index + 1) for piece in pieces["body_fill"]] == [
        ("block_square", 1),
        ("block_square", 3),
        ("block_square", 4),
        ("block_square", 6),
        ("block_square", 7),
        ("block_square", 8),
    ]

    segments = make_terrain_strip(
        -100,
        length=1200,
        theme="fortress",
        profile="mountain",
        segment_w=48,
        seed=303,
        gap_min=292,
        gap_max=390,
        center_y=292,
        center_wave=118,
        top_min=28,
        bottom_min=34,
        irregularity=58,
    )
    layout = build_stage3_composer_layout(segments, pieces, start_x=0, end_x=1000)
    body = [placement for placement in layout.placements if placement.role == "body_fill"]

    assert body
    assert all(placement.image.get_size() in source_sizes for placement in body)
    assert all(placement.clip.size == placement.image.get_size() for placement in body)


def test_stage3_composer_body_fill_touches_surface_caps() -> None:
    from src.entities.stage3_composer_terrain import (
        SURFACE_CAP_OVERHANG,
        _surface_band_depth,
        load_stage3_composer_pieces,
    )

    pieces = load_stage3_composer_pieces()
    cap_heights = sorted(piece.image.get_height() for piece in pieces["floor_surface"])

    assert _surface_band_depth(pieces) == cap_heights[len(cap_heights) // 2] - SURFACE_CAP_OVERHANG


def test_stage3_composer_rect_roles_are_available() -> None:
    from src.entities.stage3_composer_terrain import load_stage3_composer_pieces
    from src.entities.terrain import _stage3_piece_cover_scale

    pieces = load_stage3_composer_pieces()
    expected_roles = {
        "floor_surface",
        "ceiling_surface",
        "body_fill",
        "fixed_floor_block",
        "fixed_ceiling_block",
        "exposed_column",
        "floor_prop",
        "decor_prop",
        "turret_mount",
        "breakable_block",
    }

    assert expected_roles <= set(pieces)
    assert all(pieces[role] for role in expected_roles)
    assert [(piece.group, piece.index + 1) for piece in pieces["breakable_block"]] == [
        ("block_square", 2),
        ("block_tall", 1),
        ("block_tall", 2),
        ("block_tall", 4),
        ("block_tall", 8),
    ]
    for w, h in ((150, 94), (105, 246), (107, 168), (123, 288)):
        assert min(_stage3_piece_cover_scale(piece.image, w, h) for piece in pieces["breakable_block"]) <= 1.25
        assert min(
            abs((piece.image.get_width() / max(1, piece.image.get_height())) - (w / h))
            for piece in pieces["breakable_block"]
        ) <= 0.02


def test_stage2_composer_rect_roles_are_available() -> None:
    from src.entities.stage3_composer_terrain import load_stage3_composer_pieces

    pieces = load_stage3_composer_pieces(
        ROOT / "tools" / "stage2_terrain_rects.json",
        mask_dir=ROOT / "tools" / "stage2_terrain_alpha_masks",
    )
    expected_roles = {
        "floor_surface",
        "ceiling_surface",
        "body_fill",
        "fixed_floor_block",
        "fixed_ceiling_block",
        "exposed_column",
        "floor_prop",
        "decor_prop",
        "turret_mount",
        "breakable_block",
    }

    assert expected_roles <= set(pieces)
    assert all(pieces[role] for role in expected_roles)
    assert len(pieces["floor_surface"]) >= 6
    assert len(pieces["block_square"]) >= 12
    assert all(piece.image.get_width() > 0 and piece.image.get_height() > 0 for piece in pieces["floor_surface"])


def test_stage1_clot_runtime_fits_representative_dedicated_materials(monkeypatch) -> None:
    from src.entities import terrain as terrain_module

    data = json.loads((ROOT / "data" / "stages" / "stage1.json").read_text(encoding="utf-8"))
    fixed_clots = [
        event
        for event in [*data["boss_terrain"], *data["world_events"]]
        if event.get("kind") == "clot"
    ]
    samples = {
        "breakable_block": next(event for event in fixed_clots if event.get("material_role") == "breakable_block"),
    }
    real_material_surface = terrain_module._stage3_rect_material_surface

    for role, event in samples.items():
        w = int(event["w"])
        h = int(event["h"])
        surface_anchor = str(event.get("surface_anchor", "floor"))
        image = real_material_surface(
            w,
            h,
            seed=101,
            require_top=surface_anchor != "ceiling",
            kind="clot",
            preferred_role=role,
            surface_anchor=surface_anchor,
            material_asset=str(event["material_asset"]),
            allow_asset_resize=True,
        )

        assert image is not None
        assert image.get_size() == (w, h)
        bounds = image.get_bounding_rect()
        assert bounds.width >= int(w * 0.6)
        assert bounds.height >= int(h * 0.6)

    calls: list[dict] = []

    def record_material_surface(w: int, h: int, **kwargs):
        calls.append({"w": w, "h": h, **kwargs})
        return pygame.Surface((w, h), pygame.SRCALPHA)

    monkeypatch.setattr(terrain_module, "_stage3_rect_material_surface", record_material_surface)
    sample = samples["breakable_block"]
    terrain_module.Terrain(
        0,
        float(sample["y"]),
        int(sample["w"]),
        int(sample["h"]),
        "clot",
        material_role=str(sample["material_role"]),
        material_asset=str(sample["material_asset"]),
    )

    assert calls
    assert calls[0]["kind"] == "clot"
    assert calls[0]["preferred_role"] == "breakable_block"
    assert calls[0]["material_asset"] == sample["material_asset"]
    assert calls[0]["allow_asset_resize"] is True

    calls.clear()
    terrain_module.Terrain(0, 0, 112, 64, "clot")
    assert calls == []

    monkeypatch.setattr(terrain_module, "_stage3_rect_material_surface", real_material_surface)
    gate = terrain_module.Terrain(
        0,
        0,
        118,
        208,
        "clot",
        destructible=True,
        hp=10,
        fixed_drop="WeaponItem",
        material_role="breakable_block",
        material_asset="clot_gate:2",
    )
    before_damage = pygame.image.tobytes(gate.image, "RGBA")

    assert gate.take_damage(1) is False
    assert gate.image.get_size() == (118, 208)
    assert pygame.image.tobytes(gate.image, "RGBA") != before_damage
    assert any(
        gate.image.get_at((x, y)).g > 180 and gate.image.get_at((x, y)).b > 180
        for x in range(40, 78)
        for y in range(80, 128)
    )


def test_stage3_fortress_block_keeps_surface_anchor_after_damage() -> None:
    from src.entities.terrain import Terrain

    floor_block = Terrain(0, 330, 126, 168, "fortress_block", destructible=True, hp=3)
    ceiling_block = Terrain(0, 0, 126, 168, "fortress_block", destructible=True, hp=3)

    assert floor_block._surface_anchor == "floor"
    assert ceiling_block._surface_anchor == "ceiling"
    assert floor_block.take_damage(1) is False
    assert floor_block._surface_anchor == "floor"


def test_stage3_fortress_breakable_blocks_are_visually_distinct() -> None:
    from src.entities.terrain import Terrain

    normal = Terrain(0, 330, 126, 168, "fortress_block")
    breakable = Terrain(0, 330, 126, 168, "fortress_block", destructible=True, hp=3)
    reward = Terrain(0, 330, 126, 168, "fortress_block", destructible=True, hp=3, fixed_drop="WeaponItem")

    def count_crack_pixels(surface: pygame.Surface) -> int:
        count = 0
        for y in range(surface.get_height()):
            for x in range(surface.get_width()):
                r, g, b, a = surface.get_at((x, y))
                if a >= 180 and 175 <= r <= 205 and 120 <= g <= 145 and 90 <= b <= 115:
                    count += 1
        return count

    def count_reward_core_pixels(surface: pygame.Surface) -> int:
        count = 0
        for y in range(surface.get_height()):
            for x in range(surface.get_width()):
                r, g, b, a = surface.get_at((x, y))
                if a > 120 and r <= 160 and g >= 180 and b >= 210:
                    count += 1
        return count

    assert pygame.image.tobytes(normal.image, "RGBA") != pygame.image.tobytes(breakable.image, "RGBA")
    assert count_crack_pixels(breakable.image) > count_crack_pixels(normal.image) + 18
    assert count_reward_core_pixels(reward.image) > count_reward_core_pixels(breakable.image) + 40


def test_stage3_fortress_breakable_damage_changes_visual_state() -> None:
    from src.entities.terrain import Terrain, _stage3_breakable_crack_count

    def count_crack_pixels(surface: pygame.Surface) -> int:
        count = 0
        for y in range(surface.get_height()):
            for x in range(surface.get_width()):
                r, g, b, a = surface.get_at((x, y))
                if a >= 180 and 175 <= r <= 205 and 120 <= g <= 145 and 90 <= b <= 115:
                    count += 1
        return count

    block = Terrain(0, 330, 126, 168, "fortress_block", destructible=True, hp=4)
    before_count = count_crack_pixels(block.image)

    assert block.take_damage(1) is False
    first_count = count_crack_pixels(block.image)
    assert first_count > before_count

    assert block.take_damage(1) is False
    second_count = count_crack_pixels(block.image)
    assert second_count > first_count

    assert _stage3_breakable_crack_count(126, 168, 0.5) > _stage3_breakable_crack_count(126, 168, 0.0)


def test_spawner_surface_ignores_visual_only_terrain() -> None:
    from src.stages.spawner import EnemySpawner

    class VisualOnly(pygame.sprite.Sprite):
        terrain_visual_only = True

        def __init__(self) -> None:
            super().__init__()
            self.world_x = 0.0
            self.y = 0.0
            self.side = "bottom"
            self.image = pygame.Surface((100, 600), pygame.SRCALPHA)
            self.rect = self.image.get_rect(topleft=(0, 0))

        @property
        def surface_y(self) -> float:
            return 0.0

    class Collision(pygame.sprite.Sprite):
        def __init__(self) -> None:
            super().__init__()
            self.world_x = 0.0
            self.y = 420.0
            self.side = "bottom"
            self.image = pygame.Surface((100, 180), pygame.SRCALPHA)
            self.rect = self.image.get_rect(topleft=(0, 420))

        @property
        def surface_y(self) -> float:
            return 420.0

    terrain = pygame.sprite.Group(VisualOnly(), Collision())
    spawner = EnemySpawner(
        game=None,
        enemies=pygame.sprite.Group(),
        enemy_bullets=pygame.sprite.Group(),
        events=[],
        player=object(),
        terrain=terrain,
    )

    assert spawner._surface_y_at(50, "bottom") == 420.0


def test_destructible_terrain_gate_takes_damage() -> None:
    from src.entities.terrain import Terrain

    gate = Terrain(0, 0, 96, 600, "wall", destructible=True, hp=2, drop_chance=0.35)
    assert gate.drop_chance == 0.35
    assert gate.take_damage(1) is False
    assert gate.hp == 1
    assert gate.take_damage(1) is True


def test_large_debris_splits_into_shards() -> None:
    from src.entities.enemies.debris import EnemyDebrisLarge, EnemyDebrisShard

    debris = EnemyDebrisLarge(object(), 520.0, 280.0)
    shards = debris.split(object())
    assert len(shards) == 5
    assert all(isinstance(s, EnemyDebrisShard) for s in shards)


def test_spore_splitter_splits_into_pods() -> None:
    from src.entities.enemies.spore_splitter import EnemySporePod, EnemySporeSplitter

    class Resources:
        def image(self, path: str) -> pygame.Surface:
            return pygame.Surface((72, 72), pygame.SRCALPHA)

    class Game:
        resources = Resources()

    splitter = EnemySporeSplitter(Game(), 520.0, 280.0)
    pods = splitter.split(Game())

    assert len(pods) == 4
    assert all(isinstance(p, EnemySporePod) for p in pods)
    assert all(getattr(p, "drops_enabled", True) is False for p in pods)


def test_miniboss_enemies_hold_front_screen_position() -> None:
    from src.entities.enemies.cough_sprayer import EnemyCoughSprayer
    from src.entities.enemies.spore_splitter import EnemySporeSplitter

    class Resources:
        def image(self, path: str) -> pygame.Surface:
            return pygame.Surface((72, 72), pygame.SRCALPHA)

    class Game:
        resources = Resources()

    class Camera:
        x = 0.0

        def to_screen_x(self, world_x: float) -> float:
            return world_x - self.x

        def to_world_x(self, screen_x: float) -> float:
            return screen_x + self.x

    for enemy_cls in (EnemyCoughSprayer, EnemySporeSplitter):
        camera = Camera()
        enemy = enemy_cls(Game(), camera.to_world_x(850.0), 300.0)
        for _ in range(180):
            camera.x += 80.0 / 60.0
            enemy.update(1.0 / 60.0, camera)

        sx = camera.to_screen_x(enemy.world_x)
        assert 560.0 <= sx <= 700.0

        for _ in range(120):
            camera.x += 80.0 / 60.0
            enemy.update(1.0 / 60.0, camera)

        sx = camera.to_screen_x(enemy.world_x)
        assert 560.0 <= sx <= 700.0


def test_boss_phase_configs_reference_known_patterns() -> None:
    from src.entities.enemies.boss import _PHASE_CONFIGS

    known = {
        "fan5", "fan7", "aimed", "dbl_aimed", "ring8", "ring12", "ring16",
        "aimring6", "aimring8", "scatter", "cross", "spiral", "vortex2",
        "vortex3", "chaos", "burst3", "wall_gap", "fever_lunge",
        "mega_laser", "super_laser", "drone_cross", "rock_fall", "shogi_file",
        "shogi_storm", "shogi_drop", "board_throw", "mega_beam", "void_break",
        "dash_knives", "curtain",
    }
    used = {phase[1] for phases in _PHASE_CONFIGS.values() for phase in phases}
    assert used <= known


def test_enemy_bullet_supports_boss_special_shapes() -> None:
    from src.entities.bullets.enemy_bullet import EnemyBullet

    bullet = EnemyBullet(
        100.0,
        120.0,
        0.0,
        0.0,
        size=(80, 12),
        lifetime=0.1,
        terrain_passthrough=True,
        warning_only=True,
    )
    group = pygame.sprite.Group(bullet)

    assert bullet.rect.size == (80, 12)
    assert bullet.terrain_passthrough is True
    assert bullet.warning_only is True

    bullet.update(0.2)
    assert bullet not in group

    fading = EnemyBullet(
        100.0,
        120.0,
        0.0,
        0.0,
        size=(80, 24),
        lifetime=1.0,
        terrain_passthrough=True,
        warning_only=True,
        fade_shrink=True,
    )
    start_h = fading.rect.height
    fading.update(0.5)
    assert fading.rect.height < start_h
    assert fading.image.get_alpha() is not None and fading.image.get_alpha() < 255


def test_broly_beam_has_charge_and_taper() -> None:
    src = (ROOT / "src" / "entities" / "enemies" / "broly.py").read_text(encoding="utf-8")

    # チャージ相 → 本体ビーム（粒子砲フレーム・先細りで消滅）の流れを担保する。
    assert "_fire_warning()" in src
    assert "warning_only=True" in src
    assert "_fire_charge_beam()" in src
    assert "zunda_charge_frames" in src      # ZUNDA粒子砲 冒頭のチャージ相
    assert "zunda_beam_frames" in src        # 本体ビーム→放電フレーム
    assert "LaserBeamSprite" in src          # 動画フレーム対応の本体ビーム
    assert "taper_time=" in src              # 発射終了後に徐々に細くなる


def test_laser_beam_is_persistent_and_not_cancelled_on_contact() -> None:
    from src.entities.bullets.laser_fx import BOSS_PALETTE, LaserBeamSprite

    beam = LaserBeamSprite(300.0, 200.0, 400, 60, palette=BOSS_PALETTE,
                           lifetime=0.6, damage=20, warning_only=False)
    # 連続レーザーは接触で相殺・消滅しない（永続フラグ）かつ地形貫通。
    assert beam.persistent is True
    assert beam.terrain_passthrough is True

    # game_scene の相棒（カロナール）相殺ループは persistent を除外している。
    src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    assert 'getattr(bullet, "persistent", False)' in src


def test_boss_turret_guard_blocks_core_damage() -> None:
    from src.entities.enemies.boss import Boss

    class Resources:
        def image(self, path: str) -> pygame.Surface:
            return pygame.Surface((80, 60), pygame.SRCALPHA)

        def pixelfont(self, size: int):
            return pygame.font.Font(None, size)

    class Sound:
        def play_se_alias(self, *args, **kwargs) -> None:
            pass

    class Game:
        resources = Resources()
        sound = Sound()

    class ShieldNode:
        def alive(self) -> bool:
            return True

    boss = Boss(Game(), 3)
    boss._summoned = [ShieldNode()]
    hp = boss.hp

    assert boss.suppresses_hit_feedback() is True
    assert boss.take_damage(10) is False
    assert boss.hp == hp

    boss._summoned = []
    boss._stun_timer = 1.0
    assert boss.take_damage(10) is False
    assert boss.hp < hp


def test_boss_rock_fall_bypasses_terrain_collision() -> None:
    from src.entities.enemies.boss import Boss

    class Resources:
        def image(self, path: str) -> pygame.Surface:
            return pygame.Surface((80, 60), pygame.SRCALPHA)

        def pixelfont(self, size: int):
            return pygame.font.Font(None, size)

    class Sound:
        def play_se_alias(self, *args, **kwargs) -> None:
            pass

    class Game:
        resources = Resources()
        sound = Sound()

    boss = Boss(Game(), 4)
    rock = boss._rock_bullet(120.0, 220.0)

    assert rock.terrain_passthrough is True


def test_matching_zero_summons_real_shield_drones() -> None:
    from src.entities.enemies.boss_drone import MatchingZeroDrone
    from src.scenes.game_scene import GameScene

    class Resources:
        def image(self, path: str) -> pygame.Surface:
            return pygame.Surface((80, 72), pygame.SRCALPHA)

    class Sound:
        def play_se_alias(self, *args, **kwargs) -> None:
            pass

    class Game:
        resources = Resources()
        sound = Sound()

    class BossStub:
        rect = pygame.Rect(560, 240, 120, 120)

    class PlayerStub:
        sx = 140.0
        sy = 300.0

    scene = object.__new__(GameScene)
    scene.game = Game()
    scene._boss = BossStub()
    scene._boss_stage_id = lambda: 3
    scene.enemy_bullets = pygame.sprite.Group()
    scene.player = PlayerStub()
    scene.enemies = pygame.sprite.Group()

    spawned = GameScene._summon_boss_turrets(scene, 3)

    assert len(spawned) == 3
    assert all(isinstance(d, MatchingZeroDrone) for d in spawned)
    assert all(d.alive() for d in spawned)


def test_matching_zero_drone_tracks_boss_and_can_be_destroyed() -> None:
    from src.entities.enemies.boss_drone import MatchingZeroDrone

    class Resources:
        def image(self, path: str) -> pygame.Surface:
            return pygame.Surface((80, 72), pygame.SRCALPHA)

    class Sound:
        def play_se_alias(self, *args, **kwargs) -> None:
            pass

    class Game:
        resources = Resources()
        sound = Sound()

    class Camera:
        def to_world_x(self, sx: float) -> float:
            return sx + 1000.0

    class BossStub:
        rect = pygame.Rect(560, 240, 120, 120)

    drone = MatchingZeroDrone(Game(), BossStub(), 0)
    drone.update(0.1, Camera())

    assert drone.requires_laser is False
    assert drone.rect.centerx < BossStub.rect.centerx
    assert drone.world_x == drone.rect.centerx + 1000.0
    assert drone.drops_enabled is False
    assert drone.drop_chance == 0.0
    assert drone.take_damage(12) is True


def test_matching_zero_rear_drone_requires_laser_damage() -> None:
    from src.entities.enemies.boss_drone import MatchingZeroDrone

    class Resources:
        def image(self, path: str) -> pygame.Surface:
            return pygame.Surface((80, 72), pygame.SRCALPHA)

    class Sound:
        def play_se_alias(self, *args, **kwargs) -> None:
            pass

    class Game:
        resources = Resources()
        sound = Sound()

    class BossStub:
        rect = pygame.Rect(560, 240, 120, 120)

    drone = MatchingZeroDrone(Game(), BossStub(), 1)
    hp = drone.hp

    assert drone.requires_laser is True
    assert drone.blocks_projectile_damage(object()) is True
    assert drone.take_damage(99) is False
    assert drone.hp == hp
    assert drone.take_laser_damage(hp) is True


def test_spawner_surface_positions_follow_bottom_terrain() -> None:
    from src.core.camera import Camera
    from src.entities.terrain import make_terrain_strip
    from src.stages.spawner import EnemySpawner

    camera = Camera()
    terrain_segments = make_terrain_strip(
        camera.spawn_x() - 32,
        length=256,
        segment_w=64,
        seed=5,
        gap_min=380,
        gap_max=380,
    )
    terrain = pygame.sprite.Group(*terrain_segments)
    spawner = EnemySpawner(
        game=None,
        enemies=pygame.sprite.Group(),
        enemy_bullets=pygame.sprite.Group(),
        events=[],
        player=object(),
        terrain=terrain,
    )

    wx, wy = spawner._surface_positions(1, "bottom", camera, offset=24.0, step=56.0)[0]
    surface_y = spawner._surface_y_at(wx, "bottom")
    assert surface_y is not None
    assert wy == surface_y - 24.0


def test_laser_beam_blocks_at_terrain() -> None:
    from src.entities.laser_beam import LaserBeam
    from src.entities.terrain import Terrain

    laser = LaserBeam()
    laser.state = "firing"
    laser._beam_progress = 1.0
    laser._width_progress = 1.0
    terrain = Terrain(240, 110, 48, 80)

    laser.hit_check(
        pygame.sprite.Group(),
        None,
        120.0,
        140.0,
        terrain=pygame.sprite.Group(terrain),
    )

    assert laser._terrain_block_x == terrain.rect.left
    assert laser.terrain_hit is not None
    assert laser.terrain_hit[0] is terrain


def test_laser_beam_reports_boss_kill() -> None:
    from src.entities.laser_beam import LaserBeam

    class BossStub:
        def __init__(self) -> None:
            self.rect = pygame.Rect(260, 120, 80, 80)
            self._form2 = False
            self._form3 = False

        def suppresses_hit_feedback(self) -> bool:
            return False

        def take_damage(self, amount: int, stance: float | None = None) -> bool:
            return amount >= 1

    laser = LaserBeam()
    laser.state = "firing"
    laser._beam_progress = 1.0
    laser._width_progress = 1.0
    killed, hit, boss_killed = laser.hit_check(
        pygame.sprite.Group(),
        BossStub(),
        120.0,
        160.0,
    )

    assert killed == []
    assert hit is True
    assert boss_killed is True
    assert laser.boss_killed is True


def test_laser_beam_uses_laser_specific_enemy_damage() -> None:
    from src.entities.laser_beam import LaserBeam

    class LaserOnlyEnemy(pygame.sprite.Sprite):
        def __init__(self) -> None:
            super().__init__()
            self.image = pygame.Surface((30, 30), pygame.SRCALPHA)
            self.rect = self.image.get_rect(center=(250, 140))

        def take_damage(self, amount: int) -> bool:
            raise AssertionError("normal damage should be blocked")

        def take_laser_damage(self, amount: int) -> bool:
            return True

    enemy = LaserOnlyEnemy()
    laser = LaserBeam()
    laser.state = "firing"
    laser._beam_progress = 1.0
    laser._width_progress = 1.0

    killed, hit, boss_killed = laser.hit_check(
        pygame.sprite.Group(enemy),
        None,
        120.0,
        140.0,
    )

    assert killed == [enemy]
    assert hit is True
    assert boss_killed is False


def test_project_text_files_are_utf8_and_mojibake_free() -> None:
    from tools.dev_env import text_integrity_issues

    assert text_integrity_issues(ROOT) == []


def test_project_runner_prefers_utf8_and_venv() -> None:
    src = (ROOT / "tools" / "run.py").read_text(encoding="utf-8")
    assert "PYTHONIOENCODING" in src
    assert ".venv" in src
    assert "stage3-composer-report" in src
    assert "stage-terrain-composer" in src
    assert "stage-composer-report" in src
    assert "stage-designer" in src
    assert "stage-rect-preview" in src
    assert "stage-rect-editor" in src
    assert "stage-alpha-mask-editor" in src
    assert "stage3-rect-preview" in src
    assert "stage3-rect-editor" in src
    assert "stage3-alpha-mask-editor" in src


def test_stage_designer_formats_stage_json_for_hand_editing() -> None:
    from tools.stage_designer import _format_stage_json

    data = json.loads((ROOT / "data" / "stages" / "stage3.json").read_text(encoding="utf-8"))
    text = _format_stage_json(data)
    first_event = data["world_events"][0]
    first_event_text = json.dumps(first_event, ensure_ascii=False, separators=(", ", ": "))

    assert json.loads(text) == data
    assert '        {"asset": "strip_top:' in text
    assert f"    {first_event_text}" in text
    if "x" in first_event:
        assert f'\n          "x": {first_event["x"]}' not in text


def test_stage_designer_stage_profiles_select_stage_defaults() -> None:
    from tools.stage_designer import DEFAULT_MASK_DIR, DEFAULT_RECTS, _parse_args, _profile_from_args, _profile_path

    default_profile = _profile_from_args(_parse_args([]))
    stage1_profile = _profile_from_args(_parse_args(["--stage", "1"]))
    stage2_profile = _profile_from_args(_parse_args(["--stage", "2"]))
    inferred_stage1_profile = _profile_from_args(
        _parse_args(["--stage-json", str(ROOT / "data" / "stages" / "stage1.json")])
    )
    inferred_stage2_profile = _profile_from_args(
        _parse_args(["--stage-json", str(ROOT / "data" / "stages" / "stage2.json")])
    )

    assert default_profile.stage_id == 3
    assert stage1_profile.stage_id == 1
    assert inferred_stage1_profile is stage1_profile
    assert stage1_profile.stage_json == ROOT / "data" / "stages" / "stage1.json"
    assert stage1_profile.rects == ROOT / "tools" / "stage1_terrain_rects.json"
    assert stage1_profile.mask_dir == ROOT / "tools" / "stage1_terrain_alpha_masks"
    assert stage1_profile.background == ROOT / "assets" / "graphic" / "stage1_fever_corridor_bg.png"
    assert stage1_profile.terrain_kind == "clot"
    assert stage2_profile.stage_id == 2
    assert inferred_stage2_profile.stage_id == 2
    assert stage2_profile.stage_json == ROOT / "data" / "stages" / "stage2.json"
    assert stage2_profile.rects == ROOT / "tools" / "stage2_terrain_rects.json"
    assert _profile_path(stage2_profile.rects, stage2_profile.fallback_rects) == stage2_profile.rects
    assert stage2_profile.fallback_rects == DEFAULT_RECTS
    assert stage2_profile.fallback_mask_dir == DEFAULT_MASK_DIR
    assert stage2_profile.background == ROOT / "assets" / "graphic" / "stage2_cyber_static_bg.png"
    assert stage2_profile.terrain_kind == "data_block"


def test_stage_designer_stage2_event_palette_uses_data_blocks() -> None:
    from tools.stage_designer import Selection, StageDesigner, _event_templates_for_kind

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainStrip", "length": 1000}], "world_events": []}
    designer.event_templates = _event_templates_for_kind("data_block")
    designer.selection = None
    designer.message = ""
    designer.dirty = False
    designer.undo_stack = []

    index = next(i for i, (name, _template) in enumerate(designer.event_templates) if name == "solid block")
    designer._add_event_template_at(index, 120, 240)

    assert designer.data["world_events"][0]["kind"] == "data_block"
    assert designer.selection == Selection("event", 0)


def test_stage_designer_stage2_block_previews_use_rect_roles() -> None:
    from tools.stage_designer import Selection, StageDesigner, _event_material_role, _event_templates_for_kind, _piece_asset_id

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainStrip", "length": 1000}], "world_events": []}
    designer.rects_path = ROOT / "tools" / "stage2_terrain_rects.json"
    designer.mask_dir = ROOT / "tools" / "stage2_terrain_alpha_masks"
    designer.event_templates = _event_templates_for_kind("data_block")
    designer.selection = None
    designer.message = ""
    designer.dirty = False
    designer.undo_stack = []
    designer._composer_piece_cache_key = None
    designer._composer_piece_cache = None

    expected = {
        "solid block": "fixed_floor_block",
        "ceiling block": "fixed_ceiling_block",
        "turret mount": "turret_mount",
        "breakable gate": "breakable_block",
        "weapon gate": "breakable_block",
    }
    templates = dict(_event_templates_for_kind("data_block"))

    for name, role in expected.items():
        event = templates[name]
        image = designer._event_rect_image(event, int(event["w"]), int(event["h"]))
        piece = designer._event_rect_piece(event, int(event["w"]), int(event["h"]))
        role_images = [piece.image for piece in designer._composer_pieces()[role]]

        assert _event_material_role(event) == role
        assert any(image is role_image for role_image in role_images)
        assert image.get_size() == piece.image.get_size()

    index = next(i for i, (name, _event) in enumerate(designer.event_templates) if name == "weapon gate")
    designer._add_event_template_at(index, 420, 180)
    added = designer.data["world_events"][0]
    added_piece = designer._event_rect_piece(added, int(added["w"]), int(added["h"]))

    assert added["material_role"] == "breakable_block"
    assert added["material_asset"] == _piece_asset_id(added_piece)
    assert (added["w"], added["h"]) == added_piece.image.get_size()
    assert designer.selection == Selection("event", 0)


def test_stage_designer_stage1_clot_assets_keep_authored_dimensions() -> None:
    from tools.stage_designer import Selection, StageDesigner, _event_templates_for_kind

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainStrip", "length": 1000}], "world_events": []}
    designer.rects_path = ROOT / "tools" / "stage1_terrain_rects.json"
    designer.mask_dir = ROOT / "tools" / "stage1_terrain_alpha_masks"
    designer.event_templates = _event_templates_for_kind("clot")
    designer.selection = None
    designer.message = ""
    designer.dirty = False
    designer.undo_stack = []
    designer._composer_piece_cache_key = None
    designer._composer_piece_cache = None

    templates = dict(designer.event_templates)
    for name in ("solid block", "ceiling block", "turret mount", "breakable gate", "weapon gate"):
        event = templates[name]
        size = (int(event["w"]), int(event["h"]))
        image = designer._event_rect_image(event, *size)

        assert image is not None
        assert image.get_size() == size

    template = templates["weapon gate"]
    original_size = (int(template["w"]), int(template["h"]))
    index = next(i for i, (name, _event) in enumerate(designer.event_templates) if name == "weapon gate")
    designer._add_event_template_at(index, 420, 180)
    added = designer.data["world_events"][0]

    assert added["material_role"] == "breakable_block"
    assert added["material_asset"].startswith("clot_gate:")
    assert (added["w"], added["h"]) == original_size
    assert designer.selection == Selection("event", 0)

    for invalid_asset in ("", "invalid", "unknown:1", 123):
        invalid = {**template, "material_asset": invalid_asset}
        assert designer._event_rect_piece(invalid, *original_size) is None


def test_stage2_data_block_runtime_uses_rect_material_asset() -> None:
    from src.entities.stage3_composer_terrain import load_stage3_composer_pieces
    from src.entities.terrain import Terrain

    pieces = load_stage3_composer_pieces(
        ROOT / "tools" / "stage2_terrain_rects.json",
        mask_dir=ROOT / "tools" / "stage2_terrain_alpha_masks",
    )
    piece = pieces["turret_mount"][0]
    terrain = Terrain(
        0,
        0,
        piece.image.get_width(),
        piece.image.get_height(),
        "data_block",
        material_role="turret_mount",
        material_asset=f"{piece.group}:{piece.index + 1}",
    )

    assert terrain.image.get_size() == piece.image.get_size()
    assert terrain.image.get_at((10, 10)) == piece.image.get_at((10, 10))


def test_stage_designer_piece_palette_uses_stable_asset_identity() -> None:
    from types import SimpleNamespace

    import pygame

    from tools.stage_designer import StageDesigner

    pygame.font.init()
    designer = StageDesigner.__new__(StageDesigner)
    designer.mode = "terrain"
    designer.piece_palette_role = "floor_surface"
    designer.font = pygame.font.Font(None, 16)
    designer.small_font = pygame.font.Font(None, 13)
    designer._piece_preview_cache = {}

    image = pygame.Surface((220, 80), pygame.SRCALPHA)
    selected_piece = SimpleNamespace(group="strip_top", index=0, image=image)
    visible_piece = SimpleNamespace(group="strip_top", index=0, image=image)
    designer._current_piece_role = lambda: "floor_surface"  # type: ignore[method-assign]
    designer._current_piece_asset = lambda: selected_piece  # type: ignore[method-assign]

    target = pygame.Surface((180, 96), pygame.SRCALPHA)
    rect = pygame.Rect(8, 8, 120, 76)
    designer._draw_piece_cell(target, rect, "floor_surface", visible_piece)
    cached_preview = next(iter(designer._piece_preview_cache.values()))
    designer._draw_piece_cell(target, rect, "floor_surface", visible_piece)

    assert target.get_at(rect.topleft)[:3] == (91, 232, 188)
    assert next(iter(designer._piece_preview_cache.values())) is cached_preview


def test_stage_designer_caches_strip_composer_layout_across_scroll() -> None:
    from tools.stage_designer import StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {
        "stage_id": 2,
        "terrain_layout": [
            {
                "type": "TerrainStrip",
                "length": 1200,
                "segment_w": 48,
                "seed": 202,
                "gap_min": 358,
                "gap_max": 468,
                "center_y": 300,
                "center_wave": 88,
                "top_min": 24,
                "bottom_min": 28,
                "irregularity": 78,
                "start_offset": -90,
            }
        ],
        "world_events": [],
    }
    designer.rects_path = ROOT / "tools" / "stage2_terrain_rects.json"
    designer.mask_dir = ROOT / "tools" / "stage2_terrain_alpha_masks"
    designer._terrain_cache_key = None
    designer._terrain_cache = None
    designer._composer_layout_cache_key = None
    designer._composer_layout_cache = None
    designer._piece_layout_cache_key = None
    designer._piece_layout_cache = None

    first = designer._composer_layout()
    designer.camera_x = 420.0
    second = designer._composer_layout()

    assert second is first
    assert [placement.asset for placement in second.placements] == [placement.asset for placement in first.placements]


def test_stage_designer_moves_boss_gate_as_one_unit() -> None:
    from tools.stage_designer import _set_event_x

    gate = {
        "type": "BossGate",
        "trigger_x": 10150,
        "lock_camera_x": 9350,
        "player_limit_x": 10150,
    }

    _set_event_x(gate, 10200)

    assert gate == {
        "type": "BossGate",
        "trigger_x": 10200,
        "lock_camera_x": 9400,
        "player_limit_x": 10200,
    }


def test_stage_designer_adds_duplicates_and_deletes_terrain_pieces() -> None:
    from tools.stage_designer import Selection, StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {
        "terrain_layout": [
            {"type": "TerrainPieces", "renderer": "stage3_composer", "pieces": []}
        ],
        "world_events": [],
    }
    designer.rects_path = ROOT / "tools" / "stage3_terrain_rects.json"
    designer.mask_dir = ROOT / "tools" / "stage3_alpha_masks"
    designer.mode = "terrain"
    designer.selection = None
    designer.message = ""
    designer.dirty = False
    designer.undo_stack = []
    designer._terrain_cache_key = None
    designer._terrain_cache = None
    designer.piece_palette_role = "floor_surface"
    designer.piece_palette_index = 0

    designer._add_piece_at(120, 240)
    piece = designer.data["terrain_layout"][0]["pieces"][0]

    assert piece["asset"].startswith("strip_top:")
    assert piece["role"] == "floor_surface"
    assert piece["collision"] == "surface"
    assert piece["side"] == "bottom"
    assert designer.selection == Selection("piece", 0)

    original_asset = piece["asset"]
    designer._cycle_piece_asset(1)
    assert designer.data["terrain_layout"][0]["pieces"][0]["asset"] != original_asset or len(
        designer._piece_palette_options("floor_surface")
    ) == 1

    designer._cycle_selected_piece_collision()
    assert designer.data["terrain_layout"][0]["pieces"][0]["collision"] == "rect"

    designer._duplicate_selection()
    pieces = designer.data["terrain_layout"][0]["pieces"]
    assert len(pieces) == 2
    assert pieces[1]["x"] == pieces[0]["x"] + 48
    assert pieces[1]["y"] == pieces[0]["y"] + 24

    designer._delete_selection()
    assert len(designer.data["terrain_layout"][0]["pieces"]) == 1

    designer._add_palette_payload_at({"kind": "piece", "role": "ceiling_surface", "asset": "strip_top:2"}, 210, -40)
    added = designer.data["terrain_layout"][0]["pieces"][-1]
    assert added["asset"] == "strip_top:2"
    assert added["role"] == "ceiling_surface"
    assert added["side"] == "top"
    assert added["flip_y"] is True


def test_stage1_designer_flip_toggle_uses_effective_default() -> None:
    from tools.stage_designer import Selection, StageDesigner
    from tools.stage_terrain_profiles import STAGE_TERRAIN_PROFILES

    designer = StageDesigner.__new__(StageDesigner)
    designer.profile = STAGE_TERRAIN_PROFILES[1]
    designer.data = {"terrain_layout": [{"type": "TerrainPieces", "pieces": [
        {"asset": "vessel_surface:1", "x": 0, "y": 0, "role": "ceiling_surface", "collision": "surface", "side": "top"}
    ]}], "world_events": []}
    designer.selection = Selection("piece", 0)
    designer.selections = [designer.selection]
    designer.undo_stack = []
    designer.dirty = False
    designer.message = ""
    designer._terrain_cache_key = None
    designer._terrain_cache = None

    piece = designer.data["terrain_layout"][0]["pieces"][0]
    assert designer._effective_piece_flip(piece, "y") is False
    designer._toggle_selected_piece_flip("y")
    assert piece["flip_y"] is True
    designer._toggle_selected_piece_flip("y")
    assert piece["flip_y"] is False


def test_stage_designer_multi_selection_operations_and_layers() -> None:
    from tools.stage_designer import Selection, StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainPieces", "pieces": [
        {"asset": "a:1", "x": 0, "y": 0, "draw_order": 1},
        {"asset": "a:2", "x": 90, "y": 0, "draw_order": 9},
        {"asset": "a:2", "x": 10, "y": 10},
        {"asset": "a:3", "x": 20, "y": 20},
        {"asset": "a:4", "x": 30, "y": 30},
    ]}], "world_events": []}
    designer.selection = Selection("piece", 2)
    designer.selections = [Selection("piece", 1), Selection("piece", 2)]
    designer.undo_stack = []
    designer.dirty = False
    designer.message = ""
    designer._terrain_cache_key = None
    designer._terrain_cache = None

    designer._move_selection(5, -2)
    pieces = designer.data["terrain_layout"][0]["pieces"]
    assert [(pieces[i]["x"], pieces[i]["y"]) for i in (1, 2)] == [(95, -2), (15, 8)]
    designer._move_piece_layers(1, to_edge=True)
    assert [piece["asset"] for piece in pieces] == ["a:1", "a:3", "a:4", "a:2", "a:2"]
    designer._duplicate_selection()
    assert len(pieces) == 7
    assert [piece["asset"] for piece in pieces[-2:]] == ["a:2", "a:2"]
    designer._delete_selection()
    assert len(pieces) == 5


def test_stage_designer_interleaves_piece_and_destructible_terrain_layers() -> None:
    from tools.stage_designer import Selection, StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainPieces", "pieces": [
        {"asset": "a:1", "x": 0, "y": 0},
        {"asset": "a:2", "x": 40, "y": 0},
    ]}], "world_events": [
        {"type": "breakable_gate", "x": 20, "y": 0, "w": 30, "h": 30, "kind": "clot", "hp": 4},
        {"type": "EnemyVirus", "x": 100, "count": 1},
    ]}
    designer.selection = Selection("event", 0)
    designer.selections = [Selection("piece", 0), Selection("event", 0)]
    designer.undo_stack = []
    designer.dirty = False
    designer.message = ""
    designer._terrain_cache_key = None
    designer._terrain_cache = None
    designer._composer_layout_cache_key = None
    designer._composer_layout_cache = None
    designer._piece_layout_cache_key = None
    designer._piece_layout_cache = None

    designer._move_terrain_layers(1, to_edge=True)

    piece = designer.data["terrain_layout"][0]["pieces"][0]
    gate = designer.data["world_events"][0]
    assert piece["draw_order"] > designer.data["terrain_layout"][0]["pieces"][1]["draw_order"]
    assert gate["draw_order"] > designer.data["terrain_layout"][0]["pieces"][1]["draw_order"]
    assert "draw_order" not in designer.data["world_events"][1]


def test_stage_designer_ctrl_drag_copies_selected_group_after_drag_threshold() -> None:
    from tools.stage_designer import Selection, StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainPieces", "pieces": [
        {"asset": "a:1", "x": 0, "y": 0},
    ]}], "world_events": []}
    designer.selection = None
    designer.selections = []
    designer.guide_mode = False
    designer.panning = False
    designer.palette_drag = None
    designer.marquee_start = None
    designer.marquee_current = None
    designer.drag_offset = pygame.Vector2(0, 0)
    designer.drag_start_world = pygame.Vector2(0, 0)
    designer.drag_origins = {}
    designer.undo_stack = []
    designer.dirty = False
    designer.message = ""
    designer._terrain_cache_key = None
    designer._terrain_cache = None
    designer._composer_layout_cache_key = None
    designer._composer_layout_cache = None
    designer._piece_layout_cache_key = None
    designer._piece_layout_cache = None
    designer._update_cursor_world = lambda _pos: None
    designer._screen_to_world = lambda pos: (float(pos[0]), float(pos[1] - 48))

    def select_piece(_pos, *, toggle: bool = False):
        selected = Selection("piece", 0)
        if toggle:
            designer._set_selections([selected])
        else:
            designer._set_selections([selected])
        return selected

    designer._select_at = select_piece
    pygame.key.set_mods(pygame.KMOD_CTRL)
    try:
        designer._handle_mouse_down(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(20, 68)))
        designer._handle_mouse_motion(pygame.event.Event(pygame.MOUSEMOTION, pos=(50, 98)))
        designer._handle_mouse_up(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(50, 98)))
    finally:
        pygame.key.set_mods(0)

    pieces = designer.data["terrain_layout"][0]["pieces"]
    assert len(pieces) == 2
    assert (pieces[0]["x"], pieces[0]["y"]) == (0, 0)
    assert (pieces[1]["x"], pieces[1]["y"]) == (30, 30)
    assert pieces[1]["draw_order"] == max(piece["draw_order"] for piece in pieces)
    assert len(designer.undo_stack) == 1


def test_stage_designer_ctrl_drag_copies_multi_selection_to_front_in_z_order() -> None:
    from tools.stage_designer import Selection, StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainPieces", "pieces": [
        {"asset": "a:1", "x": 0, "y": 0, "draw_order": 5},
        {"asset": "a:2", "x": 30, "y": 0, "draw_order": 2},
    ]}], "world_events": [
        {"type": "breakable_gate", "x": 10, "y": 0, "w": 20, "h": 20, "kind": "clot", "draw_order": 4},
        {"type": "breakable_gate", "x": 80, "y": 0, "w": 20, "h": 20, "kind": "clot", "draw_order": 9},
    ]}
    designer.selection = Selection("event", 0)
    designer.selections = [Selection("piece", 0), Selection("event", 0)]
    designer.undo_stack = []
    designer.dirty = False
    designer.message = ""
    designer._terrain_cache_key = None
    designer._terrain_cache = None
    designer._composer_layout_cache_key = None
    designer._composer_layout_cache = None
    designer._piece_layout_cache_key = None
    designer._piece_layout_cache = None

    designer._duplicate_selection(offset=False)
    designer._bring_selected_terrain_to_front()

    pieces = designer.data["terrain_layout"][0]["pieces"]
    events = designer.data["world_events"]
    copied_piece, copied_event = pieces[-1], events[-1]
    assert copied_event["draw_order"] == max(event["draw_order"] for event in events if event is not copied_event) + 1
    assert copied_piece["draw_order"] == copied_event["draw_order"] + 1
    assert copied_piece["draw_order"] == max([
        *(piece["draw_order"] for piece in pieces),
        *(event["draw_order"] for event in events),
    ])


def test_stage_designer_scales_rect_terrain_preview_with_zoom() -> None:
    from tools.stage_designer import StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer._event_image_cache = {}
    designer._event_rect_image = lambda _event, _w, _h: pygame.Surface((80, 40), pygame.SRCALPHA)
    event = {"type": "Terrain", "kind": "clot", "w": 80, "h": 40}

    palette_image = designer._event_image(event, max_w=160, max_h=80)
    image = designer._event_image(event, max_w=160, max_h=80, exact_rect_size=True)

    assert palette_image.get_size() == (80, 40)
    assert image.get_size() == (160, 80)


def test_stage_designer_defers_piece_layout_rebuild_while_dragging() -> None:
    from tools.stage_designer import Selection, StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainPieces", "pieces": [
        {"asset": "a:1", "x": 10, "y": 20},
    ]}], "world_events": []}
    designer.selection = Selection("piece", 0)
    designer.selections = [designer.selection]
    designer.dragging = True
    designer.drag_start_world = pygame.Vector2(10, 20)
    designer.drag_offset = pygame.Vector2(0, 0)
    designer.drag_origins = {}
    designer.dirty = False
    designer._drag_terrain_dirty = False
    cached_layout = object()
    designer._piece_layout_cache_key = "cached"
    designer._piece_layout_cache = cached_layout
    designer._terrain_cache_key = "cached"
    designer._terrain_cache = object()
    designer._composer_layout_cache_key = "cached"
    designer._composer_layout_cache = object()

    designer._set_selection_world_pos(75, 90)

    assert designer.data["terrain_layout"][0]["pieces"][0]["x"] == 75
    assert designer.data["terrain_layout"][0]["pieces"][0]["y"] == 90
    assert designer._piece_layout_cache is cached_layout
    assert designer._drag_terrain_dirty is True


def test_stage1_event_palette_can_restore_boss_gate_and_boss() -> None:
    from tools.stage_designer import Selection, StageDesigner, _event_templates_for_kind

    templates = dict(_event_templates_for_kind("clot"))
    assert templates["boss gate"] == {
        "type": "BossGate", "trigger_x": 7650, "lock_camera_x": 6850, "player_limit_x": 7650,
    }
    assert templates["boss appearance"] == {
        "type": "Boss", "x": 8100, "count": 1, "formation": "single", "preload": 0,
    }

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainPieces", "pieces": []}], "world_events": []}
    designer.event_templates = list(templates.items())
    designer.selection = None
    designer.undo_stack = []
    designer.dirty = False
    designer.message = ""
    gate_index = next(i for i, (name, _event) in enumerate(designer.event_templates) if name == "boss gate")
    designer._add_event_template_at(gate_index, 9000, 200)

    assert designer.selection == Selection("event", 0)
    assert designer.data["world_events"] == [{
        "type": "BossGate", "trigger_x": 9000, "lock_camera_x": 8200, "player_limit_x": 9000,
    }]


def test_stage_designer_draws_stage_bounds_even_when_overlays_are_off() -> None:
    from tools.stage_designer import SCREEN_HEIGHT, StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer.camera_y = 0.0
    designer.zoom = 1.0
    designer.small_font = pygame.font.Font(None, 13)
    target = pygame.Surface((320, SCREEN_HEIGHT), pygame.SRCALPHA)
    designer._draw_stage_bounds(target)

    assert target.get_at((40, 0))[:3] == (255, 174, 104)
    assert target.get_at((40, SCREEN_HEIGHT - 1))[:3] == (104, 218, 255)


def test_stage_designer_layer_reorder_reuses_loaded_piece_atlas(monkeypatch: pytest.MonkeyPatch) -> None:
    import tools.stage_designer as designer_module
    from tools.stage_designer import StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainPieces", "pieces": [
        {"asset": "vessel_surface:1", "x": 0, "y": 400, "role": "floor_surface", "side": "bottom"},
    ]}], "world_events": []}
    designer.rects_path = ROOT / "tools" / "stage1_terrain_rects.json"
    designer.mask_dir = ROOT / "tools" / "stage1_terrain_alpha_masks"
    designer._composer_piece_cache_key = None
    designer._composer_piece_cache = None
    designer._piece_preview_cache = {}
    designer._piece_layout_cache_key = None
    designer._piece_layout_cache = None

    _layout_before, atlas = designer._piece_layout()
    designer.data["terrain_layout"][0]["pieces"][0]["draw_order"] = 1
    designer._piece_layout_cache_key = None
    designer._piece_layout_cache = None
    monkeypatch.setattr(designer_module, "load_stage3_composer_pieces", lambda *_args, **_kwargs: pytest.fail("atlas reload"))

    _layout_after, reused_atlas = designer._piece_layout()
    assert reused_atlas is atlas


def test_stage1_organic_autofill_uses_overlapping_ordered_bands() -> None:
    from tools.stage_designer import StageDesigner
    from tools.stage_terrain_profiles import STAGE_TERRAIN_PROFILES

    designer = StageDesigner.__new__(StageDesigner)
    designer.profile = STAGE_TERRAIN_PROFILES[1]
    designer.rects_path = ROOT / "tools" / "stage1_terrain_rects.json"
    designer.mask_dir = ROOT / "tools" / "stage1_terrain_alpha_masks"
    designer._composer_piece_cache_key = None
    designer._composer_piece_cache = None
    designer._piece_preview_cache = {}
    generated = designer._stage1_organic_autofill([[0, 440], [600, 460]], "bottom", 0, 600)

    assets = [piece["asset"].split(":", 1)[0] for piece in generated]
    bands = [piece["auto_fill_band"] for piece in generated]
    assert assets[0] == "vessel_surface"
    assert "vessel_fill" not in assets
    assert bands == sorted(bands)
    assert {piece["flip_y"] for piece in generated if piece["auto_fill_band"] == 0} == {True}
    surface = [piece for piece in generated if piece["auto_fill_band"] == 0]
    assert surface[1]["x"] - surface[0]["x"] < 239


def test_stage_designer_adds_duplicates_and_deletes_events_from_palette() -> None:
    from tools.stage_designer import EVENT_TEMPLATES, Selection, StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainPieces", "pieces": []}], "world_events": []}
    designer.mode = "events"
    designer.selection = None
    designer.message = ""
    designer.dirty = False
    designer.undo_stack = []
    designer.event_palette_index = next(i for i, (name, _template) in enumerate(EVENT_TEMPLATES) if name == "solid block")

    designer._add_event_at(320, 360)
    event = designer.data["world_events"][0]

    assert event == {"type": "Terrain", "x": 320, "y": 360, "w": 140, "h": 92, "kind": "fortress_block"}
    assert designer.selection == Selection("event", 0)

    designer._duplicate_selection()
    events = designer.data["world_events"]
    assert len(events) == 2
    assert events[1]["x"] == 416
    assert events[1]["y"] == 384

    designer._delete_selection()
    assert len(designer.data["world_events"]) == 1

    designer._add_palette_payload_at({"kind": "event", "template_index": designer.event_palette_index}, 500, 410)
    assert designer.data["world_events"][-1]["x"] == 500


def test_stage_designer_event_palette_uses_enemy_type_once_and_edits_variants() -> None:
    from tools.stage_designer import EVENT_TEMPLATES, Selection, StageDesigner

    enemy_templates = [
        template
        for _name, template in EVENT_TEMPLATES
        if str(template.get("type", "")).startswith("Enemy")
    ]
    enemy_types = [template["type"] for template in enemy_templates]

    assert enemy_types.count("EnemyVirus") == 1
    assert enemy_types.count("EnemyTakeshi") == 1
    assert enemy_types.count("EnemyPachemon") == 1
    assert {"EnemyBroly", "EnemyDebrisLarge", "EnemyCoughSprayer", "EnemySporeSplitter", "EnemyBilly"} <= set(enemy_types)

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {
        "terrain_layout": [{
            "type": "TerrainPieces",
            "pieces": [],
            "guide_top": [[0, 60], [500, 60]],
            "guide_bottom": [[0, 520], [500, 520]],
        }],
        "world_events": [{"type": "EnemyBroly", "x": 200, "count": 1, "formation": "single"}],
    }
    designer.rects_path = ROOT / "tools" / "stage3_terrain_rects.json"
    designer.mask_dir = ROOT / "tools" / "stage3_alpha_masks"
    designer._terrain_cache_key = None
    designer._terrain_cache = None
    designer.cursor_world = pygame.Vector2(200, 300)
    designer.selection = Selection("event", 0)
    designer.message = ""
    designer.undo_stack = []
    designer.dirty = False

    designer._adjust_selected_event_count(1)
    event = designer.data["world_events"][0]
    assert event["count"] == 2
    assert event["formation"] == "line"
    assert "anchor_y" in event

    designer._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SEMICOLON, unicode="+"))
    assert event["count"] == 3
    designer._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_MINUS, unicode="-"))
    assert event["count"] == 2

    designer._cycle_selected_event_formation()
    assert event["formation"] == "v_shape"

    designer._toggle_selected_event_enhanced()
    assert event["enhanced"] is True
    designer._toggle_selected_event_enhanced()
    assert "enhanced" not in event


def test_stage_designer_formats_and_autofills_guide_points() -> None:
    from tools.stage_designer import Selection, StageDesigner, _format_stage_json

    data = {
        "stage_id": 3,
        "terrain_layout": [{
            "type": "TerrainPieces",
            "theme": "fortress",
            "renderer": "stage3_composer",
            "composer_sample_step": 48,
            "composer_tolerance": 26,
            "composer_collision_step": 8,
            "composer_collision_tolerance": 10,
            "guide_top": [[0, 58], [240, 78], [480, 52]],
            "guide_bottom": [[0, 520], [240, 488], [480, 510]],
            "pieces": [{"asset": "strip_top:1", "x": 120, "y": 430, "role": "floor_surface", "collision": "surface", "side": "bottom"}],
        }],
        "world_events": [],
    }

    text = _format_stage_json(data)
    assert '"guide_top": [' in text
    assert "        [0, 58]," in text

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = copy = json.loads(json.dumps(data))
    designer.rects_path = ROOT / "tools" / "stage3_terrain_rects.json"
    designer.mask_dir = ROOT / "tools" / "stage3_alpha_masks"
    designer.selection = None
    designer.message = ""
    designer.dirty = False
    designer.undo_stack = []
    designer._terrain_cache_key = None
    designer._terrain_cache = None
    designer.selection = None

    designer._guide_lines()
    designer.selection = Selection("guide_line", 1)
    designer._auto_fill_from_guides()

    layout = copy["terrain_layout"][0]
    pieces = layout["pieces"]
    assert designer.dirty is True
    assert designer.undo_stack
    assert len(pieces) > 1
    assert any(piece["role"] == "floor_surface" for piece in pieces)
    assert all(piece.get("side") == "bottom" for piece in pieces)
    assert not any(piece.get("asset") == "strip_top:1" and piece.get("x") == 120 for piece in pieces)


def test_stage_designer_event_preview_positions_show_formations() -> None:
    from tools.stage_designer import StageDesigner

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {
        "terrain_layout": [{
            "type": "TerrainPieces",
            "pieces": [],
            "guide_top": [[0, 60], [500, 60]],
            "guide_bottom": [[0, 520], [500, 520]],
        }],
        "world_events": [],
    }
    designer.rects_path = ROOT / "tools" / "stage3_terrain_rects.json"
    designer.mask_dir = ROOT / "tools" / "stage3_alpha_masks"
    designer._terrain_cache_key = None
    designer._terrain_cache = None

    line = designer._event_preview_positions({"type": "EnemyTakeshi", "x": 200, "count": 3, "formation": "line"})
    v_shape = designer._event_preview_positions({"type": "EnemyPachemon", "x": 200, "count": 3, "formation": "v_shape"})
    surface = designer._event_preview_positions({"type": "EnemyCrawler", "x": 200, "count": 2, "surface": "bottom", "surface_offset": 22})

    assert len(line) == 3
    assert line[0][0] == line[1][0] == line[2][0]
    assert line[0][1] < line[1][1] < line[2][1]
    assert len(v_shape) == 3
    assert v_shape[0][1] < v_shape[1][1] < v_shape[2][1]
    assert len(surface) == 2
    assert all(y == 498 for _x, y in surface)


def test_stage_designer_selects_visible_event_previews_without_flattening_formations() -> None:
    from tools.stage_designer import Selection, StageDesigner, TOOLBAR_H

    pygame.display.set_mode((1, 1))
    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {
        "terrain_layout": [{
            "type": "TerrainPieces",
            "pieces": [],
            "guide_top": [[0, 60], [1000, 60]],
            "guide_bottom": [[0, 520], [1000, 520]],
        }],
        "world_events": [
            {"type": "EnemyDebrisLarge", "x": 200, "count": 1, "formation": "single"},
            {"type": "EnemyTakeshi", "x": 400, "count": 3, "formation": "line"},
        ],
    }
    designer.rects_path = ROOT / "tools" / "stage3_terrain_rects.json"
    designer.mask_dir = ROOT / "tools" / "stage3_alpha_masks"
    designer._terrain_cache_key = None
    designer._terrain_cache = None
    designer._event_image_cache = {}
    designer.camera_x = 0.0
    designer.camera_y = 0.0
    designer.zoom = 1.0
    designer.mode = "events"
    designer.selection = None
    designer.message = ""
    designer.drag_offset = pygame.Vector2(0, 0)
    designer.dirty = False

    debris_pos = designer._event_preview_positions(designer.data["world_events"][0])[0]
    designer._select_at((int(debris_pos[0]), int(debris_pos[1] + TOOLBAR_H)))
    assert designer.selection == Selection("event", 0)

    designer.selection = Selection("event", 1)
    before = designer._event_preview_positions(designer.data["world_events"][1])
    designer._set_selection_world_pos(460, 340)
    event = designer.data["world_events"][1]
    after = designer._event_preview_positions(event)

    assert event["x"] == 460
    assert "y" not in event
    assert event["anchor_y"] == 340
    assert before[0][1] < before[1][1] < before[2][1]
    assert after[0][1] < after[1][1] < after[2][1]


def test_stage_designer_guide_lines_can_be_created_edited_and_retyped() -> None:
    from tools.stage_designer import Selection, StageDesigner, TOOLBAR_H

    designer = StageDesigner.__new__(StageDesigner)
    designer.data = {"terrain_layout": [{"type": "TerrainPieces", "pieces": []}], "world_events": []}
    designer.guide_side = "bottom"
    designer.selection = None
    designer.message = ""
    designer.dirty = False
    designer.undo_stack = []
    designer.camera_x = 0.0
    designer.camera_y = 0.0
    designer.zoom = 1.0
    designer.drag_offset = pygame.Vector2(0, 0)
    designer.drag_start_world = pygame.Vector2(0, 0)
    designer.dragging = False

    designer._handle_guide_mouse_down((100, TOOLBAR_H + 420))
    designer._handle_guide_mouse_down((100, TOOLBAR_H + 430))
    designer._handle_guide_mouse_down((220, TOOLBAR_H + 450))

    line = designer.data["terrain_layout"][0]["guide_lines"][0]
    assert line["side"] == "bottom"
    assert line["points"] == [[100, 430], [220, 450]]

    designer.dragging = False
    designer._handle_guide_mouse_down((160, TOOLBAR_H + 440))
    assert designer.selection == Selection("guide_line", 0)

    designer.selection = Selection("guide_line", 0)
    designer._toggle_selected_guide_side()
    assert line["side"] == "top"

    designer.selection = Selection("guide_point", 0, sub_index=0)
    designer._delete_selection()
    assert line["points"] == [[220, 450]]


def test_stage3_composer_report_opens_preview_by_default() -> None:
    from tools import stage3_composer_report

    assert stage3_composer_report._parse_args([]).open_preview is True
    assert stage3_composer_report._parse_args(["--no-open"]).open_preview is False


def test_stage3_composer_report_uses_stage_composer_options() -> None:
    from tools import stage3_composer_report

    stage_path = ROOT / "data" / "stages" / "stage3.json"
    stage3 = json.loads(stage_path.read_text(encoding="utf-8"))
    layout = stage3["terrain_layout"][0]
    options = stage3_composer_report._composer_options(stage_path)

    assert options["sample_step"] == int(layout.get("composer_sample_step", 48))
    assert options["tolerance"] == int(layout.get("composer_tolerance", 26))
    assert options["collision_step"] == int(layout.get("composer_collision_step", 8))
    assert options["collision_tolerance"] == int(layout.get("composer_collision_tolerance", 10))


def test_settings_manager_ignores_wrong_json_shapes(tmp_path, monkeypatch) -> None:
    from src.managers import settings as settings_mod

    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "_SETTINGS_PATH", settings_path)

    settings_path.write_text("[]", encoding="utf-8")
    manager = settings_mod.SettingsManager()

    assert manager.get("bgm_volume") == 0.8
    assert manager.get_key("fire") == pygame.K_z

    settings_path.write_text(
        json.dumps({
            "bgm_volume": "loud",
            "se_volume": 1.5,
            "key_bindings": "K_SPACE",
        }),
        encoding="utf-8",
    )
    manager = settings_mod.SettingsManager()

    assert manager.get("bgm_volume") == 0.8
    assert manager.get("se_volume") == 1.0
    assert manager.get_key("fire") == pygame.K_z


def test_highscore_manager_filters_wrong_json_shapes(tmp_path, monkeypatch) -> None:
    from src.managers import highscore as highscore_mod

    highscore_path = tmp_path / "highscore.json"
    monkeypatch.setattr(highscore_mod, "_HIGHSCORE_PATH", highscore_path)

    highscore_path.write_text("{}", encoding="utf-8")
    assert highscore_mod.HighScoreManager().get_scores() == []

    highscore_path.write_text(
        json.dumps([
            {"name": "A", "score": "50", "stage": "2"},
            {"name": "bad", "score": "nan", "stage": 1},
            ["not", "a", "score"],
            {"name": "B", "score": 75, "stage": 3, "rank": 99},
        ]),
        encoding="utf-8",
    )

    assert highscore_mod.HighScoreManager().get_scores() == [
        {"name": "B", "score": 75, "stage": 3, "rank": 1},
        {"name": "A", "score": 50, "stage": 2, "rank": 2},
    ]


def test_manual_docs_do_not_reference_removed_items() -> None:
    design = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    for term in (
        "LaserItem", "HomingItem", "ShieldItem", "shield.py",
        "ScoreItem", "score_item.py", "ExtraLifeItem", "extra_life.py", "1UP",
    ):
        assert term not in design


def test_debug_f2_docs_match_implementation() -> None:
    tools_doc = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    debug_src = (ROOT / "src" / "scenes" / "game" / "debug_mixin.py").read_text(encoding="utf-8")
    assert "ウェポンアイテムをドロップ" in debug_src
    assert "ウェポンアイテムを自機前方にドロップ" in tools_doc


def test_boss_defense_gimmicks_suppress_hit_feedback() -> None:
    boss_src = (ROOT / "src" / "entities" / "enemies" / "boss.py").read_text(encoding="utf-8")
    game_src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    laser_src = (ROOT / "src" / "entities" / "laser_beam.py").read_text(encoding="utf-8")

    assert "def suppresses_hit_feedback" in boss_src
    assert "if dealt > 0:" in boss_src
    assert 'getattr(self._boss, "suppresses_hit_feedback"' in game_src
    assert 'getattr(boss, "suppresses_hit_feedback"' in laser_src


def test_companion_shoots_only_while_player_fires() -> None:
    player_src = (ROOT / "src" / "entities" / "player.py").read_text(encoding="utf-8")
    companion_src = (ROOT / "src" / "entities" / "companion.py").read_text(encoding="utf-8")

    assert "self.fire_held" in player_src
    assert 'getattr(player, "fire_held", False)' in companion_src


def test_companion_holds_fire_during_boss_intro() -> None:
    """ボス出現演出中（alert/entering）は先輩も射撃しない。

    自機弾は game_scene 側で `_combat_active` のときだけ生成されるため、
    先輩も同じゲートを共有しないと演出中だけ撃ててしまう。
    """
    from src.entities.companion import Karonaru

    class SoundStub:
        def play_se_alias(self, *_a, **_k) -> None:
            pass

    class GameStub:
        sound = SoundStub()

    class WeaponStub:
        speed_multiplier = 1.0

    class PlayerStub:
        rect = pygame.Rect(400, 300, 24, 32)
        weapon = WeaponStub()
        fire_held = True

    class CameraStub:
        x = 0.0

    companion = Karonaru(GameStub())
    player = PlayerStub()
    camera = CameraStub()
    bullets = pygame.sprite.Group()
    empty = pygame.sprite.Group()

    # クールダウンを使い切った直後でも、演出中は撃たない。
    companion._shoot_cooldown = 0.0
    companion.update(0.016, player, bullets, camera, empty, empty, None, can_fire=False)
    assert len(bullets) == 0

    # 戦闘中（can_fire=True）なら同じ条件で撃つ。
    companion._shoot_cooldown = 0.0
    companion.update(0.016, player, bullets, camera, empty, empty, None, can_fire=True)
    assert len(bullets) >= 1

    # game_scene は自機弾・先輩で同一の _combat_active ゲートを共有する
    # （状態テーブル _INTRO_BEHAVIOR から導出。両者が別条件に分岐しないことを保証）。
    scene_src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    assert "can_fire=self._combat_active" in scene_src   # 先輩側
    assert "if self._combat_active:" in scene_src        # 自機側


def test_boss_kill_clears_mid_dialogue_queue() -> None:
    src = (ROOT / "src" / "scenes" / "game" / "post_boss_mixin.py").read_text(encoding="utf-8")
    assert "self._boss_dialogue_timer = 0.0" in src
    assert "self._boss_dialogue_queue = []" in src


def test_boss_gimmick_draw_ignores_missing_boss() -> None:
    from src.scenes.game_scene import GameScene

    scene = object.__new__(GameScene)
    scene._boss = None
    GameScene._draw_boss_gimmick(scene, pygame.Surface((32, 32)))


def test_boss_intro_waits_for_midboss_cleanup_and_keeps_bgm() -> None:
    src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    spawner_src = (ROOT / "src" / "stages" / "spawner.py").read_text(encoding="utf-8")

    assert "_BOSS_GATE_ENEMIES" in src
    assert "EnemyCoughSprayer" in src
    assert "EnemySporeSplitter" in src
    assert "def _boss_gate_blocked" in src
    assert "def _hold_before_boss_room" in src
    assert "def _start_boss_alert" in src
    assert "boss_gate_pending" in src
    assert "player_limit_x" in src
    assert "clear_boss_gate" in spawner_src
    assert "self.camera.scroll_speed = 0.0" in src
    assert "play_bgm(BOSS_BGM.get" in src
    assert "play_bgm_if_new(BOSS_BGM.get" in src


def test_boss_gate_clamps_camera_and_player_before_room() -> None:
    from src.scenes.game_scene import GameScene

    class CameraStub:
        x = 2862.0
        scroll_speed = 80.0

    class PlayerStub:
        sx = 790.0
        sy = 120.0
        rect = pygame.Rect(790, 120, 24, 32)

    class SpawnerStub:
        boss_gate_event = {
            "lock_camera_x": 2850,
            "player_limit_x": 3650,
        }

    scene = object.__new__(GameScene)
    scene.camera = CameraStub()
    scene.player = PlayerStub()
    scene.spawner = SpawnerStub()

    GameScene._hold_before_boss_room(scene)

    assert scene.camera.x == 2850.0
    assert scene.camera.scroll_speed == 0.0
    assert scene.player.sx == 3650 - 2850 - scene.player.rect.width
    assert scene.camera.x + scene.player.rect.right <= 3650


def test_final_boss_post_defeat_does_not_require_extra_dialogue_wait() -> None:
    from src.scenes.game.config import POST_BOSS_FINAL_TIMEOUT

    src = (ROOT / "src" / "scenes" / "game" / "post_boss_mixin.py").read_text(encoding="utf-8")
    assert POST_BOSS_FINAL_TIMEOUT <= 2.5
    assert "[] if is_final else pages" in src
    assert "0.0 if is_final else" in src
    assert "FFVI_勝利のファンファーレ.mp3" in src


def test_stage3_blackhole_uses_actor_scene() -> None:
    # 承認欲求ブラックホールは専用の俳優シーン（BlackholeScene）で再生する。
    # 物語タイムラインの "3->4" ビートが scene="blackhole" を持ち、story_flow が
    # それを BlackholeScene に解決する。
    from src.story import script
    assert script.story_beat("3->4").scene == "blackhole"
    flow_src = (ROOT / "src" / "scenes" / "story_flow.py").read_text(encoding="utf-8")
    assert "BlackholeScene" in flow_src
    scene_src = (ROOT / "src" / "scenes" / "blackhole_scene.py").read_text(encoding="utf-8")
    assert "Player(self.game)" in scene_src
    assert "Karonaru(self.game)" in scene_src
    assert "_draw_pull_lines" not in scene_src


def test_credits_roll_fades_bgm_before_title() -> None:
    src = (ROOT / "src" / "scenes" / "credits_roll.py").read_text(encoding="utf-8")
    assert "stop_bgm(fadeout_ms=_FADEOUT_MS)" in src
    assert "self._fadeout_timer" in src
    assert "self._on_complete()" in src


def test_final_return_spawns_karonaru_before_dialogue() -> None:
    # 最終決戦の演出 SSOT は src/scenes/game/final_battle.py。
    # GameScene はそこへ委譲するだけなので、内部挙動は director を、
    # フェーズ検知の配線は GameScene を検査する。
    fb = (ROOT / "src" / "scenes" / "game" / "final_battle.py").read_text(encoding="utf-8")
    gs = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    spawn_at = fb.index("self._spawn_returning_karonaru()")
    dialogue_at = fb.index("self._play_final_dialogue(FINAL_SEQ[\"return\"]")
    assert spawn_at < dialogue_at
    assert "self._final.seq == \"return_join\"" in gs
    assert "self._final.draw_arrival_trail" in gs
    assert "def draw_arrival_trail" in fb
    assert "SE_KARONARU_ARRIVE" in fb
    assert "start = (-48.0, arrival_y)" in fb
    assert "self._karonaru_heal_player()" in fb
    assert "scene.player.hp = scene.player.max_hp" in fb
    assert "final_chance" in fb
    assert "KARONARU RETURNS" not in fb
    assert "KARONARU RETURNS" not in gs


def test_design_md_autogen_blocks_are_current() -> None:
    import subprocess
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_docs.py"), "--check"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"design.md の AUTOGEN ブロックが古い:\n{result.stderr.strip()}"
    )
