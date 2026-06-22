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
        "Terrain", "TerrainStrip", "solid", "platform", "gate", "breakable_gate",
        "weapon_gate", "turret_mount", "cave_section", "corridor",
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
    rect_terrain_types = {"Terrain", "solid", "platform", "gate", "breakable_gate", "weapon_gate", "turret_mount"}
    strip_terrain_types = {"TerrainStrip", "cave_section", "corridor"}
    from src.core.registries import ITEM_NAMES
    from src.entities.terrain import TERRAIN_STRIP_THEMES
    valid_strip_themes = set(TERRAIN_STRIP_THEMES)

    def assert_terrain_event(section: str, i: int, ev: dict) -> None:
        assert ev.get("type") in rect_terrain_types | strip_terrain_types, (
            f"{section}[{i}]: terrain section only allows Terrain/TerrainStrip"
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
        else:
            for field in ("length",):
                assert field in ev, f"{section}[{i}](TerrainStrip): missing '{field}'"
            assert ev.get("theme", "fever_cave") in valid_strip_themes, (
                f"{section}[{i}](TerrainStrip): unknown theme '{ev.get('theme', 'fever_cave')}'"
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
            if ev.get("type") == "Terrain":
                for field in ("y", "w", "h", "kind"):
                    assert field in ev, f"{p.name} events[{i}](Terrain): 必須フィールド '{field}' が欠如"
                assert ev["kind"] in valid_terrain_kinds, (
                    f"{p.name} events[{i}](Terrain): 未知の kind '{ev['kind']}'"
                )
            elif ev.get("type") == "TerrainStrip":
                for field in ("theme", "length"):
                    assert field in ev, f"{p.name} events[{i}](TerrainStrip): 必須フィールド '{field}' が欠如"
                assert ev["theme"] in valid_strip_themes, (
                    f"{p.name} events[{i}](TerrainStrip): 未知の theme '{ev['theme']}'"
                )
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
        for section in ("initial_terrain", "terrain_layout", "boss_terrain"):
            for i, ev in enumerate(data.get(section, [])):
                assert_terrain_event(f"{p.name} {section}", i, ev)


# ── ボス ─────────────────────────────────────────────────────────────

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
    assert stage.terrain_layout[0]["type"] == "TerrainStrip"
    assert stage.random_drop_scale == stage1_data["random_drop_scale"]
    assert stage2.initial_terrain == []
    assert stage2.terrain_layout
    assert stage2.random_drop_scale < 1.0
    assert stage3.initial_terrain == []
    assert stage3.terrain_layout
    assert stage3.random_drop_scale < 1.0
    assert stage4.initial_terrain == []
    assert stage4.terrain_layout
    assert stage4.random_drop_scale < 1.0
    assert any(ev["type"] == "EnemyTurret" and ev["x"] == 1710 for ev in stage.world_events)
    assert all(ev.get("type") != "EnemyTurret" for ev in stage.events)


def test_random_item_drops_use_stage_scale() -> None:
    src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")

    assert "def _random_drop_chance" in src
    assert "self._random_drop_chance(float(getattr(ter, \"drop_chance\", 0.0)))" in src
    assert "chance = self._random_drop_chance(getattr(enemy, \"drop_chance\"" in src


def test_stage1_uses_authored_blood_cell_setpieces() -> None:
    data = json.loads((ROOT / "data" / "stages" / "stage1.json").read_text(encoding="utf-8"))
    layout = data["terrain_layout"][0]
    world_events = data["world_events"]
    fixed_drop_chances = [
        float(ev.get("drop_chance", 0.0))
        for ev in world_events
        if ev.get("destructible") or ev.get("type") == "breakable_gate"
    ]
    first_enemy_x = min(ev["x"] for ev in world_events if ev["type"].startswith("Enemy"))
    turrets = [ev for ev in world_events if ev["type"] == "EnemyTurret"]
    mounts = [ev for ev in world_events if ev["type"] == "turret_mount"]
    gate_events = [ev for ev in world_events if ev.get("type") in {"breakable_gate", "weapon_gate"}]
    reward_gates = [ev for ev in world_events if ev.get("type") == "weapon_gate"]
    fixed_weapon_events = [ev for ev in world_events if ev.get("fixed_drop") == "WeaponItem"]
    miniboss_events = [
        ev for ev in world_events
        if ev.get("type") in {"EnemyCoughSprayer", "EnemySporeSplitter"}
    ]

    assert layout["type"] == "TerrainStrip"
    assert layout["theme"] == "fever_cave"
    assert layout["length"] >= 11000
    assert layout["center_wave"] >= 80
    assert 0.0 < layout["breakable_chance"] <= 0.03
    assert layout["breakable_drop_chance"] <= 0.05
    assert 0.0 < data["random_drop_scale"] < 1.0
    assert "weapon_drop_limit" not in data
    assert first_enemy_x >= 900
    assert sum(int(ev.get("count", 1)) for ev in turrets) >= 5
    assert len(mounts) >= 5
    assert {ev.get("surface") for ev in turrets} >= {"top", "bottom"}
    assert max(fixed_drop_chances) <= 0.08
    assert any(ev.get("kind") == "clot" and ev.get("destructible") for ev in world_events)
    assert len(gate_events) >= 4
    assert len(reward_gates) == 1
    assert reward_gates[0].get("fixed_drop") is None
    assert max(ev.get("hp", 0) for ev in gate_events) >= 20
    assert [ev["type"] for ev in fixed_weapon_events].count("EnemyCoughSprayer") == 1
    assert all(ev.get("fixed_drop") == "WeaponItem" for ev in miniboss_events)
    assert any(ev.get("type") == "EnemyCrawler" for ev in world_events)
    assert any(ev.get("type") == "EnemyPachemon" for ev in world_events)
    assert any(ev.get("type") == "EnemyCoughSprayer" for ev in world_events)
    assert any(ev.get("type") == "EnemyBilly" for ev in world_events)
    assert any(ev.get("type") == "Boss" and ev.get("x") for ev in world_events)
    assert data["events"] == []


def test_stage1_preplaces_boss_room_before_boss_alert() -> None:
    from src.core.constants import SCREEN_WIDTH
    from src.stages.stage import Stage

    data = json.loads((ROOT / "data" / "stages" / "stage1.json").read_text(encoding="utf-8"))
    boss_events = [ev for ev in data["world_events"] if ev["type"] == "Boss"]
    boss_gates = [ev for ev in data["world_events"] if ev["type"] == "BossGate"]
    boss_x = boss_events[0]["x"]
    gate_x = boss_gates[0]["trigger_x"]
    boss_room_blocks = [
        ev for ev in data["world_events"]
        if ev.get("kind") == "clot" and ev.get("x", 0) >= gate_x
    ]
    first_boss_room_x = min(ev["x"] for ev in boss_room_blocks)
    stage = Stage(object(), 1)

    assert stage.boss_terrain_mode == "preplaced"
    assert data["terrain_layout"][0]["length"] >= boss_x + 800
    assert len(boss_gates) == 1
    assert boss_gates[0]["trigger_x"] < boss_x
    assert boss_gates[0]["lock_camera_x"] + SCREEN_WIDTH <= first_boss_room_x
    assert boss_gates[0]["player_limit_x"] <= first_boss_room_x
    assert boss_x - SCREEN_WIDTH - boss_gates[0]["lock_camera_x"] <= 500
    assert boss_events[0].get("preload", 80) == 0
    assert len(boss_room_blocks) >= 4


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


def test_stage3_uses_authored_labor_fortress_setpieces() -> None:
    from src.core.constants import SCREEN_WIDTH
    from src.stages.stage import Stage

    data = json.loads((ROOT / "data" / "stages" / "stage3.json").read_text(encoding="utf-8"))
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
        if ev.get("kind") in {"wall", "rock", "fortress_block"} and ev.get("x", 0) >= boss_gate["trigger_x"]
    ]
    first_boss_room_x = min(ev["x"] for ev in boss_room_blocks)
    stage = Stage(object(), 3)

    assert data.get("initial_terrain", []) == []
    assert data["events"] == []
    assert data["boss_terrain_mode"] == "preplaced"
    assert 0.0 < data["random_drop_scale"] < 1.0
    assert layout["type"] == "TerrainStrip"
    assert layout["theme"] == "fortress"
    assert layout["renderer"] == "stage3_composer"
    assert layout["profile"] == "mountain"
    assert layout["length"] >= boss_x + 800
    assert layout["breakable_drop_chance"] <= 0.05
    assert len(world_events) >= 40
    assert sum(int(ev.get("count", 1)) for ev in turrets) >= 10
    assert len(mounts) >= 3
    assert {ev.get("surface") for ev in turrets} >= {"top", "bottom"}
    assert len(gates) >= 3
    assert len(reward_gates) == 1
    assert all(ev.get("fixed_drop") == "WeaponItem" for ev in minibosses)
    assert [ev["type"] for ev in fixed_weapon_events].count("EnemyCoughSprayer") == 2
    assert [ev["type"] for ev in fixed_weapon_events].count("EnemySporeSplitter") == 2
    assert any(ev["type"] == "EnemyBilly" for ev in world_events)
    assert max(ev.get("hp", 0) for ev in gates) >= 24
    assert boss_gate["lock_camera_x"] + SCREEN_WIDTH <= first_boss_room_x
    assert boss_gate["player_limit_x"] <= first_boss_room_x
    assert boss_x - SCREEN_WIDTH - boss_gate["lock_camera_x"] <= 500
    assert stage.boss_terrain_mode == "preplaced"


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
                + [script.BOSS_FORM3_INTRO] + list(script.FINAL_SEQ.values())):
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


