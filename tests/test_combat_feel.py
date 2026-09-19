"""Combat choices, stable dialogue staging and deliberate cinematic hits."""
import hashlib
import json
from pathlib import Path

import pygame
import pytest

from tools.headless import build_game_scene
from src.core.battle_systems import HeatSystem
from src.entities.weapon import Weapon
from src.managers.input import InputManager
from src.scenes import dialogue_panel as panel

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def stage(monkeypatch, tmp_path):
    monkeypatch.setenv("FLU_USER_DATA_DIR", str(tmp_path))
    game, scene = build_game_scene(1)
    game.input = InputManager(game.settings, physical_input=False)
    scene.spawner.skip_all_events()
    for group in (scene.enemies, scene.enemy_bullets, scene.terrain, scene.items):
        group.empty()
    scene.camera.scroll_speed = 0
    scene._stage_banner_timer = scene._bgm_delay = 0
    scene.player._entering = False
    yield game, scene
    game.close()


def test_main_fire_continues_during_laser_overheat(stage):
    game, scene = stage
    scene.player.weapon.main_level = 4
    scene.player.weapon.laser_level = 1
    scene._heat.add(100)
    event = pygame.event.Event(pygame.KEYDOWN, key=game.settings.get_key("fire"))
    game.step(1 / 60, [event], allow_debug=False)
    assert scene._heat.overheated
    assert len(scene.player_bullets) >= 3
    assert scene.laser.state == "ready"


def test_upgraded_main_fire_alone_never_overheats(stage):
    game, scene = stage
    scene.player.weapon.main_level = 4
    fire = pygame.event.Event(pygame.KEYDOWN, key=game.settings.get_key("fire"))
    for frame in range(660):
        game.step(1 / 60, [fire] if frame == 0 else [], allow_debug=False)
    assert scene._heat.heat == 0 and not scene._heat.overheated
    assert scene.player_bullets


def test_laser_choice_builds_heat_and_main_fire_window_cools_it():
    heat = HeatSystem()
    heat.heat = 70
    heat.update(.5, laser_active=True)
    assert heat.heat == 70
    heat.update(.5, laser_active=False)
    assert heat.heat < 70
    before = heat.heat
    heat.update(.5, boss_down=True, laser_active=True)
    assert heat.heat < before


def test_main_upgrades_preserve_central_fire_and_increase_coverage(stage):
    previous = 0
    for level in range(5):
        weapon = Weapon()
        weapon.main_level = level
        rounds = [weapon.get_bullets(0, 0, pygame.sprite.Group()) for _ in range(2)]
        central = [sum(b.damage for b in volley if b.vy == 0) for volley in rounds]
        assert all(central)
        dps = min(central) / weapon.shoot_cooldown
        assert dps >= previous
        previous = dps
        if level == 3:
            assert rounds[0][1].vy * rounds[1][1].vy < 0


def test_story_window_and_portraits_stay_at_fixed_height(stage, monkeypatch):
    from src.story.speakers import SAWAGUCHI, NARRATION
    game, _ = stage
    windows, body_areas = [], []
    original = panel._draw_window
    text = panel._draw_text
    def window(screen, rect, style, alpha):
        windows.append(rect.copy())
        return original(screen, rect, style, alpha)
    def body(screen, resources, rect, lines, style, **kwargs):
        font = resources.pixelfont(kwargs["body_size"])
        area = panel._text_rect(rect, kwargs["text_x"], kwargs["text_w"],
                               kwargs["reserved_bottom"], kwargs["name_height"])
        assert len(lines) * panel._line_height(font) - 2 <= area.h
        body_areas.append(area)
        return text(screen, resources, rect, lines, style, **kwargs)
    monkeypatch.setattr(panel, "_draw_window", window)
    monkeypatch.setattr(panel, "_draw_text", body)
    for speaker, lines, hint in (
        (SAWAGUCHI, ["短い台詞。"], ""),
        (NARRATION, ["長い文章でもウィンドウの高さと立ち絵の位置は変えない。" * 3], "ENTER: 次へ"),
        (SAWAGUCHI, ["一行目", "二行目", "三行目", "四行目"], "ENTER: 次へ"),
    ):
        panel.draw_story_panel(game.screen, game.resources, speaker, lines, hint_text=hint)
    assert len({tuple(r) for r in windows}) == 1
    assert len({r.y for r in body_areas}) == 1


