from __future__ import annotations
import pygame
from src.core.scene import Scene
from src.managers.playlog import PlayLogger
from src.scenes.meta_ui import (
    ACCENT_CORAL,
    ACCENT_MINT,
    TEXT,
    TEXT_MUTED,
    draw_meta_background,
    draw_meta_footer,
    draw_meta_title,
    draw_pixel_cursor,
    fit_text,
)


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

    # ステージ別到達率: そのステージに到達したセッション数 / 総プレイ数
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
    _PAGE_LABELS = ("全体の記録", "倒れた時間帯", "倒れた時の装備")

    def on_enter(self) -> None:
        self._font_title = self.game.resources.pixelfont(38)
        self._font_head = self.game.resources.pixelfont(22)
        self._font_row = self.game.resources.pixelfont(20)
        self._font_hint = self.game.resources.pixelfont(18)
        self._stats = _compute_stats(PlayLogger.load_all_sessions())
        self._page = 0
        self._n_pages = len(self._PAGE_LABELS)

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        inp = self.game.input
        previous = self._page
        if inp.is_just_pressed(pygame.K_RIGHT):
            if self._stats is not None:
                self._page = min(self._page + 1, self._n_pages - 1)
        elif inp.is_just_pressed(pygame.K_LEFT):
            if self._stats is not None:
                self._page = max(self._page - 1, 0)
        elif (inp.is_action_just_pressed("ui_back")
              or inp.is_action_just_pressed("ui_accept")
              or inp.is_just_pressed(pygame.K_ESCAPE)):
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)
            from src.scenes.title import TitleScene
            self.game.change_scene(TitleScene(self.game))
        if previous != self._page:
            self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)

    def _text(self, screen, text, x, y, width, *, color=TEXT, font=None, right=False):
        font = font or self._font_row
        surface = font.render(fit_text(font, text, width), False, color)
        screen.blit(surface, (x + width - surface.get_width() if right else x, y))

    def draw(self, screen: pygame.Surface) -> None:
        draw_meta_background(screen)
        draw_meta_title(screen, self._font_title, "プレイ記録", accent=TEXT, y=22)
        if self._stats is None:
            for text, font, y, color in (
                ("まだプレイ記録がありません", self._font_head, 254, TEXT),
                ("プレイを終えると、到達した章や装備を振り返れます。", self._font_hint, 300, TEXT_MUTED),
            ):
                surface = font.render(text, False, color)
                screen.blit(surface, surface.get_rect(centerx=400, y=y))
        else:
            for i, label in enumerate(self._PAGE_LABELS):
                rect = pygame.Rect(70 + i * 224, 92, 212, 36)
                selected = i == self._page
                text = self._font_hint.render(label, False, ACCENT_CORAL if selected else TEXT_MUTED)
                text_rect = text.get_rect(centerx=rect.centerx, y=rect.y + 6)
                screen.blit(text, text_rect)
                if selected:
                    draw_pixel_cursor(screen, text_rect.left - 22, text_rect.centery)
            if self._page == 0:
                self._draw_summary(screen)
                self._draw_stage_table(screen)
            elif self._page == 1:
                self._draw_death_hotspot(screen)
            else:
                self._draw_death_weapons(screen)

        back = self.game.settings.key_display("ui_back")
        accept = self.game.settings.key_display("ui_accept")
        keys = " / ".join(dict.fromkeys((accept, back, "ESC")))
        pages = "←→: ページ切替   " if self._stats is not None else ""
        draw_meta_footer(screen, self._font_hint, f"{pages}{keys}: タイトルへ戻る")

    def _draw_summary(self, screen: pygame.Surface) -> None:
        st = self._stats
        rows = [
            ("プレイ回数", f"{st['n']:,} 回"),
            ("クリア回数", f"{st['cleared']:,} 回"),
            ("平均到達章", f"{st['avg_stage']:.1f} 章"),
            ("最高スコア", f"{st['best_score']:,}"),
        ]
        for i, (label, value) in enumerate(rows):
            y = 154 + i * 32
            self._text(screen, label, 98, y, 220, color=TEXT_MUTED)
            self._text(screen, value, 350, y, 352, right=True,
                       color=ACCENT_MINT if i == 3 else TEXT)

    def _draw_stage_table(self, screen: pygame.Surface) -> None:
        st = self._stats
        for x, width, label in ((98, 140, "章"), (262, 218, "到達率"), (494, 208, "ボス平均撃破時間")):
            self._text(screen, label, x, 300, width, font=self._font_hint, color=TEXT_MUTED)
        for i, stage in enumerate(st["stages"]):
            y = 334 + i * 35
            rate = st["survival"][stage] / st["n"]
            self._text(screen, f"第{stage}章", 98, y, 140)
            if rate:
                pygame.draw.rect(screen, ACCENT_MINT, (262, y + 8, round(130 * rate), 8))
            self._text(screen, f"{rate * 100:.0f}%", 402, y, 70, right=True)
            avg_boss = st["avg_boss"][stage]
            self._text(screen, "—" if avg_boss is None else f"{avg_boss:,.0f} 秒",
                       494, y, 208, right=True, color=ACCENT_MINT if avg_boss is not None else TEXT_MUTED)
        self._text(screen, "到達率：その章に進んだプレイの割合", 98, 484, 604,
                   font=self._font_hint, color=TEXT_MUTED)

    def _draw_death_hotspot(self, screen: pygame.Surface) -> None:
        st = self._stats
        hotspot = st.get("death_hotspot", {})
        self._text(screen, "倒れやすい時間帯", 98, 157, 604, font=self._font_head)
        self._text(screen, "章の開始からの時間を、10秒ごとに集計しています。", 98, 193, 604,
                   font=self._font_hint, color=TEXT_MUTED)
        if not hotspot:
            self._text(screen, "倒れた記録はありません", 98, 275, 604)
            return
        for x, width, label in ((98, 110, "章"), (250, 212, "最も多い時間帯"), (480, 222, "件数 / この章の総数")):
            self._text(screen, label, x, 236, width, font=self._font_hint, color=TEXT_MUTED)
        for i, stage in enumerate(st["stages"]):
            y = 272 + i * 52
            self._text(screen, f"第{stage}章", 98, y, 110)
            if stage not in hotspot:
                self._text(screen, "記録なし", 250, y, 212, color=TEXT_MUTED)
                continue
            zone, count, total = hotspot[stage]
            self._text(screen, f"{zone:,}–{zone + 10:,} 秒", 250, y, 212)
            self._text(screen, f"{count:,} / {total:,}", 480, y, 222, right=True)
            pygame.draw.rect(screen, ACCENT_CORAL, (250, y + 31, round(452 * count / total), 4))

    def _draw_death_weapons(self, screen: pygame.Surface) -> None:
        st = self._stats
        total = st.get("deaths_total", 0)
        self._text(screen, "倒れた時の装備", 98, 157, 604, font=self._font_head)
        if not total:
            self._text(screen, "装備が記録されたデータはありません", 98, 260, 604)
            return
        self._text(screen, f"装備の記録 {total:,} 件の平均値", 98, 193, 604,
                   font=self._font_hint, color=TEXT_MUTED)
        averages = st.get("death_field_avg", {})
        rows = (("メイン射撃", "main_level"), ("移動速度", "speed_level"),
                ("レーザー", "laser_level"), ("追尾弾", "homing_level"),
                ("磁力", "magnet_level"), ("バリア所持率", "has_barrier"))
        for i, (label, field) in enumerate(rows):
            value = averages.get(field)
            if value is None:
                formatted = "—"
            elif field == "has_barrier":
                formatted = f"{value * 100:.0f}%"
            else:
                formatted = f"{value:.2f} 段階"
            y = 234 + i * 35
            self._text(screen, label, 98, y, 280, color=TEXT_MUTED)
            self._text(screen, formatted, 400, y, 302, right=True)
        low = st.get("low_main", 0)
        self._text(screen, f"メイン未強化で倒れた回数  {low:,} / {total:,}", 98, 470, 604,
                   font=self._font_hint, color=ACCENT_CORAL if low / total >= 0.5 else TEXT_MUTED)
