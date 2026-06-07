"""
プレイデータ収集ロガー。
ゲームバランス改善のためのローカルセッションログを data/playlogs/ に JSONL 形式で記録する。

収集データ（すべてローカルファイルのみ、外部送信なし）:
  - セッション開始・終了時刻
  - ステージ到達数・クリアフラグ
  - 死亡時のステージ・HP・経過時間・最終武器構成
  - ボス撃破時間
  - スコア・キル数
"""
from __future__ import annotations
import json
import time
from datetime import datetime
from pathlib import Path

_LOG_DIR = Path(__file__).parent.parent.parent / "data" / "playlogs"


class PlayLogger:
    def __init__(self) -> None:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        self._path = _LOG_DIR / f"session_{today}.jsonl"
        self._run: dict = {}

    # ── セッション管理 ───────────────────────────────────────────

    def begin_run(self) -> None:
        """プレイ開始（ステージ1スタート時）"""
        self._run = {
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "stage_reached": 1,
            "cleared": False,
            "score": 0,
            "kill_count": 0,
            "events": [],
        }

    def end_run(self, *, cleared: bool, score: int, kill_count: int) -> None:
        """プレイ終了（ゲームオーバー / ゲームクリア時）"""
        if not self._run:
            return
        self._run.update({
            "ended_at":   datetime.now().isoformat(timespec="seconds"),
            "cleared":    cleared,
            "score":      score,
            "kill_count": kill_count,
        })
        self._flush()

    # ── イベント記録 ─────────────────────────────────────────────

    def log_stage_start(self, stage_id: int) -> None:
        self._run["stage_reached"] = max(self._run.get("stage_reached", 1), stage_id)
        self._event("stage_start", stage=stage_id)

    def log_player_death(
        self,
        stage_id: int,
        elapsed: float,
        hp: int,
        weapon_snapshot: dict,
    ) -> None:
        self._event(
            "player_death",
            stage=stage_id,
            elapsed_sec=round(elapsed, 1),
            hp_remaining=hp,
            weapon=weapon_snapshot,
        )

    def log_boss_killed(
        self,
        stage_id: int,
        elapsed_since_spawn: float,
        weapon_snapshot: dict | None = None,
    ) -> None:
        kwargs: dict = dict(
            stage=stage_id,
            elapsed_sec=round(elapsed_since_spawn, 1),
        )
        if weapon_snapshot is not None:
            kwargs["weapon"] = weapon_snapshot
        self._event("boss_killed", **kwargs)

    # ── 内部 ─────────────────────────────────────────────────────

    def _event(self, event_type: str, **kwargs) -> None:
        if not self._run:
            return
        entry = {"type": event_type, "ts": datetime.now().isoformat(timespec="seconds")}
        entry.update(kwargs)
        self._run.setdefault("events", []).append(entry)

    # ── 統計用読み込み ────────────────────────────────────────────

    @staticmethod
    def load_all_sessions() -> list[dict]:
        """全 JSONL ファイルを読み込んでセッション一覧を返す。読み込み失敗行は無視。"""
        sessions: list[dict] = []
        if not _LOG_DIR.exists():
            return sessions
        for path in sorted(_LOG_DIR.glob("session_*.jsonl")):
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        sessions.append(json.loads(line))
            except (OSError, json.JSONDecodeError):
                pass
        return sessions

    # ── 内部 ─────────────────────────────────────────────────────

    def _flush(self) -> None:
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(self._run, ensure_ascii=False) + "\n")
        except OSError:
            pass
        self._run = {}
