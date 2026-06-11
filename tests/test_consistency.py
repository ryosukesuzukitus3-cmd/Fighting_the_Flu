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
    valid = set(ENEMY_NAMES) | {"Boss", "Terrain", "TerrainStrip"}
    for p in sorted((ROOT / "data" / "stages").glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for ev in data.get("events", []):
            t = ev.get("type", "")
            assert t in valid, f"{p.name}: 未知の type '{t}'"
        for section in ("initial_terrain", "boss_terrain"):
            for ev in data.get(section, []):
                t = ev.get("type", "")
                assert t in {"Terrain", "TerrainStrip"}, (
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
    assert random_item_names() == {d.name for d in ITEM_DEFS if d.drop_weight > 0}


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
    from src.entities.terrain import TERRAIN_STRIP_THEMES
    valid_strip_themes = set(TERRAIN_STRIP_THEMES)

    def assert_terrain_event(section: str, i: int, ev: dict) -> None:
        assert ev.get("type") in {"Terrain", "TerrainStrip"}, (
            f"{section}[{i}]: terrain section only allows Terrain/TerrainStrip"
        )
        if ev.get("type") == "Terrain":
            for field in ("y", "w", "h", "kind"):
                assert field in ev, f"{section}[{i}](Terrain): missing '{field}'"
            assert ev["kind"] in valid_terrain_kinds, (
                f"{section}[{i}](Terrain): unknown kind '{ev['kind']}'"
            )
        else:
            for field in ("theme", "length"):
                assert field in ev, f"{section}[{i}](TerrainStrip): missing '{field}'"
            assert ev["theme"] in valid_strip_themes, (
                f"{section}[{i}](TerrainStrip): unknown theme '{ev['theme']}'"
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
        for i, ev in enumerate(data.get("events", [])):
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
        for section in ("initial_terrain", "boss_terrain"):
            for i, ev in enumerate(data.get(section, [])):
                assert_terrain_event(f"{p.name} {section}", i, ev)


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

def test_terrain_strip_can_spawn_breakable_segments() -> None:
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

    target = breakables[0]
    assert target.take_damage(1) is False
    assert target.hp == 1
    assert target.take_damage(1) is True


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


def test_boss_phase_configs_reference_known_patterns() -> None:
    from src.entities.enemies.boss import _PHASE_CONFIGS

    known = {
        "fan5", "fan7", "aimed", "dbl_aimed", "ring8", "ring12", "ring16",
        "aimring6", "aimring8", "scatter", "cross", "spiral", "vortex2",
        "vortex3", "chaos", "burst3", "wall_gap",
    }
    used = {phase[1] for phases in _PHASE_CONFIGS.values() for phase in phases}
    assert used <= known


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


def test_project_text_files_are_utf8_and_mojibake_free() -> None:
    from tools.dev_env import text_integrity_issues

    assert text_integrity_issues(ROOT) == []


def test_project_runner_prefers_utf8_and_venv() -> None:
    src = (ROOT / "tools" / "run.py").read_text(encoding="utf-8")
    assert "PYTHONIOENCODING" in src
    assert ".venv" in src


def test_manual_docs_do_not_reference_removed_items() -> None:
    design = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    for term in ("LaserItem", "HomingItem", "ShieldItem", "shield.py"):
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


def test_boss_kill_clears_mid_dialogue_queue() -> None:
    src = (ROOT / "src" / "scenes" / "game" / "post_boss_mixin.py").read_text(encoding="utf-8")
    assert "self._boss_dialogue_timer = 0.0" in src
    assert "self._boss_dialogue_queue = []" in src


def test_boss_gimmick_draw_ignores_missing_boss() -> None:
    from src.scenes.game_scene import GameScene

    scene = object.__new__(GameScene)
    scene._boss = None
    GameScene._draw_boss_gimmick(scene, pygame.Surface((32, 32)))


def test_stage3_blackhole_uses_actor_scene() -> None:
    src = (ROOT / "src" / "scenes" / "stageclear.py").read_text(encoding="utf-8")
    assert "BlackholeScene" in src
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
    src = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    spawn_at = src.index("self._spawn_returning_karonaru()")
    dialogue_at = src.index("self._play_final_dialogue(FINAL_SEQ[\"return\"]")
    assert spawn_at < dialogue_at
    assert "self._final_seq == \"return_join\"" in src
    assert "_draw_karonaru_arrival_trail" in src
    assert "SE_KARONARU_ARRIVE" in src
    assert "start = (-48.0, arrival_y)" in src
    assert "self._karonaru_heal_player()" in src
    assert "self.player.hp = self.player.max_hp" in src
    assert "final_chance" in src
    assert "KARONARU RETURNS" not in src


def test_design_md_autogen_blocks_are_current() -> None:
    import subprocess
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_docs.py"), "--check"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"design.md の AUTOGEN ブロックが古い:\n{result.stderr.strip()}"
    )
