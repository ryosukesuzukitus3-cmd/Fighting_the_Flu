"""プレイログ分析ツール。

data/playlogs/ 以下の全 JSONL ファイルを読み込み、
バランス調整に役立つ統計をテキストまたはグラフで出力する。

使い方:
  python tools/analyze_log.py                    # テキストサマリー（全ファイル）
  python tools/analyze_log.py --since 20260324   # 日付フィルタ
  python tools/analyze_log.py --graph            # matplotlib グラフを表示
  python tools/analyze_log.py --export csv       # data/playlog_export.csv に出力
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

LOG_DIR = Path(__file__).parent.parent / "data" / "playlogs"


# ══════════════════════════════════════════════════════════════════
# データロード
# ══════════════════════════════════════════════════════════════════

def load_runs(since: str | None = None) -> list[dict]:
    """data/playlogs/ 以下の全 .jsonl を読み込み、run リストを返す。"""
    runs: list[dict] = []
    for path in sorted(LOG_DIR.glob("session_*.jsonl")):
        # --since フィルタ: ファイル名の日付部分と比較
        if since:
            date_part = path.stem.replace("session_", "")
            if date_part < since:
                continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        runs.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return runs


def events_of(run: dict, event_type: str) -> list[dict]:
    return [e for e in run.get("events", []) if e.get("type") == event_type]


# ══════════════════════════════════════════════════════════════════
# 分析モジュール
# ══════════════════════════════════════════════════════════════════

class SurvivalStats:
    """ステージ別 到達率・クリア率"""

    def __init__(self, runs: list[dict]) -> None:
        self.total   = len(runs)
        self.reached: dict[int, int] = defaultdict(int)
        self.cleared: dict[int, int] = defaultdict(int)

        for run in runs:
            visited: set[int] = set()
            for e in run.get("events", []):
                if e["type"] == "stage_start":
                    visited.add(e["stage"])
            for s in visited:
                self.reached[s] += 1
            # ボス撃破イベントをクリア判定に使う
            for e in run.get("events", []):
                if e["type"] == "boss_killed":
                    self.cleared[e["stage"]] += 1

    def print(self) -> None:
        print(f"\n=== SURVIVAL STATS ({self.total} runs) ===")
        for s in sorted(set(list(self.reached) + list(self.cleared))):
            reach = self.reached.get(s, 0)
            clear = self.cleared.get(s, 0)
            reach_pct = reach / self.total * 100 if self.total else 0
            clear_pct = clear / reach  * 100 if reach else 0
            bar_r = "█" * int(reach_pct / 5)
            bar_c = "█" * int(clear_pct / 5)
            print(f"  Stage {s}: 到達 {reach_pct:5.1f}% {bar_r}")
            print(f"          クリア {clear_pct:5.1f}% {bar_c}  ({clear}/{reach})")


class DeathHotspot:
    """ステージ内の死亡タイミング分布（10秒刻みのゾーン）"""

    def __init__(self, runs: list[dict]) -> None:
        # stage → list of elapsed_sec at death
        self.deaths: dict[int, list[float]] = defaultdict(list)
        for run in runs:
            for e in events_of(run, "player_death"):
                self.deaths[e["stage"]].append(e.get("elapsed_sec", 0.0))

    def print(self) -> None:
        print("\n=== DEATH HOTSPOT (ステージ内の死亡タイミング) ===")
        for s in sorted(self.deaths):
            times = sorted(self.deaths[s])
            if not times:
                continue
            total = len(times)
            print(f"  Stage {s}: {total} 件  "
                  f"avg={mean(times):.1f}s  med={median(times):.1f}s  "
                  f"min={times[0]:.1f}s  max={times[-1]:.1f}s")
            # 10秒ゾーン集計
            bucket: dict[int, int] = defaultdict(int)
            for t in times:
                bucket[int(t // 10) * 10] += 1
            peak_zone = max(bucket, key=lambda z: bucket[z])
            print(f"    集中ゾーン: t={peak_zone}~{peak_zone+10}s "
                  f"({bucket[peak_zone]}/{total} 件)")
            # 分布バー
            for zone in sorted(bucket):
                bar = "■" * bucket[zone]
                print(f"    t={zone:>3}~{zone+10:<3}s | {bar} {bucket[zone]}")


class BossKillTimes:
    """ボス撃破タイム集計"""

    def __init__(self, runs: list[dict]) -> None:
        # stage → list of elapsed_sec
        self.times:   dict[int, list[float]] = defaultdict(list)
        self.weapons: dict[int, list[dict]]  = defaultdict(list)
        for run in runs:
            for e in events_of(run, "boss_killed"):
                s = e["stage"]
                self.times[s].append(e.get("elapsed_sec", 0.0))
                w = e.get("weapon")
                if w:
                    self.weapons[s].append(w)

    @staticmethod
    def _load_boss_appear_times() -> dict[int, float]:
        """data/stages/stage*.json の最初の Boss イベント時刻を返す。"""
        import json
        stages_dir = Path(__file__).parent.parent / "data" / "stages"
        result: dict[int, float] = {}
        for p in sorted(stages_dir.glob("stage*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                sid = int(data["stage_id"])
                for ev in data.get("events", []):
                    if ev.get("type") == "Boss":
                        result[sid] = float(ev["time"])
                        break
            except (KeyError, ValueError, json.JSONDecodeError):
                pass
        return result

    def print(self) -> None:
        print("\n=== BOSS KILL TIME ===")
        _BOSS_APPEAR = self._load_boss_appear_times()
        for s in sorted(self.times):
            ts = sorted(self.times[s])
            if not ts:
                continue
            appear = _BOSS_APPEAR.get(s, 0)
            avg    = mean(ts)
            med    = median(ts)
            alive  = avg - appear
            print(f"  Stage {s}: {len(ts)} 件  "
                  f"avg={avg:.1f}s  med={med:.1f}s  "
                  f"min={ts[0]:.1f}s  max={ts[-1]:.1f}s")
            print(f"    ボス登場=t{appear}s  → ボス生存 avg {alive:.1f}s")


class WeaponStateAtDeath:
    """死亡時・ボス撃破時の武器状態分析"""

    def __init__(self, runs: list[dict]) -> None:
        self.death_weapons:    dict[int, list[dict]] = defaultdict(list)
        self.boss_kill_weapons: dict[int, list[dict]] = defaultdict(list)
        for run in runs:
            for e in events_of(run, "player_death"):
                w = e.get("weapon")
                if w:
                    self.death_weapons[e["stage"]].append(w)
            for e in events_of(run, "boss_killed"):
                w = e.get("weapon")
                if w:
                    self.boss_kill_weapons[e["stage"]].append(w)

    @staticmethod
    def _avg_field(snapshots: list[dict], field: str) -> str:
        vals = [s.get(field, 0) for s in snapshots]
        return f"{mean(vals):.1f}" if vals else "-"

    @staticmethod
    def _pct_zero(snapshots: list[dict], field: str) -> str:
        vals  = [s.get(field, 0) for s in snapshots]
        zeros = sum(1 for v in vals if v == 0)
        return f"{zeros}/{len(vals)}" if vals else "-"

    def _print_group(self, label: str, by_stage: dict[int, list[dict]]) -> None:
        fields = ["main_level", "laser_level", "homing_level", "speed_level", "has_barrier"]
        for s in sorted(by_stage):
            snaps = by_stage[s]
            if not snaps:
                continue
            print(f"  Stage {s} ({label}, {len(snaps)} 件):")
            for f in fields:
                avg  = self._avg_field(snaps, f)
                zero = self._pct_zero(snaps, f)
                print(f"    {f:<15} avg={avg:<5}  未取得={zero}")
            # 警告: main_level がほぼ 0 のとき
            ml = [s.get("main_level", 0) for s in snaps]
            if mean(ml) < 0.5:
                print(f"    ⚠ main_level がほぼ 0 — "
                      f"ウェポンアップグレードが機能していない可能性")

    def print(self) -> None:
        print("\n=== WEAPON STATE AT DEATH ===")
        self._print_group("死亡時", self.death_weapons)
        if any(self.boss_kill_weapons.values()):
            print("\n=== WEAPON STATE AT BOSS KILL ===")
            self._print_group("ボス撃破時", self.boss_kill_weapons)
        else:
            print("\n  ℹ boss_killed の weapon データなし "
                  "(旧ログ形式。新プレイ後に自動追加されます)")


# ══════════════════════════════════════════════════════════════════
# CSV エクスポート
# ══════════════════════════════════════════════════════════════════

def export_csv(runs: list[dict]) -> None:
    import csv
    out_path = Path(__file__).parent.parent / "data" / "playlog_export.csv"
    rows = []
    for run in runs:
        base = {
            "started_at":   run.get("started_at", ""),
            "ended_at":     run.get("ended_at", ""),
            "cleared":      run.get("cleared", False),
            "stage_reached": run.get("stage_reached", 1),
            "score":        run.get("score", 0),
            "kill_count":   run.get("kill_count", 0),
        }
        for e in run.get("events", []):
            row = dict(base)
            row["event_type"] = e.get("type", "")
            row["event_ts"]   = e.get("ts", "")
            row["stage"]      = e.get("stage", "")
            row["elapsed_sec"] = e.get("elapsed_sec", "")
            w = e.get("weapon", {})
            for wf in ("main_level", "laser_level", "homing_level",
                       "speed_level", "magnet_level", "has_barrier"):
                row[f"w_{wf}"] = w.get(wf, "") if w else ""
            rows.append(row)

    if not rows:
        print("エクスポートするデータがありません。")
        return

    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"エクスポート完了: {out_path}  ({len(rows)} 行)")


# ══════════════════════════════════════════════════════════════════
# グラフ出力
# ══════════════════════════════════════════════════════════════════

def show_graphs(runs: list[dict]) -> None:
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.rcParams["font.family"] = ["MS Gothic", "DejaVu Sans"]
    except ImportError:
        print("ERROR: matplotlib が必要です。  pip install matplotlib")
        return

    surv  = SurvivalStats(runs)
    death = DeathHotspot(runs)
    bkt   = BossKillTimes(runs)

    stages = sorted(surv.reached)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(f"プレイログ分析  ({len(runs)} runs)", fontsize=14)

    # グラフ1: ステージ到達・クリア率
    ax = axes[0]
    reach_pcts = [surv.reached.get(s, 0) / surv.total * 100 for s in stages]
    clear_pcts = [
        surv.cleared.get(s, 0) / surv.reached[s] * 100 if surv.reached.get(s) else 0
        for s in stages
    ]
    x = range(len(stages))
    ax.bar([i - 0.2 for i in x], reach_pcts, width=0.4, label="到達率", color="steelblue")
    ax.bar([i + 0.2 for i in x], clear_pcts, width=0.4, label="クリア率", color="tomato")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"Stage {s}" for s in stages])
    ax.set_ylabel("%")
    ax.set_ylim(0, 110)
    ax.legend()
    ax.set_title("ステージ到達・クリア率")

    # グラフ2: 死亡タイミング分布（ステージ別ヒストグラム）
    ax = axes[1]
    colors = ["steelblue", "tomato", "seagreen", "orange"]
    for i, s in enumerate(sorted(death.deaths)):
        times = death.deaths[s]
        if times:
            ax.hist(times, bins=range(0, 120, 10), alpha=0.6,
                    label=f"Stage {s}", color=colors[i % len(colors)])
    ax.set_xlabel("ステージ経過秒")
    ax.set_ylabel("死亡数")
    ax.legend()
    ax.set_title("死亡タイミング分布")

    # グラフ3: ボス撃破タイム
    ax = axes[2]
    for i, s in enumerate(sorted(bkt.times)):
        ts = bkt.times[s]
        if ts:
            ax.boxplot(ts, positions=[s], widths=0.5,
                       patch_artist=True,
                       boxprops=dict(facecolor=colors[i % len(colors)], alpha=0.6))
    ax.set_xlabel("Stage")
    ax.set_ylabel("経過秒 (stage_start から)")
    ax.set_title("ボス撃破タイム分布")
    ax.set_xticks(stages)

    plt.tight_layout()
    plt.show()


# ══════════════════════════════════════════════════════════════════
# エントリポイント
# ══════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="プレイログ分析ツール")
    parser.add_argument("--since",  type=str, default=None,
                        help="この日付以降のログのみ対象 (例: 20260324)")
    parser.add_argument("--graph",  action="store_true",
                        help="matplotlib グラフを表示")
    parser.add_argument("--export", choices=["csv"],
                        help="エクスポート形式")
    args = parser.parse_args()

    if not LOG_DIR.exists():
        print(f"ERROR: ログディレクトリが見つかりません: {LOG_DIR}")
        sys.exit(1)

    runs = load_runs(since=args.since)
    if not runs:
        print("ログデータが見つかりませんでした。")
        sys.exit(0)

    print(f"ログ読み込み完了: {len(runs)} runs  (フィルタ: since={args.since or 'なし'})")

    if args.export == "csv":
        export_csv(runs)
        return

    # テキストサマリー
    SurvivalStats(runs).print()
    DeathHotspot(runs).print()
    BossKillTimes(runs).print()
    WeaponStateAtDeath(runs).print()

    if args.graph:
        show_graphs(runs)


if __name__ == "__main__":
    main()
