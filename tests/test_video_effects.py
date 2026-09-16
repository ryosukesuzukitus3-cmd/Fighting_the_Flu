from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pygame
import pytest
from PIL import Image

from src.core.video_effects import DEBUG_ONLY_VIDEO_EFFECT_KEYS, VIDEO_EFFECT_SPECS
from src.scenes.game.config import BOSS_MID_LINE_DURATION
from src.scenes.game import debug_stage_panel
from src.scenes.game_scene import GameScene
from src.story.script import BOSS_BREAK_TUTORIAL
from tools.capture import _parse_args as parse_capture_args


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("opacity", [0, 64, 145, 255])
def test_additive_effect_opacity_controls_pixels_without_mutating_source(opacity):
    from src.core.video_effects import VideoEffectSpec
    from src.entities.video_effect import VideoEffectLayer, _PlayingEffect

    source = pygame.Surface((1, 1), pygame.SRCALPHA)
    source.fill((255, 255, 255, 255))
    effect = _PlayingEffect(VideoEffectSpec("test", "synthetic", "test", 1, 1, (1, 1)),
                            (source,), (0, 0), (1, 1), opacity=opacity)
    layer = VideoEffectLayer(None)
    layer._effects.append(effect)
    target = pygame.Surface((1, 1), pygame.SRCALPHA)
    target.fill((0, 0, 0, 255))
    layer.draw(target)
    assert tuple(target.get_at((0, 0)))[:3] == (opacity, opacity, opacity)
    assert tuple(source.get_at((0, 0))) == (255, 255, 255, 255)


def test_alpha_effect_still_uses_surface_opacity():
    from src.core.video_effects import VideoEffectSpec
    from src.entities.video_effect import VideoEffectLayer, _PlayingEffect

    source = pygame.Surface((1, 1), pygame.SRCALPHA)
    source.fill((255, 255, 255, 255))
    effect = _PlayingEffect(VideoEffectSpec("test", "synthetic", "test", 1, 1, (1, 1), "alpha"),
                            (source,), (0, 0), (1, 1), opacity=0)
    layer = VideoEffectLayer(None)
    layer._effects.append(effect)
    target = pygame.Surface((1, 1), pygame.SRCALPHA)
    target.fill((20, 30, 40, 255))
    layer.draw(target)
    assert tuple(target.get_at((0, 0))) == (20, 30, 40, 255)