def test_all_authored_story_pages_fit_fixed_window(stage, monkeypatch):
    from src.story.script import STORY_BEATS
    game, _ = stage
    observed = []
    def measure(screen, resources, rect, lines, style, **kw):
        font = resources.pixelfont(kw["body_size"])
        area = panel._text_rect(rect, kw["text_x"], kw["text_w"],
                               kw["reserved_bottom"], kw["name_height"])
        assert len(lines) * panel._line_height(font) - 2 <= area.h, lines
        observed.append(rect.h)
    monkeypatch.setattr(panel, "_draw_text", measure)
    for beat in STORY_BEATS:
        if beat.scene == "credits":
            continue
        for page in beat.pages:
            panel.draw_story_panel(game.screen, game.resources, page.speaker, page.lines,
                                   show_portrait=False, hint_text="ENTER: 次へ")
    assert observed and set(observed) == {224}


def test_final_beam_requires_charge_and_wavefront_before_hit(stage):
    from src.entities.combat_effects import FinalBeam
    game, _ = stage
    beam = FinalBeam(game, (150, 300), (650, 250))
    boss = pygame.Rect(610, 210, 80, 80)
    beam.advance(beam.CHARGE - .01)
    beam.draw_effect(game.screen)
    assert not beam.collides_with_rect(boss)
    beam.advance(beam.TRAVEL)
    assert not beam.collides_with_rect(boss)
    beam.advance(.02)
    assert beam.collides_with_rect(boss)
    assert not beam.collides_with_rect(pygame.Rect(200, 500, 20, 20))


def test_fortress_shows_local_muzzles_and_real_projectiles(stage, monkeypatch):
    from src.entities.enemies.boss import Boss
    from src.entities.combat_effects import EnergyMuzzle
    game, scene = stage
    boss = Boss(game, 3)
    boss._state = "fight"
    boss.rect.center = (600, 300)
    boss.sx, boss.sy = 600, 300
    videos = []
    boss.video_effect_fn = lambda *a, **kw: videos.append(a)
    shots = pygame.sprite.Group()
    boss._shoot(shots, scene.player)
    assert not videos
    assert sum(isinstance(b, EnergyMuzzle) for b in shots) == 2
    assert any(not getattr(b, "warning_only", False) and b.damage > 0 for b in shots)


def test_new_asset_files_decode_match_provenance_and_are_credited(stage):
    from src.story.script import CREDITS
    game, _ = stage
    manifest = json.loads((ROOT / "data/combat_asset_sources.json").read_text("utf-8"))
    credits = " ".join(line for page in CREDITS for line in page.lines)
    assert "Kenney (kenney.nl)" in credits and "Particle Pack / Sci-Fi Sounds" in credits
    from src.core.runtime_assets import runtime_data_files
    packaged = set(runtime_data_files())
    for row in manifest["files"]:
        file = ROOT / row["path"]
        assert file in packaged
        assert hashlib.sha256(file.read_bytes()).hexdigest() == row["sha256"]
        if file.suffix == ".png":
            assert pygame.image.load(file).get_size() == (512, 512)
        else:
            assert pygame.mixer.Sound(file).get_length() > 0


