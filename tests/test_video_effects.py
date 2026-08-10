from pathlib import Path

from PIL import Image

from src.core.video_effects import VIDEO_EFFECT_SPECS
from src.scenes.game import debug_stage_panel


ROOT = Path(__file__).resolve().parents[1]


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


def test_every_effect_is_wired_outside_the_debug_gallery() -> None:
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
        assert f'"{spec.key}"' in source, f"{spec.key} is debug-only"


def test_max_homing_missile_keeps_original_collision_canvas() -> None:
    source = (ROOT / "src" / "entities" / "bullets" / "player_bullet.py").read_text(
        encoding="utf-8"
    )
    assert "canvas = pygame.Surface(_TOKIN_SIZE" in source
    assert "pygame.transform.smoothscale(frame, (26, 11))" in source
