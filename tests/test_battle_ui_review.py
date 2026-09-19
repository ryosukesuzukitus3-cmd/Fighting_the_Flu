"""Readable battle UI and reversible, explicit two-tree upgrade selection."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pygame
import pytest

from src.entities.hud import HUD, HUD_BOTTOM
from src.entities.weapon import Weapon
from src.managers.input import InputManager
from src.scenes.game.upgrade_mixin import GameSceneUpgradeMixin
from src.scenes.game.pause_mixin import GameScenePauseMixin

FONT = Path(__file__).resolve().parents[1] / "assets/font/DotGothic16-Regular.ttf"


class RecordingFont:
    def __init__(self, size, records):
        self.font = pygame.font.Font(FONT, size)
        self.records = records

    def size(self, text):
        return self.font.size(text)

    def get_linesize(self):
        return self.font.get_linesize()

    def render(self, text, *args):
        result = self.font.render(text, *args)
        self.records.append((text, result.get_width()))
        return result


class Menus(GameSceneUpgradeMixin, GameScenePauseMixin):
    pass


@pytest.fixture
def scene():
    pygame.font.init()
    records = []
    keys = {"ui_accept": pygame.K_F9, "ui_back": pygame.K_F10, "pause": pygame.K_F11}
    displays = {"ui_accept": "F9", "ui_back": "F10", "pause": "F11",
                "weapon_select": "V", "laser": "SPACE"}
    settings = SimpleNamespace(get_key=keys.__getitem__, key_display=displays.__getitem__)
    result = Menus()
    result.game = SimpleNamespace(
        resources=SimpleNamespace(pixelfont=lambda size: RecordingFont(size, records)),
        settings=settings, input=InputManager(settings), sound=Mock(),
        story=SimpleNamespace(karonaru_lost=False), records=records, displays=displays,
    )
    result.player = SimpleNamespace(weapon=Weapon(), hp=100, max_hp=100)
    result.player.weapon.weapon_stock = 2
    result._companion = Mock(stock=2)
    result._companion.is_upgrade_available.return_value = True
    result._companion.upgrade_level.return_value = 0
    result._pause_font = result._upgrade_font = None
    result._pause_cursor = 0
    result._paused = False
    return result


def test_confirmation_returns_to_each_unselected_tree_without_spending(scene):
    scene._open_upgrade_ui()
    top, bottom = scene._top_available_indices(), scene._bottom_available_indices()
    scene._upg_zone = "confirm"
    scene._confirm_zone(top, bottom)
    assert scene._upg_zone == "top"
    assert scene.player.weapon.weapon_stock == scene._companion.stock == 2
    scene._confirm_zone(top, bottom)
    scene._upg_zone = "confirm"
    scene._confirm_zone(top, bottom)
    assert scene._upg_zone == "bottom"
    assert scene.player.weapon.main_level == 0
    scene._confirm_zone(top, bottom)
    assert scene._upg_zone == "confirm"
    scene._confirm_zone(top, bottom)
    assert not scene._upgrading
    assert scene.player.weapon.main_level == 1
    assert scene.player.weapon.weapon_stock == scene._companion.stock == 1
    scene._companion.apply_upgrade.assert_called_once()


def test_back_discards_pending_selection_and_keeps_both_stocks(scene):
    scene._open_upgrade_ui()
    scene._upg_top_choice = 0
    scene._upg_bottom_choice = 1
    scene.game.input.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F10))
    scene._update_upgrade_ui()
    assert not scene._upgrading
    assert scene.player.weapon.main_level == 0
    assert scene.player.weapon.weapon_stock == scene._companion.stock == 2
    scene._companion.apply_upgrade.assert_not_called()


def test_absent_companion_does_not_block_player_upgrade(scene):
    scene._companion = None
    scene._open_upgrade_ui()
    top = scene._top_available_indices()
    scene._confirm_zone(top, [])
    assert scene._upg_zone == "confirm"
    scene._confirm_zone(top, [])
    assert not scene._upgrading
    assert scene.player.weapon.main_level == 1


def test_upgrade_draw_offers_early_addons_and_keeps_long_key_hints_on_screen(scene):
    scene._open_upgrade_ui()
    scene.game.displays.update(ui_accept="RIGHT CTRL", ui_back="LEFT SHIFT")
    scene._draw_upgrade_ui(pygame.Surface((800, 600), pygame.SRCALPHA))
    text = "\n".join(text for text, _ in scene.game.records)
    assert "主砲 Lv2で解放" not in text
    assert "HOMING 1" in text and "LASER 1" in text
    assert "RIGHT CTRL" in text and "LEFT SHIFT" in text
    assert "保留して閉じる" in text
    assert all(width <= 752 for _, width in scene.game.records)


def test_laser_explanation_uses_bound_key_and_keeps_release_and_stop_instructions(scene):
    scene._open_upgrade_ui()
    scene._upg_top_cursor = 2  # laser
    scene.game.displays["laser"] = "RIGHT CTRL"
    scene._draw_upgrade_ui(pygame.Surface((800, 600), pygame.SRCALPHA))
    text = "".join(text for text, _ in scene.game.records)
    assert "[RIGHT CTRL] 押している間だけ発射。" in text
    assert "離すと停止・冷却。" in text
    assert all(width <= 752 for _, width in scene.game.records)


def test_empty_hud_omits_unavailable_actions_and_stays_in_top_band(scene):
    scene.player.weapon.weapon_stock = 0
    surface = pygame.Surface((800, 600), pygame.SRCALPHA)
    HUD(scene.game).draw(surface, scene.player, 0, 0, 0)
    text = "\n".join(text for text, _ in scene.game.records)
    assert "[V]" not in text and "[B]" not in text
    assert "未装備" not in text and "追加装備 なし" not in text
    assert "HP 100/100" in text
    assert surface.get_bounding_rect().bottom <= HUD_BOTTOM


def test_overheated_laser_does_not_advertise_ready_to_fire(scene):
    surface = pygame.Surface((800, 600), pygame.SRCALPHA)
    HUD(scene.game).draw(surface, scene.player, 0, 0, 0,
        heat=SimpleNamespace(overheated=True, ratio=1.0, display_temp=39.9),
        laser=SimpleNamespace(state="ready"))
    text = "\n".join(text for text, _ in scene.game.records)
    assert "熱暴走・冷却中" in text and "熱で停止" in text
    assert "発射可" not in text


def test_companion_only_stock_still_shows_the_upgrade_action(scene):
    scene.player.weapon.weapon_stock = 0
    surface = pygame.Surface((800, 600), pygame.SRCALPHA)
    HUD(scene.game).draw(surface, scene.player, 0, 0, 0, companion_stock=2)
    text = "\n".join(text for text, _ in scene.game.records)
    assert "[V]" in text and "自機0・先輩2" in text


def test_pause_uses_configured_back_key_to_resume(scene):
    scene._paused = True
    scene._draw_pause(pygame.Surface((800, 600), pygame.SRCALPHA))
    text = "\n".join(text for text, _ in scene.game.records)
    assert "一時停止" in text and "F10: ゲームを再開" in text
    scene.game.input.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F10))
    scene._update_pause()
    assert not scene._paused