@pytest.mark.parametrize("stage_id,ratio,warning_duration", [(2,.65,1.15),(4,.56,.85)])
def test_boss_beams_always_warn_at_the_firing_position(stage, stage_id, ratio, warning_duration):
    from src.entities.enemies.boss import Boss
    from src.entities.bullets.laser_fx import LaserBeamSprite
    game, scene = stage
    boss = Boss(game, stage_id)
    if stage_id == 4:
        boss._transform_form2()
        boss._transform_form3()
    boss._state = "fight"
    boss.sx, boss.sy = 610, 300
    boss.rect.center = (610, 300)
    boss.hp = int(boss.max_hp * ratio)
    boss._shot_variant = 1  # Enter after an odd number of previous volleys.
    boss._fight_time = 999  # Enrage cannot shorten the displayed warning.
    boss._shoot_timer = 0
    shots = pygame.sprite.Group()
    boss.update(1/60, shots, scene.player)
    warnings = [b for b in shots if isinstance(b, LaserBeamSprite) and b.warning_only]
    assert len(warnings) == 1
    assert not any(isinstance(b, LaserBeamSprite) and not b.warning_only for b in shots)
    y = warnings[0].rect.centery
    assert boss._shoot_timer == pytest.approx(warning_duration)
    scene.player.sy = 40
    elapsed = 0
    while elapsed < warning_duration + .05:
        boss.update(1/60, shots, scene.player)
        elapsed += 1/60
        beams = [b for b in shots if isinstance(b, LaserBeamSprite) and not b.warning_only]
        if beams:
            break
    assert beams and beams[0].rect.centery == y
    assert elapsed >= warning_duration
    assert boss.sy == pytest.approx(y, abs=1)


@pytest.mark.parametrize("form", [1, 2])
def test_broly_opens_only_after_beam_ends_and_repeats_warning(stage, form):
    from src.entities.enemies.boss import Boss
    from src.entities.bullets.laser_fx import LaserBeamSprite
    game, scene = stage
    boss = Boss(game, 2)
    if form == 2:
        boss._transform_super_saiyan()
    boss._state = "fight"
    boss.sx, boss.sy = 610, 300
    boss.rect.center = (610, 300)
    shots = pygame.sprite.Group()
    openings, warnings = 0, 0
    previous_open = False
    previous_warning = False
    for _ in range(900):
        shots.update(1/60)
        boss.update(1/60, shots, scene.player)
        warning = boss._beam_charge_pattern is not None
        warnings += int(warning and not previous_warning)
        previous_warning = warning
        if boss.is_stance_down:
            assert not any(isinstance(b, LaserBeamSprite) and not b.warning_only for b in shots)
            assert not boss.suction_active
            openings += int(not previous_open)
        previous_open = boss.is_stance_down
    assert openings >= 2 and warnings >= 2
    assert boss.stance_ratio() is None


def test_single_damage_hits_respect_defense_without_disappearing(stage):
    from src.entities.enemies.boss import Boss
    game, _ = stage
    boss = Boss(game, 2)
    boss._state = "fight"
    hp = boss.hp
    for _ in range(10):
        boss.take_damage(1)
    assert hp - boss.hp == 2
    boss._weak_timer = 1
    hp = boss.hp
    for _ in range(10):
        boss.take_damage(1)
    assert hp - boss.hp == 20


def test_laser_release_stops_damage_and_repress_keeps_hit_cooldown():
    from src.entities.laser_beam import LaserBeam
    from types import SimpleNamespace
    beam = LaserBeam()
    hits = []
    boss = SimpleNamespace(rect=pygame.Rect(200, 280, 80, 80),
                           take_damage=lambda amount, **kw: hits.append(amount))
    enemies = pygame.sprite.Group()
    beam.update(.08, True)
    beam.hit_check(enemies, boss, 120, 300)
    assert hits == [1]
    beam.update(.001, False)
    beam.hit_check(enemies, boss, 120, 300)
    assert not beam.is_active and hits == [1]
    beam.update(.08, True)
    beam.hit_check(enemies, boss, 120, 300)
    assert hits == [1]
