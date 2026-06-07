"""ステージバナー・ボス演出 オーバーレイ ミックスイン。"""
from __future__ import annotations
import pygame

from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.scenes.game.config import (
    STAGE_NAMES, STAGE_BANNER_DURATION,
    BOSS_DIALOGUE_DURATION, BOSS_NAME_DURATION,
    ALERT_DURATION, FIGHT_BANNER_DURATION,
)
from src.story.speakers import speaker_name, speaker_color, speaker_portrait


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

    # ── 話者ネームプレート（セリフボックス共通）────────────────
    def _draw_speaker_nameplate(self, screen: pygame.Surface, speaker: str,
                                box_x: int, box_y: int, alpha: int = 255) -> None:
        """セリフボックス左上に話者名を表示する（name が空なら何もしない）。"""
        name = speaker_name(speaker)
        if not name:
            return
        if not hasattr(self, "_nameplate_font") or self._nameplate_font is None:  # type: ignore[attr-defined]
            self._nameplate_font = self.game.resources.pixelfont(18)  # type: ignore[attr-defined]
        color = speaker_color(speaker)
        label = self._nameplate_font.render(name, True, color)  # type: ignore[attr-defined]
        pad   = 8
        plate_w = label.get_width() + pad * 2
        plate_h = label.get_height() + 4
        plate_y = box_y - plate_h + 2
        plate = pygame.Surface((plate_w, plate_h), pygame.SRCALPHA)
        plate.fill((10, 0, 30, min(225, alpha)))
        pygame.draw.rect(plate, (*color, min(220, alpha)), (0, 0, plate_w, plate_h), 2, border_radius=4)
        screen.blit(plate, (box_x + 6, plate_y))
        label.set_alpha(alpha)
        screen.blit(label, (box_x + 6 + pad, plate_y + 2))

    # ── 発言者ポートレート（セリフボックス共通）──────────────────
    def _draw_speaker_portrait(self, screen: pygame.Surface, speaker: str,
                               box_x: int, box_y: int, box_h: int, alpha: int = 255) -> int:
        """セリフボックス左にポートレートを描画し、本文の左x座標を返す。
        画像が無い話者は何もせず既定の本文x(box_x+20)を返す。"""
        default_text_x = box_x + 20
        path = speaker_portrait(speaker)
        if not path:
            return default_text_x
        raw  = self.game.resources.image(path)  # type: ignore[attr-defined]
        size = box_h - 8
        img  = pygame.transform.smoothscale(raw, (size, size)).convert_alpha()
        img.set_alpha(alpha)
        px, py = box_x + 6, box_y + 4
        screen.blit(img, (px, py))
        pygame.draw.rect(screen, speaker_color(speaker), (px, py, size, size), 2, border_radius=4)
        return px + size + 12

    # ── ボス登場時セリフ（ENTERで送る）────────────────────────
    def _draw_boss_intro_dialogue(self, screen: pygame.Surface) -> None:
        if not hasattr(self, "_intro_dialogue_font") or self._intro_dialogue_font is None:  # type: ignore[attr-defined]
            self._intro_dialogue_font = self.game.resources.pixelfont(26)  # type: ignore[attr-defined]

        pages = self._boss_intro_pages   # type: ignore[attr-defined]   # list[Line]
        idx   = self._boss_intro_page_idx  # type: ignore[attr-defined]
        if not pages:
            return
        line  = pages[idx]
        total = len(pages)

        box_h = 80
        box_y = SCREEN_HEIGHT - box_h - 20

        overlay = pygame.Surface((SCREEN_WIDTH - 40, box_h), pygame.SRCALPHA)
        overlay.fill((10, 0, 30, 210))
        pygame.draw.rect(overlay, (180, 60, 60, 200),
                         (0, 0, SCREEN_WIDTH - 40, box_h), 2, border_radius=6)
        screen.blit(overlay, (20, box_y))

        self._draw_speaker_nameplate(screen, line.speaker, 20, box_y)
        text_x = self._draw_speaker_portrait(screen, line.speaker, 20, box_y, box_h)

        surf = self._intro_dialogue_font.render(line.text, True, (255, 240, 200))  # type: ignore[attr-defined]
        screen.blit(surf, (text_x, box_y + (box_h - surf.get_height()) // 2))

        # ページ番号 + ENTERヒント
        hint_font = self.game.resources.pixelfont(16)  # type: ignore[attr-defined]
        hint = hint_font.render(f"{idx + 1}/{total}  ENTER: 次へ", True, (140, 120, 160))
        screen.blit(hint, (SCREEN_WIDTH - hint.get_width() - 28, box_y + box_h - hint.get_height() - 4))

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
            self._boss_dialogue_font = self.game.resources.pixelfont(26)  # type: ignore[attr-defined]

        t = self._boss_dialogue_timer / BOSS_DIALOGUE_DURATION  # type: ignore[attr-defined]
        alpha = 240 if t > 0.15 else int(240 * (t / 0.15))

        box_h = 64
        box_y = SCREEN_HEIGHT - box_h - 20
        overlay = pygame.Surface((SCREEN_WIDTH - 40, box_h), pygame.SRCALPHA)
        overlay.fill((10, 0, 30, min(200, alpha)))
        pygame.draw.rect(overlay, (100, 80, 160, min(alpha, 180)),
                         (0, 0, SCREEN_WIDTH - 40, box_h), 2, border_radius=6)
        screen.blit(overlay, (20, box_y))

        speaker = getattr(self, "_boss_dialogue_speaker", "")
        self._draw_speaker_nameplate(screen, speaker, 20, box_y, alpha=alpha)
        text_x = self._draw_speaker_portrait(screen, speaker, 20, box_y, box_h, alpha=alpha)

        text = self._boss_dialogue_font.render(self._boss_dialogue_text, True, (255, 240, 200))  # type: ignore[attr-defined]
        text.set_alpha(alpha)
        screen.blit(text, (text_x, box_y + (box_h - text.get_height()) // 2))

    # ── ボス撃破後セリフ（ENTERで送る）────────────────────────
    def _draw_defeat_dialogue(self, screen: pygame.Surface) -> None:
        if not hasattr(self, "_defeat_dialogue_font") or self._defeat_dialogue_font is None:  # type: ignore[attr-defined]
            self._defeat_dialogue_font = self.game.resources.pixelfont(26)  # type: ignore[attr-defined]

        pages = self._defeat_dialogue_pages   # type: ignore[attr-defined]   # list[Line]
        idx   = self._defeat_dialogue_index   # type: ignore[attr-defined]
        if not pages or idx >= len(pages):
            return
        line  = pages[idx]
        total = len(pages)

        box_h = 80
        box_y = SCREEN_HEIGHT - box_h - 20

        overlay = pygame.Surface((SCREEN_WIDTH - 40, box_h), pygame.SRCALPHA)
        overlay.fill((0, 10, 30, 210))
        pygame.draw.rect(overlay, (60, 120, 180, 200),
                         (0, 0, SCREEN_WIDTH - 40, box_h), 2, border_radius=6)
        screen.blit(overlay, (20, box_y))

        self._draw_speaker_nameplate(screen, line.speaker, 20, box_y)
        text_x = self._draw_speaker_portrait(screen, line.speaker, 20, box_y, box_h)

        surf = self._defeat_dialogue_font.render(line.text, True, (200, 230, 255))  # type: ignore[attr-defined]
        screen.blit(surf, (text_x, box_y + (box_h - surf.get_height()) // 2))

        hint_font = self.game.resources.pixelfont(16)  # type: ignore[attr-defined]
        if idx < total - 1:
            hint = hint_font.render(f"{idx + 1}/{total}  ENTER: 次へ", True, (100, 140, 180))
        else:
            hint = hint_font.render("ENTER: 続ける", True, (100, 180, 140))
        screen.blit(hint, (SCREEN_WIDTH - hint.get_width() - 28, box_y + box_h - hint.get_height() - 4))
