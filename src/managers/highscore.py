import json
from pathlib import Path

from src.core.user_data import user_data_dir

_HIGHSCORE_PATH = user_data_dir() / "highscore.json"
_MAX_ENTRIES = 10


class HighScoreManager:
    def __init__(self) -> None:
        self._scores: list[dict] = []
        self._load()

    def _load(self) -> None:
        if _HIGHSCORE_PATH.exists():
            try:
                with open(_HIGHSCORE_PATH, encoding="utf-8") as f:
                    self._scores = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._scores = []  # 破損ファイルは空スコアで継続

    def save(self) -> None:
        with open(_HIGHSCORE_PATH, "w", encoding="utf-8") as f:
            json.dump(self._scores, f, ensure_ascii=False, indent=2)

    def add(self, name: str, score: int, stage: int) -> None:
        self._scores.append({"name": name, "score": score, "stage": stage})
        self._scores.sort(key=lambda x: x["score"], reverse=True)
        self._scores = self._scores[:_MAX_ENTRIES]
        for i, entry in enumerate(self._scores):
            entry["rank"] = i + 1
        self.save()

    def get_scores(self) -> list[dict]:
        return self._scores

    def is_high_score(self, score: int) -> bool:
        if len(self._scores) < _MAX_ENTRIES:
            return True
        return score > self._scores[-1]["score"]
