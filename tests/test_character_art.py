"""Character art remains readable without changing gameplay collision envelopes."""
import pygame
import pytest

from tools.headless import build_game_scene
from src.core.sprite_art import fit_character_art
from src.entities.companion import Karonaru
from src.entities.enemies.boss import Boss
from src.scenes.dialogue_panel import _tachie_image
from src.story.speakers import SAWAGUCHI, KARONARU, KARONARU_MAX, BOSS2, BOSS3, speaker_portrait


@pytest.fixture
def game(monkeypatch, tmp_path):
    monkeypatch.setenv("FLU_USER_DATA_DIR", str(tmp_path))
    game, _ = build_game_scene(1)
    yield game
    game.close()


def test_art_preserves_aspect_and_crisp_small_pixels_without_mutating_sources():
    source = pygame.Surface((8, 10), pygame.SRCALPHA)
    source.fill((255, 255, 255, 10))  # Faint decorative glow must not shrink the body.
    pygame.draw.rect(source, (20, 100, 180, 255), (3, 1, 2, 8))
    pygame.draw.rect(source, (180, 40, 20, 255), (3, 1, 1, 8))
    image = fit_character_art(source, (32, 32))
    bounds = image.get_bounding_rect(min_alpha=32)
    assert bounds.size == (8, 32)
    assert bounds.center == (16, 16)
    assert {tuple(image.get_at((x, 15))) for x in range(bounds.left, bounds.right)} == {
        (20, 100, 180, 255), (180, 40, 20, 255),
    }
    image.fill((0, 0, 0, 0))
    assert fit_character_art(source, (32, 32)).get_bounding_rect(min_alpha=32) == bounds
    assert source.get_at((0, 0)).a == 10


def test_new_companion_art_keeps_both_collision_sizes_and_fills_its_height(game):
    companion = Karonaru(game)
    companion.rect.center = (250, 210)
    for maximum, expected_size, expected_hit in ((False, (34, 34), (26, 26)), (True, (56, 56), (48, 48))):
        if maximum:
            companion.set_max()
        assert companion.rect.size == expected_size
        assert companion.hit_rect.size == expected_hit
        assert companion.rect.center == (250, 210)
        body = companion.image.get_bounding_rect(min_alpha=128)
        assert body.height >= expected_size[1] - 2
        assert body.width >= expected_size[0] // 2


def test_dialogue_uses_finished_art_and_keeps_faces_proportional(game):
    for speaker in (KARONARU, KARONARU_MAX, BOSS2, BOSS3):
        path = speaker_portrait(speaker)
        assert "dummy" not in path
        assert game.resources.image(path).get_width() > 128
    source = game.resources.image(speaker_portrait(SAWAGUCHI))
    original = source.get_bounding_rect(min_alpha=32)
    image = _tachie_image(game.resources, SAWAGUCHI, 300, flip=False, active=True)
    result = image.get_bounding_rect(min_alpha=32)
    assert result.width / result.height == pytest.approx(original.width / original.height, abs=.01)
    assert result.width < result.height


def test_broly_transformation_keeps_collision_envelope_with_high_quality_art(game):
    boss = Boss(game, stage_id=2)
    boss.sx, boss.sy = 530, 280
    boss._transform_super_saiyan()
    assert boss.rect.size == (216, 182)
    assert boss.rect.center == (530, 280)
    assert boss.image.get_bounding_rect(min_alpha=128).width >= 170


def test_pixel_hero_and_inner_shadow_keep_existing_gameplay_sizes(game):
    from src.entities.player import Player
    from src.story.speakers import BOSS_SAWAGUCHI

    player = Player(game)
    assert player.rect.size == (23, 31)
    assert player.hit_rect.size == (21, 28)
    assert player.muzzle_screen() == (player.sx + 23, player.sy + 15.5)
    boss = Boss(game, stage_id=4)
    boss.sx, boss.sy = 530, 280
    boss._transform_form3()
    assert boss.rect.size == (117, 153)
    assert boss.rect.center == (530, 280)
    assert speaker_portrait(SAWAGUCHI) == speaker_portrait(BOSS_SAWAGUCHI)
    assert game.resources.image(speaker_portrait(SAWAGUCHI)).get_width() > 49