def test_stage3_composer_floor_props_are_collidable() -> None:
    from src.entities.stage3_composer_terrain import (
        build_stage3_composer_layout,
        load_stage3_composer_pieces,
        make_stage3_composer_terrain,
    )
    from src.entities.terrain import make_terrain_strip

    stage3 = json.loads((ROOT / "data" / "stages" / "stage3.json").read_text(encoding="utf-8"))
    layout = stage3["terrain_layout"][0]
    segments = make_terrain_strip(
        float(layout.get("start_offset", 0)),
        length=int(layout["length"]),
        theme=str(layout["theme"]),
        profile=str(layout["profile"]),
        segment_w=int(layout["segment_w"]),
        seed=int(layout["seed"]),
        gap_min=int(layout["gap_min"]),
        gap_max=int(layout["gap_max"]),
        center_y=int(layout["center_y"]),
        center_wave=int(layout["center_wave"]),
        top_min=int(layout["top_min"]),
        bottom_min=int(layout["bottom_min"]),
        irregularity=int(layout["irregularity"]),
        breakable_chance=float(layout["breakable_chance"]),
        breakable_hp=int(layout["breakable_hp"]),
        breakable_drop_chance=float(layout["breakable_drop_chance"]),
    )
    composer_layout = build_stage3_composer_layout(segments, load_stage3_composer_pieces())
    sprites = make_stage3_composer_terrain(segments)
    prop_blocks = [
        sprite
        for sprite in sprites
        if not getattr(sprite, "terrain_visual_only", False)
        and getattr(sprite, "side", "") == ""
    ]

    assert any(placement.role == "prop" for placement in composer_layout.placements)
    assert composer_layout.collision_rects
    assert prop_blocks
    assert all(block.rect.width > 0 and block.rect.height > 0 for block in prop_blocks)


