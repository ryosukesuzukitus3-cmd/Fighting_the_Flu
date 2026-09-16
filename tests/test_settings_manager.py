from __future__ import annotations

import json

import pygame

from src.managers import settings as settings_mod
from src.managers.input import InputManager


def _manager(tmp_path, monkeypatch) -> settings_mod.SettingsManager:
    monkeypatch.setattr(settings_mod, "_SETTINGS_PATH", tmp_path / "settings.json")
    return settings_mod.SettingsManager()


def test_shared_ui_actions_have_defaults_and_display_names(tmp_path, monkeypatch) -> None:
    manager = _manager(tmp_path, monkeypatch)

    assert manager.get_key("ui_accept") == pygame.K_RETURN
    assert manager.get_key("ui_back") == pygame.K_x
    assert manager.key_display("ui_accept") == "ENTER"
    assert manager.action_display_name("ui_accept") == "メニュー決定"
    assert manager.action_display_name("ui_back") == "メニュー戻る"


def test_set_save_load_and_reset_key_bindings(tmp_path, monkeypatch) -> None:
    manager = _manager(tmp_path, monkeypatch)

    assert manager.set_key_binding("fire", pygame.K_a) is True
    assert manager.set_key_binding("laser", pygame.K_l) is True
    assert manager.get_key("fire") == pygame.K_a
    assert manager.key_display("laser") == "L"
    manager.save()

    loaded = settings_mod.SettingsManager()
    assert loaded.get_key("fire") == pygame.K_a
    assert loaded.get_key("laser") == pygame.K_l

    loaded.reset_key_bindings()
    assert loaded.get_key("fire") == pygame.K_z
    assert loaded.get_key("laser") == pygame.K_SPACE


def test_set_key_binding_rejects_unknown_action_and_unsupported_key(tmp_path, monkeypatch) -> None:
    manager = _manager(tmp_path, monkeypatch)

    before = manager.get_key_bindings()
    assert manager.set_key_binding("not_an_action", pygame.K_q) is False
    assert manager.set_key_binding("fire", 999_999) is False
    assert manager.set_key_binding("fire", "K_q") is False  # type: ignore[arg-type]
    assert manager.set_key_binding("fire", True) is False  # type: ignore[arg-type]
    assert manager.get_key_bindings() == before


def test_menu_bindings_reject_navigation_and_command_conflicts(tmp_path, monkeypatch) -> None:
    manager = _manager(tmp_path, monkeypatch)

    assert manager.set_key_binding("ui_accept", pygame.K_DOWN) is False
    assert manager.set_key_binding("ui_accept", pygame.K_x) is False
    assert manager.set_key_binding("ui_back", pygame.K_RETURN) is False
    assert manager.set_key_binding("pause", pygame.K_RETURN) is False

    # Pause and menu-back intentionally share X by default.
    assert manager.get_key("ui_accept") == pygame.K_RETURN
    assert manager.get_key("ui_back") == pygame.K_x
    assert manager.get_key("pause") == pygame.K_x


def test_loading_repairs_menu_binding_conflicts(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "_SETTINGS_PATH", settings_path)
    settings_path.write_text(
        json.dumps(
            {
                "key_bindings": {
                    "ui_accept": "K_DOWN",
                    "ui_back": "K_RETURN",
                    "pause": "K_RETURN",
                }
            }
        ),
        encoding="utf-8",
    )

    manager = settings_mod.SettingsManager()

    assert manager.get_key("ui_accept") == pygame.K_RETURN
    assert manager.get_key("ui_back") == pygame.K_x
    assert manager.get_key("pause") == pygame.K_x


def test_loading_filters_unknown_actions_and_invalid_key_names(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "_SETTINGS_PATH", settings_path)
    settings_path.write_text(
        json.dumps(
            {
                "key_bindings": {
                    "fire": "K_a",
                    "laser": "NOT_A_PYGAME_KEY",
                    "unknown": "K_q",
                }
            }
        ),
        encoding="utf-8",
    )

    manager = settings_mod.SettingsManager()

    assert manager.get_key("fire") == pygame.K_a
    assert manager.get_key("laser") == pygame.K_SPACE
    assert "unknown" not in manager.get("key_bindings")


def test_input_manager_uses_rebound_ui_actions(tmp_path, monkeypatch) -> None:
    settings = _manager(tmp_path, monkeypatch)
    assert settings.set_key_binding("ui_accept", pygame.K_a)
    inp = InputManager(settings)

    inp.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))

    assert inp.is_action_just_pressed("ui_accept") is True
    assert inp.is_action_just_pressed("ui_back") is False
