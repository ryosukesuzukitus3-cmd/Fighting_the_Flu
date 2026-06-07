from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from src.managers.resource import ResourceManager
    from src.managers.settings import SettingsManager

# BGMファイルのフルパスを解決するためのアセットルート
_ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"


class SoundManager:
    """
    BGM は pygame.mixer.music（ストリーミング再生・メモリ効率良好）で管理。
    SE  は pygame.mixer.Sound（チャンネルベース音量制御）で管理。
    """

    def __init__(self, resources: ResourceManager, settings: SettingsManager) -> None:
        self._resources = resources
        self._bgm_volume: float = settings.get("bgm_volume", 0.8)
        self._se_volume:  float = settings.get("se_volume",  1.0)
        self._current_bgm_path: str = ""

    # ── BGM ──────────────────────────────────────────────────────────

    def set_bgm_volume(self, volume: float) -> None:
        self._bgm_volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self._bgm_volume)

    def play_bgm(self, path: str, loops: int = -1, volume: float | None = None) -> None:
        """BGMをストリーミング再生。既存BGMは即停止してから切り替える。

        volume を指定すると、その曲だけ基準音量(_bgm_volume)に対する倍率で再生する
        （例: volume=0.7 で基準の0.7倍）。次に別BGMを再生すると基準音量へ戻る。
        """
        self.stop_bgm()
        self._current_bgm_path = path
        vol = self._bgm_volume if volume is None else self._bgm_volume * volume
        pygame.mixer.music.load(str(_ASSETS_DIR / path))
        pygame.mixer.music.set_volume(vol)
        pygame.mixer.music.play(loops)

    def play_bgm_if_new(self, path: str, loops: int = -1) -> None:
        """同じBGMがすでに再生中なら再起動しない（タイトル画面復帰時のBGM維持用）"""
        if self._current_bgm_path == path and pygame.mixer.music.get_busy():
            return
        self.play_bgm(path, loops)

    def stop_bgm(self, fadeout_ms: int = 0) -> None:
        self._current_bgm_path = ""
        if fadeout_ms > 0:
            pygame.mixer.music.fadeout(fadeout_ms)
        else:
            pygame.mixer.music.stop()

    # ── SE ───────────────────────────────────────────────────────────

    def set_se_volume(self, volume: float) -> None:
        self._se_volume = max(0.0, min(1.0, volume))

    def play_se(self, path: str, volume: float = 1.0) -> None:
        """SEを再生。音量はチャンネルに設定し、キャッシュされたSoundオブジェクトを汚染しない。"""
        sound = self._resources.sound(path)
        channel = sound.play()
        if channel is not None:
            channel.set_volume(self._se_volume * volume)

    # ── エイリアス対応（story.aliases で BGM_*/SE_* を解決）─────────────

    def play_bgm_alias(self, alias: str | None, loops: int = -1) -> None:
        """BGM エイリアス（または生パス）を再生。未用意（None）なら何もしない。"""
        from src.story.aliases import bgm_path
        path = bgm_path(alias)
        if path:
            self.play_bgm(path, loops)

    def play_se_alias(self, alias: str | None, volume: float = 1.0) -> None:
        """SE エイリアス（または生パス）を再生。未用意（None）なら何もしない。"""
        from src.story.aliases import se_path
        path = se_path(alias)
        if path:
            self.play_se(path, volume)
