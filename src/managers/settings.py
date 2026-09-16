import json
from pathlib import Path
import pygame

from src.core.user_data import user_data_dir

_SETTINGS_PATH = user_data_dir() / "settings.json"

KEY_BINDING_DISPLAY_NAMES: dict[str, str] = {
    "move_up": "上へ移動",
    "move_down": "下へ移動",
    "move_left": "左へ移動",
    "move_right": "右へ移動",
    "fire": "ショット",
    "laser": "レーザー",
    "weapon_select": "ウェポン選択",
    "bomb": "持駒を打つ",
    "pause": "ポーズ",
    "ui_accept": "メニュー決定",
    "ui_back": "メニュー戻る",
}

_DEFAULTS: dict = {
    "bgm_volume": 0.8,
    "se_volume": 1.0,
    "key_bindings": {
        "move_up":    "K_UP",
        "move_down":  "K_DOWN",
        "move_left":  "K_LEFT",
        "move_right": "K_RIGHT",
        "fire":          "K_z",
        "laser":         "K_SPACE",
        "weapon_select": "K_v",
        "bomb":          "K_b",
        "pause":         "K_x",
        "ui_accept":     "K_RETURN",
        "ui_back":       "K_x",
    },
}


def _pygame_key_names() -> dict[int, str]:
    """Return one stable pygame constant name for each supported key code."""
    names: dict[int, str] = {}
    for name, value in vars(pygame).items():
        if name.startswith("K_") and isinstance(value, int):
            names.setdefault(value, name)
    return names


_PYGAME_KEY_NAMES = _pygame_key_names()
_MENU_NAV_KEYS = frozenset({pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT})


class SettingsManager:
    def __init__(self) -> None:
        self._data: dict = {
            k: (v.copy() if isinstance(v, dict) else v)
            for k, v in _DEFAULTS.items()
        }
        self._load()

    def _load(self) -> None:
        if _SETTINGS_PATH.exists():
            try:
                with open(_SETTINGS_PATH, encoding="utf-8") as f:
                    loaded = json.load(f)
                if not isinstance(loaded, dict):
                    return
                # key_bindings はデフォルトにマージ（欠損・不正キーはデフォルト維持）
                bindings = loaded.pop("key_bindings", None)
                if isinstance(bindings, dict):
                    valid_bindings = {
                        action: key_name
                        for action, key_name in bindings.items()
                        if (
                            action in _DEFAULTS["key_bindings"]
                            and isinstance(key_name, str)
                            and isinstance(getattr(pygame, key_name, None), int)
                        )
                    }
                    self._data["key_bindings"].update(valid_bindings)
                    self._repair_menu_binding_conflicts()
                for key in ("bgm_volume", "se_volume"):
                    value = loaded.get(key)
                    if isinstance(value, (int, float)):
                        self._data[key] = max(0.0, min(1.0, float(value)))
            except (json.JSONDecodeError, OSError):
                pass  # 破損ファイルはデフォルト値で継続

    def save(self) -> None:
        try:
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        """値をメモリ上で更新する。保存は save() を明示的に呼ぶか SettingsScene.on_exit で行う。"""
        self._data[key] = value

    def get_key(self, action: str) -> int:
        """アクション名 → pygame キー定数（int）を返す。未定義時はデフォルト値を使用。"""
        bindings = self._data.get("key_bindings", {})
        key_name = bindings.get(action) or _DEFAULTS["key_bindings"].get(action, "K_RETURN")
        key = getattr(pygame, key_name, None)
        if isinstance(key, int):
            return key
        default_name = _DEFAULTS["key_bindings"].get(action, "K_RETURN")
        return getattr(pygame, default_name, pygame.K_RETURN)

    def get_key_bindings(self) -> dict[str, int]:
        """Return a detached action-to-pygame-key mapping in settings UI order."""
        return {
            action: self.get_key(action)
            for action in KEY_BINDING_DISPLAY_NAMES
        }

    def set_key_binding(self, action: str, key: int) -> bool:
        """Bind ``action`` to ``key``; return False for unsupported input."""
        if action not in _DEFAULTS["key_bindings"] or type(key) is not int:
            return False
        key_name = _PYGAME_KEY_NAMES.get(key)
        if key_name is None:
            return False
        if self._menu_binding_conflicts(action, key):
            return False
        self._data["key_bindings"][action] = key_name
        return True

    def _menu_binding_conflicts(self, action: str, key: int) -> bool:
        """Keep menu navigation usable while allowing pause/back to share a key."""
        if action not in {"ui_accept", "ui_back", "pause"}:
            return False
        if key in _MENU_NAV_KEYS:
            return True
        if action == "ui_accept":
            return key in {self.get_key("ui_back"), self.get_key("pause")}
        return key == self.get_key("ui_accept")

    def _repair_menu_binding_conflicts(self) -> None:
        """Repair hand-edited or legacy settings that could trap menu input."""
        bindings = self._data["key_bindings"]
        accept = self.get_key("ui_accept")
        back = self.get_key("ui_back")
        pause = self.get_key("pause")
        if accept in _MENU_NAV_KEYS or accept in {back, pause}:
            bindings["ui_accept"] = _DEFAULTS["key_bindings"]["ui_accept"]
            accept = self.get_key("ui_accept")
        if back in _MENU_NAV_KEYS or back == accept:
            bindings["ui_back"] = _DEFAULTS["key_bindings"]["ui_back"]
        if pause in _MENU_NAV_KEYS or pause == accept:
            bindings["pause"] = _DEFAULTS["key_bindings"]["pause"]

    def reset_key_bindings(self) -> None:
        """Restore every gameplay and UI action to its default key."""
        self._data["key_bindings"] = _DEFAULTS["key_bindings"].copy()

    def action_display_name(self, action: str) -> str:
        """Return the user-facing Japanese name for a configurable action."""
        return KEY_BINDING_DISPLAY_NAMES.get(action, action)

    def key_display(self, action: str) -> str:
        """アクション名 → 表示用キー名（例: "Z" / "SPACE" / "X"）。
        チュートリアル等でキーバインドとズレない表示を作るために使う。"""
        bindings = self._data.get("key_bindings", {})
        key_name = bindings.get(action) or _DEFAULTS["key_bindings"].get(action, "K_RETURN")
        name = key_name[2:] if key_name.startswith("K_") else key_name
        return {"RETURN": "ENTER"}.get(name.upper(), name.upper())