def test_stage3_composer_body_fill_uses_uncut_rect_pieces() -> None:
    from src.entities.stage3_composer_terrain import build_stage3_composer_layout, load_stage3_composer_pieces
    from src.entities.terrain import make_terrain_strip

    pieces = load_stage3_composer_pieces()
    source_sizes = {
        piece.image.get_size()
        for piece in pieces.get("block_square", [])
        if piece.image.get_width() <= 130
    }
    source_sizes = source_sizes or {piece.image.get_size() for piece in pieces.get("block_square", [])}
    assert source_sizes

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
    body = [placement for placement in layout.placements if placement.role == "body"]

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
    cap_heights = sorted(piece.image.get_height() for piece in pieces["strip_top"])

    assert _surface_band_depth(pieces) == cap_heights[len(cap_heights) // 2] - SURFACE_CAP_OVERHANG


def test_stage3_fortress_block_keeps_surface_anchor_after_damage() -> None:
    from src.entities.terrain import Terrain

    floor_block = Terrain(0, 330, 126, 168, "fortress_block", destructible=True, hp=3)
    ceiling_block = Terrain(0, 0, 126, 168, "fortress_block", destructible=True, hp=3)

    assert floor_block._surface_anchor == "floor"
    assert ceiling_block._surface_anchor == "ceiling"
    assert floor_block.take_damage(1) is False
    assert floor_block._surface_anchor == "floor"


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
        "mega_laser", "drone_cross", "rock_fall", "shogi_file",
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


def test_broly_beam_has_warning_and_fadeout() -> None:
    src = (ROOT / "src" / "entities" / "enemies" / "broly.py").read_text(encoding="utf-8")

    assert "_fire_warning()" in src
    assert "warning_only=True" in src
    assert "_fire_charge_beam()" in src
    assert "fade_shrink=True" in src
    assert "_paint_charge_beam" in src


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

        def take_damage(self, amount: int) -> bool:
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

    assert options["sample_step"] == layout["composer_sample_step"]
    assert options["tolerance"] == layout["composer_tolerance"]
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
