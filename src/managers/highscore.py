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
                    loaded = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._scores = []  # 破損ファイルは空スコアで継続
                return
            if not isinstance(loaded, list):
                self._scores = []
                return
            self._scores = self._ranked_scores(
                entry for entry in (self._score_entry(raw) for raw in loaded)
                if entry is not None
            )

    def save(self) -> None:
        try:
            with open(_HIGHSCORE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._scores, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def add(self, name: str, score: int, stage: int) -> None:
        self._scores = self._ranked_scores([
            *self._scores,
            {"name": name, "score": int(score), "stage": int(stage)},
        ])
        self.save()

    def get_scores(self) -> list[dict]:
        return self._scores

    def is_high_score(self, score: int) -> bool:
        if len(self._scores) < _MAX_ENTRIES:
            return True
        return score > self._scores[-1]["score"]

    def _score_entry(self, raw: object) -> dict | None:
        if not isinstance(raw, dict):
            return None
        try:
            score = int(raw["score"])
            stage = int(raw["stage"])
        except (KeyError, TypeError, ValueError):
            return None
        return {
            "name": str(raw.get("name", "")),
            "score": score,
            "stage": stage,
        }

    def _ranked_scores(self, scores) -> list[dict]:
        ranked = sorted(scores, key=lambda x: x["score"], reverse=True)[:_MAX_ENTRIES]
        for i, entry in enumerate(ranked):
            entry["rank"] = i + 1
        return ranked
