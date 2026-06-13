import json
from pathlib import Path
import pygame

from src.core.user_data import user_data_dir

_SETTINGS_PATH = user_data_dir() / "settings.json"

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
        "pause":         "K_x",
    },
}


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
                # key_bindings はデフォルトにマージ（欠損キーはデフォルト維持）
                bindings = loaded.pop("key_bindings", None)
                if isinstance(bindings, dict):
                    valid_bindings = {
                        action: key_name
                        for action, key_name in bindings.items()
                        if isinstance(action, str) and isinstance(key_name, str)
                    }
                    self._data["key_bindings"].update(valid_bindings)
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
        if action == "laser":
            return pygame.K_SPACE
        bindings  = self._data.get("key_bindings", {})
        key_name  = bindings.get(action) or _DEFAULTS["key_bindings"].get(action, "K_RETURN")
        return getattr(pygame, key_name, pygame.K_RETURN)

    def key_display(self, action: str) -> str:
        """アクション名 → 表示用キー名（例: "Z" / "SPACE" / "X"）。
        チュートリアル等でキーバインドとズレない表示を作るために使う。"""
        if action == "laser":
            return "SPACE"
        bindings = self._data.get("key_bindings", {})
        key_name = bindings.get(action) or _DEFAULTS["key_bindings"].get(action, "K_RETURN")
        name = key_name[2:] if key_name.startswith("K_") else key_name
        return name.upper()
