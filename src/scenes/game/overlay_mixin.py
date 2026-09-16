"""ステージバナー・ボス演出 オーバーレイ ミックスイン。"""
from __future__ import annotations
import pygame

from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.scenes.game.config import (
    STAGE_NAMES, STAGE_BANNER_DURATION,
    BOSS_DIALOGUE_DURATION, BOSS_NAME_DURATION,
    ALERT_DURATION, FIGHT_BANNER_DURATION,
)
from src.scenes.dialogue_panel import (
    COMBAT_BLUE_STYLE,
    COMBAT_PURPLE_STYLE,
    COMBAT_RED_STYLE,
    draw_combat_panel,
)
from src.story.speakers import speaker_name, speaker_color


class GameSceneOverlayMixin:
    """ステージ名バナー・ボス演出オーバーレイの描画を担当する。"""

    # ── ステージ名バナー ──────────────────────────────────────
    def _draw_stage_banner(self, screen: pygame.Surface) -> None:
        if self._stage_banner_font is None:  # type: ignore[attr-defined]
            self._stage_banner_font     = self.game.resources.pixelfont(52)  # type: ignore[attr-defined]
            self._stage_banner_sub_font = self.game.resources.pixelfont(20)  # type: ignore[attr-defined]

        t = self._stage_banner_timer / STAGE_BANNER_DURATION  # type: ignore[attr-defined]
        alpha = 220 if t > 0.2 else int(220 * (t / 0.2))

        sid = self._stage_id  # type: ignore[attr-defined]
        if sid not in STAGE_NAMES:
            return
        ch_label, stage_name, monologue = STAGE_NAMES[sid]

        overlay = pygame.Surface((SCREEN_WIDTH, 130), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, min(180, alpha)))
        screen.blit(overlay, (0, SCREEN_HEIGHT // 2 - 65))

        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2

        chapter = self._stage_banner_font.render(f"{ch_label}：{stage_name}", True, (255, 220, 80))  # type: ignore[attr-defined]
        chapter.set_alpha(alpha)
        screen.blit(chapter, (cx - chapter.get_width() // 2, cy - 52))


    # ── ALERT（ボス出現予告）────────────────────────────────────
    def _draw_alert(self, screen: pygame.Surface) -> None:
        if not hasattr(self, "_alert_font") or self._alert_font is None:  # type: ignore[attr-defined]
            self._alert_font = self.game.resources.pixelfont(72)  # type: ignore[attr-defined]

        t = self._boss_intro_timer / ALERT_DURATION  # type: ignore[attr-defined]
        # 点滅: 0.15秒周期
        blink = int(self._boss_intro_timer * 6.5) % 2 == 0  # type: ignore[attr-defined]
        bg_alpha = int(160 * (0.5 + 0.5 * (1 - t)))  # 徐々に暗く

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((120, 0, 0, bg_alpha))
        screen.blit(overlay, (0, 0))

        if blink:
            cx = SCREEN_WIDTH  // 2
            cy = SCREEN_HEIGHT // 2
            text = self._alert_font.render("！！ALERT！！", True, (255, 60, 60))  # type: ignore[attr-defined]
            text.set_alpha(230)
            screen.blit(text, (cx - text.get_width() // 2, cy - text.get_height() // 2))

    # ── ボス名バナー（入場完了後）──────────────────────────────
    def _draw_boss_name(self, screen: pygame.Surface) -> None:
        if not hasattr(self, "_boss_name_font") or self._boss_name_font is None:  # type: ignore[attr-defined]
            self._boss_name_font  = self.game.resources.pixelfont(30)  # type: ignore[attr-defined]
            self._boss_name_label_font = self.game.resources.pixelfont(18)  # type: ignore[attr-defined]

        t = self._boss_intro_timer / BOSS_NAME_DURATION  # type: ignore[attr-defined]
        alpha = 255 if t > 0.2 else int(255 * (t / 0.2))

        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2

        label = self._boss_name_label_font.render("── BOSS ──", True, (180, 100, 100))  # type: ignore[attr-defined]
        label.set_alpha(alpha)
        screen.blit(label, (cx - label.get_width() // 2, cy - 30))

        name = self._boss_name_font.render(self._boss_name_text, True, (255, 80, 80))  # type: ignore[attr-defined]
        name.set_alpha(alpha)
        screen.blit(name, (cx - name.get_width() // 2, cy + 2))

    # ── ボス登場時セリフ（決定アクションで送る）──────────────
    def _draw_boss_intro_dialogue(self, screen: pygame.Surface) -> None:
        if not hasattr(self, "_intro_dialogue_font") or self._intro_dialogue_font is None:  # type: ignore[attr-defined]
            self._intro_dialogue_font = self.game.resources.pixelfont(26)  # type: ignore[attr-defined]

        pages = self._boss_intro_pages   # type: ignore[attr-defined]   # list[Line]
        idx   = self._boss_intro_page_idx  # type: ignore[attr-defined]
        if not pages:
            return
        line  = pages[idx]
        accept = self.game.settings.key_display("ui_accept")  # type: ignore[attr-defined]

        hint = f"{accept}: 次へ"
        draw_combat_panel(
            screen,
            self.game.resources,  # type: ignore[attr-defined]
            line.speaker,
            line.lines,
            hint_text=hint,
            style=COMBAT_RED_STYLE,
        )

    # ── FIGHT! バナー ──────────────────────────────────────────
    def _draw_fight_banner(self, screen: pygame.Surface) -> None:
        if not hasattr(self, "_fight_font") or self._fight_font is None:  # type: ignore[attr-defined]
            self._fight_font = self.game.resources.pixelfont(88)  # type: ignore[attr-defined]

        t = self._boss_intro_timer / FIGHT_BANNER_DURATION  # type: ignore[attr-defined]
        alpha = int(255 * min(1.0, t * 4)) if t > 0.75 else 255  # フェードアウト
        alpha = int(255 * t / 0.25) if t < 0.25 else alpha       # フェードイン

        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2

        text = self._fight_font.render("FIGHT!", True, (255, 220, 60))  # type: ignore[attr-defined]
        text.set_alpha(alpha)
        screen.blit(text, (cx - text.get_width() // 2, cy - text.get_height() // 2))

    # ── 戦闘中セリフ（自動タイムアウト）───────────────────────
    def _draw_boss_dialogue(self, screen: pygame.Surface) -> None:
        if self._boss_dialogue_font is None:  # type: ignore[attr-defined]
            self._boss_dialogue_font = self.game.resources.pixelfont(16)  # type: ignore[attr-defined]

        line_dur = getattr(self, "_boss_dialogue_line_dur", BOSS_DIALOGUE_DURATION)
        t = self._boss_dialogue_timer / max(0.001, line_dur)  # type: ignore[attr-defined]
        alpha = max(0, min(240, int(240 * t / 0.15)))
        speaker = getattr(self, "_boss_dialogue_speaker", "")
        text = " ".join(self._boss_dialogue_lines)  # type: ignore[attr-defined]
        if not text:
            return
        box_w = screen.get_width() - 32
        text_w = box_w - 24
        font = self._boss_dialogue_font

        def wrap(body, selected_font):
            rows, row = [], ""
            for char in body:
                if row and selected_font.size(row + char)[0] > text_w:
                    rows.append(row)
                    row = ""
                row += char
            if row:
                rows.append(row)
            return rows

        rows = wrap(text, font)
        if len(rows) > 2:
            font = self.game.resources.pixelfont(14)  # type: ignore[attr-defined]
            rows = wrap(text, font)
        name_font = self.game.resources.pixelfont(14)  # type: ignore[attr-defined]
        name = speaker_name(speaker)
        name_h = name_font.get_linesize() if name else 0
        row_h = font.get_linesize()
        box_h = 12 + name_h + row_h * len(rows)
        # Timed barks stay above the boss gauge and leave the central fight visible.
        box_y = screen.get_height() - 58 - box_h
        panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        panel.fill((10, 12, 24, min(150, alpha)))
        color = speaker_color(speaker)
        pygame.draw.line(panel, (*color, alpha), (0, 0), (box_w - 1, 0), 2)
        y = 5
        if name:
            label = name_font.render(name, True, color)
            label.set_alpha(alpha)
            panel.blit(label, (12, y))
            y += name_h
        for row in rows:
            label = font.render(row, True, (255, 240, 230))
            label.set_alpha(alpha)
            panel.blit(label, (12, y))
            y += row_h
        screen.blit(panel, (16, box_y))

    # ── 戦闘中カットイン（戦闘停止・決定アクションで送る）─────
    def _draw_combat_cutin(self, screen: pygame.Surface) -> None:
        pages = self._cutin_pages   # type: ignore[attr-defined]   # list[Line]
        idx   = self._cutin_idx     # type: ignore[attr-defined]
        if not pages or idx >= len(pages):
            return
        line  = pages[idx]
        accept = self.game.settings.key_display("ui_accept")  # type: ignore[attr-defined]
        hint = f"{accept}: 次へ"
        draw_combat_panel(
            screen,
            self.game.resources,  # type: ignore[attr-defined]
            line.speaker,
            line.lines,
            hint_text=hint,
            style=COMBAT_PURPLE_STYLE,
        )

    # ── ボス撃破後セリフ（決定アクションで送る）──────────────
    def _draw_defeat_dialogue(self, screen: pygame.Surface) -> None:
        if not hasattr(self, "_defeat_dialogue_font") or self._defeat_dialogue_font is None:  # type: ignore[attr-defined]
            self._defeat_dialogue_font = self.game.resources.pixelfont(26)  # type: ignore[attr-defined]

        pages = self._defeat_dialogue_pages   # type: ignore[attr-defined]   # list[Line]
        idx   = self._defeat_dialogue_index   # type: ignore[attr-defined]
        if not pages or idx >= len(pages):
            return
        line  = pages[idx]
        accept = self.game.settings.key_display("ui_accept")  # type: ignore[attr-defined]

        hint = f"{accept}: 次へ"
        draw_combat_panel(
            screen,
            self.game.resources,  # type: ignore[attr-defined]
            line.speaker,
            line.lines,
            hint_text=hint,
            style=COMBAT_BLUE_STYLE,
        )
