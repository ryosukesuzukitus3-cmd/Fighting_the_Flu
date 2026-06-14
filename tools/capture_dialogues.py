"""話者×会話シーンの代表コマをヘッドレスで撮る監査ツール。

dialogue_panel.draw_story_panel / draw_combat_panel を直接呼び、全話者・全スタイル
（story-dark / story-light / combat-red / combat-blue / combat-purple）を網羅した
代表パターンを captures/dialogue_audit/ に出力する。レビュー用。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYTHONUTF8", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT  # noqa: E402
from src.core.game import Game  # noqa: E402
from src.entities.background import ScrollingBackground  # noqa: E402
from src.scenes.dialogue_panel import (  # noqa: E402
    DARK_STYLE, LIGHT_STYLE, COMBAT_RED_STYLE, COMBAT_BLUE_STYLE, COMBAT_PURPLE_STYLE,
    draw_story_panel, draw_combat_panel,
)
import src.story.speakers as spk  # noqa: E402

OUT = ROOT / "captures" / "dialogue_audit"


def _story(screen, res, speaker, line, style, *, center=False):
    lines = line if isinstance(line, tuple) else (line,)
    draw_story_panel(
        screen, res, speaker, lines,
        chars=None, page_index=0, total_pages=1, complete=True, blink=0.0,
        hint_last="ENTER: 続ける", hint_next="ENTER: 次へ", style=style,
        center=center, arrow_on=True,
    )


def _combat(screen, res, speaker, line, style, *, page_index=None, total_pages=None,
            hint=None, center=False):
    lines = line if isinstance(line, tuple) else (line,)
    draw_combat_panel(
        screen, res, speaker, lines,
        page_index=page_index, total_pages=total_pages, hint_text=hint, style=style,
        center=center, arrow_on=True,
    )


def main() -> int:
    pygame.init()
    pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    game = Game()
    res = game.resources

    # 背景: 戦闘パネル用に実ステージ背景、ストーリー用に単色
    combat_bg = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    ScrollingBackground(1).draw(combat_bg, 0.0)
    dark_bg = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)); dark_bg.fill((8, 8, 20))
    light_bg = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)); light_bg.fill((252, 245, 220))

    # (ファイル名, 種別, 話者, セリフ, スタイル, 背景, combat引数)
    combos = [
        # ── 全画面カットシーン（story） ──
        ("01_story_narration",   "story", spk.NARRATION,    "熱が、部屋ごと薄ぼんやりさせていく。",        DARK_STYLE,  dark_bg),
        ("02_story_sawaguchi",   "story", spk.SAWAGUCHI,    "……まだ、立てる。まだ戦える。",               DARK_STYLE,  dark_bg),
        ("03_story_karonaru",    "story", spk.KARONARU,     "澤口くん、無理は禁物だよ。",                  DARK_STYLE,  dark_bg),
        ("04_story_karonaru_max","story", spk.KARONARU_MAX, "薬効、最大。ここからは私が前へ出る。",        DARK_STYLE,  dark_bg),
        ("05_story_unknown",     "story", spk.UNKNOWN,      "……誰だ。そこにいるのは。",                    DARK_STYLE,  dark_bg),
        ("06_story_system",      "story", spk.SYSTEM,       "SAVE COMPLETE.",                              DARK_STYLE,  dark_bg),
        ("07_story_sawaguchi_light","story", spk.SAWAGUCHI, "朝だった。熱は、いつのまにか引いていた。",    LIGHT_STYLE, light_bg),
        # ── 戦闘中（combat） ──
        ("08_combat_boss1_red",  "combat", spk.BOSS1,         "クシャミひとつで貴様を吹き飛ばす！",        COMBAT_RED_STYLE,  combat_bg, dict(page_index=0, total_pages=3, hint="1/3  ENTER: 次へ")),
        ("09_combat_boss2_red",  "combat", spk.BOSS2,         "情報の濁流に飲まれて消えろ！",              COMBAT_RED_STYLE,  combat_bg, dict(page_index=0, total_pages=3, hint="1/3  ENTER: 次へ")),
        ("10_combat_boss3_red",  "combat", spk.BOSS3,         "条件に一致する相手は……いません。",          COMBAT_RED_STYLE,  combat_bg, dict(page_index=0, total_pages=3, hint="1/3  ENTER: 次へ")),
        ("11_combat_boss4_red",  "combat", spk.BOSS4,         "盤上に、逃げ場はない。",                    COMBAT_RED_STYLE,  combat_bg, dict(page_index=0, total_pages=3, hint="1/3  ENTER: 次へ")),
        ("12_combat_boss4f2_red","combat", spk.BOSS4_FORM2,   "……まだだ。まだ詰んでいない。",              COMBAT_RED_STYLE,  combat_bg, dict(page_index=0, total_pages=3, hint="1/3  ENTER: 次へ")),
        ("13_combat_sawaguchi_red","combat", spk.BOSS_SAWAGUCHI,"投了は、しない。",                        COMBAT_RED_STYLE,  combat_bg, dict(page_index=0, total_pages=3, hint="1/3  ENTER: 戦闘開始")),
        ("14_combat_boss2_purple","combat", spk.BOSS2,         "まだ笑える余裕があるのか？",                COMBAT_PURPLE_STYLE, combat_bg, dict()),
        ("15_combat_sawaguchi_blue","combat", spk.SAWAGUCHI,   "……効いてる。この調子だ。",                  COMBAT_BLUE_STYLE, combat_bg, dict(page_index=0, total_pages=2, hint="1/2  ENTER: 次へ")),
        ("16_combat_karonaru_blue","combat", spk.KARONARU,     "よくやったね、澤口くん。",                  COMBAT_BLUE_STYLE, combat_bg, dict(page_index=1, total_pages=2, hint="ENTER: 続ける")),
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    saved = []
    for name, kind, speaker, line, style, bg, *rest in combos:
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        screen.blit(bg, (0, 0))
        if kind == "story":
            _story(screen, res, speaker, line, style)
        else:
            _combat(screen, res, speaker, line, style, **(rest[0] if rest else {}))
        out = OUT / f"{name}.png"
        pygame.image.save(screen, str(out))
        saved.append(out)

    for p in saved:
        print(p)
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