def test_all_supplied_video_effect_sequences_are_complete() -> None:
    assert len(VIDEO_EFFECT_SPECS) == 12
    assert len({spec.key for spec in VIDEO_EFFECT_SPECS}) == 12
    assert len({spec.source_id for spec in VIDEO_EFFECT_SPECS}) == 12

    for spec in VIDEO_EFFECT_SPECS:
        folder = ROOT / "assets" / "graphic" / "effects" / spec.key
        frames = sorted(folder.glob(f"{spec.key}_*.png"))
        assert [frame.name for frame in frames] == [
            f"{spec.key}_{i:02d}.png" for i in range(spec.frame_count)
        ]
        with Image.open(frames[len(frames) // 2]) as image:
            assert image.mode == "RGBA"
            assert image.width <= 512
            assert image.height <= 384


def test_keyed_effects_have_real_transparency() -> None:
    opaque_key = "light_arrow_tunnel"
    for spec in VIDEO_EFFECT_SPECS:
        extrema = []
        for index in range(spec.frame_count):
            frame = (ROOT / "assets" / "graphic" / "effects" / spec.key
                     / f"{spec.key}_{index:02d}.png")
            with Image.open(frame) as image:
                extrema.append(image.getchannel("A").getextrema())
        if spec.key == opaque_key:
            assert set(extrema) == {(255, 255)}
        else:
            # A sequence may contain intentional blank anticipation frames;
            # across the whole sequence it must contain both transparency and
            # visible content.
            assert min(lo for lo, _ in extrema) < 255
            assert max(hi for _, hi in extrema) > 0


def test_debug_fx_gallery_covers_registry_in_order() -> None:
    assert debug_stage_panel._TABS[-1] == "FX"
    assert debug_stage_panel._FX_KEYS == [spec.key for spec in VIDEO_EFFECT_SPECS]
    assert len(debug_stage_panel._FX_ENTRIES) == 12


def test_capture_can_force_a_boss_pattern_for_visual_review() -> None:
    args = parse_capture_args(["--boss", "--form", "3", "--pattern", "mega_beam"])
    assert args.boss
    assert args.form == 3
    assert args.pattern == "mega_beam"


def test_accepted_effects_are_wired_outside_the_debug_gallery() -> None:
    gameplay_files = (
        ROOT / "src" / "scenes" / "game_scene.py",
        ROOT / "src" / "entities" / "enemies" / "boss.py",
        ROOT / "src" / "entities" / "bullets" / "player_bullet.py",
        ROOT / "src" / "scenes" / "game" / "final_battle.py",
        ROOT / "src" / "scenes" / "cutscene_scene.py",
        ROOT / "src" / "scenes" / "blackhole_scene.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in gameplay_files)
    for spec in VIDEO_EFFECT_SPECS:
        if spec.key in DEBUG_ONLY_VIDEO_EFFECT_KEYS:
            assert f'"{spec.key}"' not in source, f"{spec.key} leaked into normal play"
        else:
            assert f'"{spec.key}"' in source, f"{spec.key} is unexpectedly debug-only"


@pytest.mark.parametrize("level", [1, 6, 7])
def test_homing_animates_missile_until_tokin_without_enlarging_collision(monkeypatch, level):
    from src.core.camera import Camera
    from src.entities.bullets.player_bullet import HomingBullet
    from src.entities.weapon import Weapon
    import src.entities.video_effect as video_effect

    def colored(color):
        surface = pygame.Surface((52, 30), pygame.SRCALPHA)
        surface.fill(color)
        return surface

    frames = (colored("red"), colored("green"))
    requested = []

    def load_frames(resources, key):
        requested.append(key)
        return frames

    monkeypatch.setattr(video_effect, "load_video_effect_frames", load_frames)
    monkeypatch.setattr(HomingBullet, "_missile_frames", None)
    monkeypatch.setattr(HomingBullet, "_base_image", None)
    tokin = pygame.Surface((26, 20), pygame.SRCALPHA)
    tokin.fill("blue")
    game = SimpleNamespace(resources=SimpleNamespace(image=lambda path: tokin))
    weapon = Weapon()
    weapon.homing_level = level
    bullets = [bullet for bullet in weapon.get_bullets(100, 100, pygame.sprite.Group(), game)
               if isinstance(bullet, HomingBullet)]
    assert bullets
    assert all(bullet.rect.size == (26, 20) for bullet in bullets)
    # These tiers each include a horizontal shot, so rotation does not alter its bounds.
    bullet = next(bullet for bullet in bullets if bullet.vy == 0)
    before = bullet.image.get_at((13, 10))
    bullet.update(0.1, Camera())
    assert bullet.rect.size == (26, 20)
    assert bullet.world_x > 100
    after = bullet.image.get_at((13, 10))
    if level < 7:
        assert requested == ["missile_loop"]
        assert before == pygame.Color("red")
        assert after == pygame.Color("green")
    else:
        assert requested == []
        assert before == after == pygame.Color("blue")


def test_boss_break_is_subdued_and_explained_only_once() -> None:
    particles = SimpleNamespace(
        spawn_hit=Mock(), spawn_spark=Mock(), spawn_glow=Mock(),
    )
    shared = SimpleNamespace(boss_break_tutorial_shown=False)
    scene = SimpleNamespace(
        _boss=SimpleNamespace(rect=pygame.Rect(300, 200, 100, 100)),
        _boss_stage_id=Mock(return_value=1),
        _spawn_popup=Mock(),
        particles=particles,
        _play_video_effect=Mock(),
        camera=SimpleNamespace(shake=Mock()),
        _hitstop_timer=0.0,
        _boss_break_flash_timer=0.0,
        _enqueue_boss_dialogue=Mock(),
        _play_shogi_snap=Mock(),
        game=SimpleNamespace(
            shared=shared,
            sound=SimpleNamespace(play_se=Mock()),
        ),
    )

    GameScene._on_boss_break(scene)

    scene._play_video_effect.assert_called_once_with(
        "anime_impact", center=(350, 250), size=(180, 180), opacity=145,
    )
    particles.spawn_hit.assert_called_once()
    scene.camera.shake.assert_called_once_with(10.0)
    scene._enqueue_boss_dialogue.assert_called_once_with(
        BOSS_BREAK_TUTORIAL, BOSS_MID_LINE_DURATION,
    )
    assert shared.boss_break_tutorial_shown

    GameScene._on_boss_break(scene)
    assert scene._enqueue_boss_dialogue.call_count == 1


def test_midfight_cutin_waits_for_the_break_tutorial_bark() -> None:
    source = (ROOT / "src" / "scenes" / "game_scene.py").read_text(encoding="utf-8")
    midfight_guard = source[source.index("# Queue boss mid-fight dialogue"):]
    assert "and self._boss_dialogue_timer <= 0" in midfight_guard.split("if mid_key in BOSS_MID:", 1)[0]
