"""Check combat visibility and key prompts with actual pygame rendering."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest

from src.entities.hud import HUD, HUD_BOTTOM
from src.entities.weapon import Weapon
from src.scenes.game.boss_fx_mixin import GameSceneBossFxMixin
from src.scenes.game.overlay_mixin import GameSceneOverlayMixin

FONT = Path(__file__).resolve().parents[1] / "assets/font/DotGothic16-Regular.ttf"


class _RecordingFont:
    def __init__(self, font, rendered):
        self.font, self.rendered = font, rendered

    def size(self, text):
        return self.font.size(text)

    def get_linesize(self):
        return self.font.get_linesize()

    def render(self, text, *args):
        surface = self.font.render(text, *args)
        self.rendered.append((text, surface.get_width()))
        return surface


@pytest.fixture
def game():
    pygame.font.init()
    rendered = []
    keys = {"weapon_select": "F8", "bomb": "LSHIFT", "laser": "RCTRL"}
    resources = SimpleNamespace(
        pixelfont=lambda size: _RecordingFont(pygame.font.Font(FONT, size), rendered),
    )
    return SimpleNamespace(
        resources=resources, settings=SimpleNamespace(key_display=keys.__getitem__),
        rendered=rendered, keys=keys,
    )


def _player():
    weapon = Weapon()
    weapon.main_level = len(weapon._MAIN_LEVELS) - 1
    weapon.speed_level = 5
    weapon.laser_level = 6
    weapon.homing_level = 7
    weapon.magnet_level = 3
    weapon.has_barrier = True
    weapon.weapon_stock = 9
    return SimpleNamespace(hp=100, max_hp=100, weapon=weapon)


def _draw_full_hud(hud, screen, player=None, **kwargs):
    hud.draw(
        screen, player or _player(), score=1234567890, kill_count=1234,
        clear_goal=0, lives=0,
        heat=SimpleNamespace(overheated=False, ratio=0.7, display_temp=39.1),
        pieces=["歩", "金", "龍"],
        laser=SimpleNamespace(state="ready", gauge_ratio=1.0), **kwargs,
    )


def test_all_player_status_fits_inside_top_band(game):
    screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    _draw_full_hud(HUD(game), screen)
    assert screen.get_bounding_rect().bottom <= HUD_BOTTOM
    assert screen.get_at((200, 150)).a == 0
    assert screen.get_at((600, 250)).a == 0
    assert all(width <= 248 for _text, width in game.rendered)
    text = [item[0] for item in game.rendered]
    assert "有給 0日" in text
    assert "メイン MEDIC" in text
    assert any("レーザー6" in item and "追尾7" in item and "磁力3" in item and "防壁" in item for item in text)


def test_hud_uses_current_remapped_gameplay_keys(game):
    hud = HUD(game)
    screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    _draw_full_hud(hud, screen)
    text = "\n".join(item[0] for item in game.rendered)
    assert "[F8]" in text and "[LSHIFT]" in text and "[RCTRL]" in text
    game.keys.update(weapon_select="Q", bomb="E", laser="R")
    game.rendered.clear()
    _draw_full_hud(hud, screen)
    text = "\n".join(item[0] for item in game.rendered)
    assert "[Q]" in text and "[E]" in text and "[R]" in text
    assert "[F8]" not in text


def test_long_weapon_name_does_not_spill_into_neighbor_column(game):
    class LongNamedWeapon(Weapon):
        @property
        def main_type(self):
            return "EXTREMELY_LONG_WEAPON_NAME" * 3

    player = _player()
    player.weapon = LongNamedWeapon()
    _draw_full_hud(HUD(game), pygame.Surface((800, 600), pygame.SRCALPHA), player)
    main_label = next(item for item in game.rendered if item[0].startswith("メイン "))
    assert main_label[0].endswith("…")
    assert main_label[1] <= 178


def test_boss_gauge_keeps_center_of_battle_uncovered(game):
    screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    boss = SimpleNamespace(hp=50, max_hp=100, is_stance_down=False, stance_ratio=lambda: 0.5)
    _draw_full_hud(HUD(game), screen, boss=boss)
    assert screen.get_at((400, 570)).a > 0
    assert screen.get_at((400, 400)).a == 0


def test_timed_bark_uses_small_band_and_preserves_all_text(game):
    scene = GameSceneOverlayMixin()
    scene.game = game
    scene._boss_dialogue_font = None
    scene._boss_dialogue_timer = 2.0
    scene._boss_dialogue_line_dur = 3.0
    scene._boss_dialogue_speaker = "カロナール先輩"
    scene._boss_dialogue_lines = ("熱が上がってきたにょ。", "少し撃つのを休めば冷えるにょ。")
    screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    scene._draw_boss_dialogue(screen)
    bounds = screen.get_bounding_rect()
    assert bounds.height <= 76
    assert bounds.bottom <= 542
    assert screen.get_at((400, 400)).a == 0
    drawn_text = "".join(item[0] for item in game.rendered)
    for line in scene._boss_dialogue_lines:
        assert line in drawn_text


@pytest.mark.parametrize("can_attack", [False, True])
def test_break_chance_only_appears_when_combat_input_is_allowed(game, can_attack):
    scene = GameSceneBossFxMixin()
    scene.game = game
    scene._accepts_combat_input = can_attack
    scene._draw_boss_concept_fx = lambda *_args: None
    scene._boss = SimpleNamespace(
        rect=pygame.Rect(550, 250, 70, 80), _state="fight",
        _current_gimmick=lambda: "shield", _shield_active=False, _down_timer=0.0,
    )
    scene._draw_boss_gimmick(pygame.Surface((800, 600), pygame.SRCALPHA))
    assert any(text == "BREAK CHANCE!" for text, _width in game.rendered) == can_attack
