from __future__ import annotations
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.managers.playlog import PlayLogger


def _compute_stats(sessions: list[dict]) -> dict | None:
    from src.core.registries import stage_ids

    valid_stages = stage_ids()
    max_stage = max(valid_stages) if valid_stages else 0

    def reached_stage(session: dict) -> int:
        try:
            return int(session.get("stage_reached", 1))
        except (TypeError, ValueError):
            return 1

    sessions = [
        s for s in sessions
        if 1 <= reached_stage(s) <= max_stage
    ]
    n = len(sessions)
    if n == 0:
        return None

    cleared   = sum(1 for s in sessions if s.get("cleared"))
    avg_stage = sum(reached_stage(s) for s in sessions) / n
    best_score = max(s.get("score", 0) for s in sessions)

    # ステージ別生存率: そのステージに到達したセッション数 / 総プレイ数
    survival: dict[int, int] = {}
    for stage in valid_stages:
        survival[stage] = sum(1 for s in sessions if reached_stage(s) >= stage)

    # ボス撃破タイム（boss_killedイベントのelapsed_secを平均）
    boss_times: dict[int, list[float]] = {stage: [] for stage in valid_stages}
    for s in sessions:
        for ev in s.get("events", []):
            if ev.get("type") == "boss_killed":
                st = ev.get("stage")
                if st in boss_times:
                    boss_times[st].append(float(ev.get("elapsed_sec", 0)))

    avg_boss: dict[int, float | None] = {
        st: (sum(t) / len(t) if t else None)
        for st, t in boss_times.items()
    }

    # ── 死亡分析（player_death イベント）──────────────────────────
    death_times: dict[int, list[float]] = {stage: [] for stage in valid_stages}
    death_weapons: list[dict] = []
    for s in sessions:
        for ev in s.get("events", []):
            if ev.get("type") == "player_death":
                st = ev.get("stage")
                if st in death_times:
                    death_times[st].append(float(ev.get("elapsed_sec", 0.0)))
                w = ev.get("weapon")
                if w:
                    death_weapons.append(w)

    # ステージ別の死亡ホットスポット（10秒刻みの最多ゾーン）
    death_hotspot: dict[int, tuple[int, int, int]] = {}
    for st, times in death_times.items():
        if not times:
            continue
        bucket: dict[int, int] = {}
        for t in times:
            z = int(t // 10) * 10
            bucket[z] = bucket.get(z, 0) + 1
        peak = max(bucket, key=lambda z: bucket[z])
        death_hotspot[st] = (peak, bucket[peak], len(times))

    # 死亡時の平均武器状態
    _fields = ["main_level", "speed_level", "laser_level",
               "homing_level", "magnet_level", "has_barrier"]
    death_field_avg: dict[str, float | None] = {}
    for f in _fields:
        vals = [float(w.get(f, 0)) for w in death_weapons]
        death_field_avg[f] = (sum(vals) / len(vals)) if vals else None
    deaths_total = len(death_weapons)
    low_main = sum(1 for w in death_weapons if w.get("main_level", 0) == 0)

    return {
        "n":          n,
        "cleared":    cleared,
        "avg_stage":  avg_stage,
        "best_score": best_score,
        "stages":     valid_stages,
        "survival":   survival,
        "avg_boss":   avg_boss,
        "death_hotspot":   death_hotspot,
        "death_field_avg": death_field_avg,
        "deaths_total":    deaths_total,
        "low_main":        low_main,
    }


class StatsScene(Scene):
    _BAR_W  = 120   # 生存率バーの最大幅（px）
    _BAR_H  = 14

    def on_enter(self) -> None:
        self._font_title = self.game.resources.pixelfont(38)
        self._font_head  = self.game.resources.pixelfont(22)
        self._font_row   = self.game.resources.pixelfont(20)
        self._font_hint  = self.game.resources.pixelfont(18)

        sessions   = PlayLogger.load_all_sessions()
        self._stats = _compute_stats(sessions)
        self._page  = 0
        self._n_pages = 3   # 0:サマリー 1:死亡ホットスポット 2:死亡時武器

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        inp = self.game.input
        if inp.is_just_pressed(pygame.K_RIGHT):
            self._page = min(self._page + 1, self._n_pages - 1)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
        elif inp.is_just_pressed(pygame.K_LEFT):
            self._page = max(self._page - 1, 0)
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
        elif inp.is_just_pressed(pygame.K_x) or inp.is_just_pressed(pygame.K_SPACE):
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)
            from src.scenes.title import TitleScene
            self.game.change_scene(TitleScene(self.game))

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((10, 10, 25))
        cx = SCREEN_WIDTH // 2

        # タイトル
        title = self._font_title.render("PLAY STATISTICS", True, (255, 220, 60))
        screen.blit(title, (cx - title.get_width() // 2, 36))

        if self._stats is None:
            msg = self._font_head.render("まだプレイデータがありません", True, (120, 120, 120))
            screen.blit(msg, (cx - msg.get_width() // 2, 260))
        elif self._page == 0:
            self._draw_summary(screen, cx)
            self._draw_stage_table(screen, cx)
        elif self._page == 1:
            self._draw_death_hotspot(screen, cx)
        else:
            self._draw_death_weapons(screen, cx)

        # ページインジケーター
        if self._stats is not None:
            dots = "  ".join("●" if i == self._page else "○" for i in range(self._n_pages))
            dsurf = self._font_hint.render(dots, True, (90, 110, 150))
            screen.blit(dsurf, (cx - dsurf.get_width() // 2, SCREEN_HEIGHT - 64))

        hint = self._font_hint.render("←→: ページ切替    X / SPACE: タイトルへ戻る", True, (80, 80, 80))
        screen.blit(hint, (cx - hint.get_width() // 2, SCREEN_HEIGHT - 38))

    # ── 描画サブルーチン ──────────────────────────────────────────

    def _draw_summary(self, screen: pygame.Surface, cx: int) -> None:
        st = self._stats
        n  = st["n"]

        rows = [
            ("総プレイ回数",      f"{n} 回"),
            ("クリア",           f"{st['cleared']} / {n}"),
            ("平均到達ステージ",  f"{st['avg_stage']:.1f}"),
            ("最高スコア",        f"{st['best_score']:,}"),
        ]

        y = 104
        for label, value in rows:
            lbl  = self._font_head.render(label, True, (160, 160, 220))
            val  = self._font_head.render(value, True, (220, 220, 220))
            screen.blit(lbl, (cx - 220, y))
            screen.blit(val, (cx + 80,  y))
            y += 32

    def _draw_stage_table(self, screen: pygame.Surface, cx: int) -> None:
        st = self._stats
        n  = st["n"]

        # セクション見出し
        y_head = 248
        pygame.draw.line(screen, (60, 60, 100), (cx - 220, y_head - 6), (cx + 220, y_head - 6))
        head = self._font_head.render("ステージ別", True, (160, 160, 220))
        screen.blit(head, (cx - 220, y_head))

        col_bar   = cx - 60
        col_pct   = cx + 72
        col_boss  = cx + 140

        sub = self._font_row.render("生存率", True, (120, 120, 180))
        screen.blit(sub, (col_bar, y_head))
        sub2 = self._font_row.render("ボス撃破", True, (120, 120, 180))
        screen.blit(sub2, (col_boss, y_head))

        y = y_head + 34
        for stage in st["stages"]:
            reached  = st["survival"][stage]
            rate     = reached / n if n > 0 else 0.0
            avg_boss = st["avg_boss"][stage]

            # ステージ名
            lbl = self._font_row.render(f"Stage {stage}", True, (200, 200, 200))
            screen.blit(lbl, (cx - 220, y))

            # 生存率バー
            bar_filled = int(self._BAR_W * rate)
            bar_rect   = pygame.Rect(col_bar, y + 2, self._BAR_W, self._BAR_H)
            fill_rect  = pygame.Rect(col_bar, y + 2, bar_filled, self._BAR_H)
            pygame.draw.rect(screen, (40, 40, 70), bar_rect, border_radius=3)
            if bar_filled > 0:
                bar_color = _rate_color(rate)
                pygame.draw.rect(screen, bar_color, fill_rect, border_radius=3)

            # 生存率テキスト
            pct = self._font_row.render(f"{rate * 100:.0f}%", True, (200, 200, 200))
            screen.blit(pct, (col_pct, y))

            # ボス平均撃破タイム
            if avg_boss is not None:
                boss_txt = self._font_row.render(f"avg {avg_boss:.0f}s", True, (180, 220, 180))
            else:
                boss_txt = self._font_row.render("---", True, (80, 80, 80))
            screen.blit(boss_txt, (col_boss, y))

            y += 36


    # ── P2: 死亡ホットスポット ────────────────────────────────────
    def _draw_death_hotspot(self, screen: pygame.Surface, cx: int) -> None:
        st = self._stats
        head = self._font_head.render("死亡ホットスポット（ステージ別）", True, (220, 160, 160))
        screen.blit(head, (cx - 220, 104))

        hotspot = st.get("death_hotspot", {})
        if not hotspot:
            msg = self._font_row.render("死亡データがありません", True, (120, 120, 120))
            screen.blit(msg, (cx - 220, 160))
            return

        y = 156
        for stage in st["stages"]:
            if stage not in hotspot:
                continue
            zone, cnt, total = hotspot[stage]
            line = f"Stage {stage}:  ピーク {zone}-{zone + 10}s  ({cnt}/{total} 件)"
            surf = self._font_row.render(line, True, (220, 210, 210))
            screen.blit(surf, (cx - 220, y))
            # 簡易バー（ピーク件数）
            bar_w = min(240, cnt * 24)
            pygame.draw.rect(screen, (200, 90, 70), (cx - 220, y + 26, bar_w, 8), border_radius=3)
            y += 50

    # ── P3: 死亡時の武器状態 ──────────────────────────────────────
    def _draw_death_weapons(self, screen: pygame.Surface, cx: int) -> None:
        st = self._stats
        head = self._font_head.render("死亡時の平均武器状態", True, (160, 200, 220))
        screen.blit(head, (cx - 220, 104))

        total = st.get("deaths_total", 0)
        if total == 0:
            msg = self._font_row.render("死亡データがありません", True, (120, 120, 120))
            screen.blit(msg, (cx - 220, 160))
            return

        favg = st.get("death_field_avg", {})
        rows = [
            ("MAIN",    favg.get("main_level")),
            ("SPEED",   favg.get("speed_level")),
            ("LASER",   favg.get("laser_level")),
            ("HOMING",  favg.get("homing_level")),
            ("MAGNET",  favg.get("magnet_level")),
            ("BARRIER", favg.get("has_barrier")),
        ]
        y = 156
        for label, val in rows:
            txt = f"{label:<8}: {val:.2f}" if val is not None else f"{label:<8}: -"
            surf = self._font_row.render(txt, True, (220, 220, 220))
            screen.blit(surf, (cx - 220, y))
            y += 30

        low = st.get("low_main", 0)
        warn_col = (240, 120, 100) if (total and low / total >= 0.5) else (160, 160, 160)
        warn = self._font_row.render(
            f"low main deaths: {low}/{total}（MAIN未強化での死亡）", True, warn_col)
        screen.blit(warn, (cx - 220, y + 12))


def _rate_color(rate: float) -> tuple[int, int, int]:
    """生存率に応じて緑→黄→赤のグラデーション色を返す"""
    if rate >= 0.7:
        return (60, 200, 100)
    if rate >= 0.4:
        return (220, 200, 60)
    return (200, 80, 60)
