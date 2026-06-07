from pathlib import Path
import pygame

_ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"


class ResourceManager:
    def __init__(self) -> None:
        self._images: dict[str, pygame.Surface] = {}
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._fonts:  dict[tuple, pygame.font.Font] = {}

    def image(self, path: str) -> pygame.Surface:
        if path not in self._images:
            surf = pygame.image.load(_ASSETS_DIR / path)
            suffix = Path(path).suffix.lower()
            self._images[path] = surf.convert_alpha() if suffix in (".png", ".gif", ".bmp") else surf.convert()
        return self._images[path]

    def sound(self, path: str) -> pygame.mixer.Sound:
        if path not in self._sounds:
            self._sounds[path] = pygame.mixer.Sound(_ASSETS_DIR / path)
        return self._sounds[path]

    def font(self, path: str, size: int) -> pygame.font.Font:
        key = (path, size)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.Font(_ASSETS_DIR / path, size)
        return self._fonts[key]

    def sysfont(self, name: str, size: int) -> pygame.font.Font:
        key = (name, size)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.SysFont(name, size)
        return self._fonts[key]

    def jpfont(self, size: int) -> pygame.font.Font:
        """日本語対応システムフォントを返す（Meiryo / Yu Gothic / MS Gothic の順で試みる）"""
        key = ("__jp__", size)
        if key not in self._fonts:
            for name in ("meiryo", "yugothic", "msgothic", "msgothic"):
                f = pygame.font.SysFont(name, size)
                if f is not None:
                    self._fonts[key] = f
                    break
            else:
                self._fonts[key] = pygame.font.SysFont(None, size)
        return self._fonts[key]

    def pixelfont(self, size: int) -> pygame.font.Font:
        """ピクセル風日本語フォント（DotGothic16）"""
        key = ("__pixel__", size)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.Font(
                _ASSETS_DIR / "font/DotGothic16-Regular.ttf", size
            )
        return self._fonts[key]
