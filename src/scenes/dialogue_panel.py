"""会話ウィンドウ描画（V2: 角ばり太枠・モノクロ名前・ピクセル基調）。

- 半透明ウィンドウ＋角ばったピクセル太枠
- 名前枠はメッセージ枠の左端にぴったり／名前は縦中央／下辺=本体上辺で連結／色一致
- 名前は白（視認性優先。話者色はアイコン枠と上辺アクセントに使用）
- 進捗ドット無し・右下に ▼ 送り誘導マーク（点滅）
- 戦闘=顔アイコン。ストーリー=立ち絵を左右に表示（顔素材流用可）、非発言側はトーンダウン
- 本文は上詰めが基本（center=True で中央寄せ＝強調）
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

import pygame

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from src.story.speakers import (
    DEFAULT_TEXT_COLOR,
    speaker_color,
    speaker_name,
    speaker_portrait,
    speaker_tachie,
)

NAME_TEXT = (238, 238, 246)   # 名前は白系（V2）
_BORDER_W = 3
_RADIUS = 0                    # 角ばり（レトロ）


@dataclass(frozen=True)
class DialoguePanelStyle:
    fill: tuple[int, int, int, int]
    border: tuple[int, int, int, int]
    hint: tuple[int, int, int]
    text: tuple[int, int, int] = DEFAULT_TEXT_COLOR
    light: bool = False


DARK_STYLE = DialoguePanelStyle(fill=(12, 14, 26, 198), border=(120, 150, 200, 230), hint=(150, 170, 205))
LIGHT_STYLE = DialoguePanelStyle(fill=(250, 242, 214, 214), border=(150, 120, 86, 230),
                                 hint=(120, 96, 72), text=(54, 42, 32), light=True)
COMBAT_RED_STYLE = DialoguePanelStyle(fill=(24, 8, 16, 200), border=(198, 92, 92, 230), hint=(170, 130, 150))
COMBAT_BLUE_STYLE = DialoguePanelStyle(fill=(8, 14, 28, 200), border=(86, 140, 196, 230),
                                       hint=(130, 166, 198), text=(214, 234, 255))
COMBAT_PURPLE_STYLE = DialoguePanelStyle(fill=(16, 8, 28, 202), border=(176, 86, 176, 230),
                                         hint=(186, 140, 196), text=(255, 236, 246))


def story_sides(active, partner):
    """会話の2人を左右に割り当てる。味方=左 / 敵=右、味方同士は主人公(澤口)=左 / 先輩=右。"""
    from src.story.speakers import SAWAGUCHI, is_ally, is_character
    people = [p for p in (active, partner) if p and is_character(p)]
    if not people:
        return (None, None)
    if len(people) == 1:
        k = people[0]
        return (k, None) if is_ally(k) else (None, k)
    a, b = people[0], people[1]
    if is_ally(a) and is_ally(b):
        left = SAWAGUCHI if SAWAGUCHI in (a, b) else a
        right = b if left == a else a
        return (left, right)
    if is_ally(a):          # a=味方, b=敵
        return (a, b)
    if is_ally(b):          # a=敵, b=味方
        return (b, a)
    return (a, b)           # 敵同士（稀）


def _sa(color, alpha):
    return (*color[:3], min(color[3], alpha))


def _fit_font(resources, lines, max_width, base_size, min_size):
    # 文字サイズは固定（自動縮小はしない＝サイズが暴れる違和感を避ける）。
    # 長い行は台本側で1行を短く保つ（収まらなければ Line/page の行を分ける）。
    return resources.pixelfont(base_size)


def _visible_lines(lines, chars):
    if chars is None:
        return tuple(lines)
    out, remaining = [], chars
    for line in lines:
        if remaining <= 0:
            break
        v = line[:remaining]
        remaining -= len(line)
        if v:
            out.append(v)
    return tuple(out)


def _wrap_line(font, text, max_w):
    """1 論理行を max_w 以内の副行へ折り返す（日本語＝文字単位で折る）。"""
    if not text or font.size(text)[0] <= max_w:
        return [text]
    out, cur = [], ""
    for ch in text:
        if cur and font.size(cur + ch)[0] > max_w:
            out.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def _arrow_visible(arrow_on):
    if arrow_on is not None:
        return arrow_on
    return (pygame.time.get_ticks() // 480) % 2 == 0


def _draw_window(screen, rect, style, alpha):
    win = pygame.Surface(rect.size, pygame.SRCALPHA)
    win.fill(_sa(style.fill, alpha))
    pygame.draw.rect(win, _sa(style.border, alpha), win.get_rect(), _BORDER_W, border_radius=_RADIUS)
    screen.blit(win, rect.topleft)


def _draw_name_tab(screen, resources, rect, speaker, style, alpha):
    name = speaker_name(speaker)
    if not name:
        return
    nf = resources.pixelfont(19)
    label = nf.render(name, True, NAME_TEXT)
    label.set_alpha(alpha)
    pad, tab_h = 14, 30
    tab = pygame.Rect(rect.x, rect.y - tab_h, label.get_width() + pad * 2, tab_h)
    ts = pygame.Surface(tab.size, pygame.SRCALPHA)
    ts.fill(_sa(style.fill, alpha))
    pygame.draw.rect(ts, _sa(style.border, alpha), ts.get_rect(), _BORDER_W, border_radius=_RADIUS)
    # 下辺の枠線を消して本体と連結
    pygame.draw.rect(ts, _sa(style.fill, alpha), (_BORDER_W, tab_h - _BORDER_W, tab.w - _BORDER_W * 2, _BORDER_W + 2))
    screen.blit(ts, tab.topleft)
    # 話者色アクセント（名前枠の上辺）
    pygame.draw.line(screen, (*speaker_color(speaker), min(220, alpha)),
                     (tab.x + 4, tab.y + 3), (tab.right - 4, tab.y + 3), 2)
    screen.blit(label, (tab.x + pad, tab.y + (tab_h - label.get_height()) // 2))


def _draw_text(screen, resources, rect, lines, style, *, chars, center, valign,
               body_size, min_body_size, text_x, text_w, alpha,
               text_transform, text_color, text_jitter):
    visible = _visible_lines(lines, chars)
    body = _fit_font(resources, visible or lines, text_w, body_size, min_body_size)
    line_h = body.get_height() + 5
    total_h = len(lines) * line_h
    pad_top = 18
    content_top = rect.y + pad_top
    content_h = rect.h - pad_top - 14
    start_y = content_top + max(0, (content_h - total_h) // 2) if valign == "center" else content_top
    for i, ln in enumerate(visible):
        draw = text_transform(ln) if text_transform else ln
        surf = body.render(draw, True, text_color or style.text)
        surf.set_alpha(alpha)
        if center:
            x = rect.centerx - surf.get_width() // 2
        else:
            j = random.randint(-text_jitter, text_jitter) if text_jitter > 0 else 0
            x = text_x + j
        screen.blit(surf, (x, start_y + i * line_h))


def _draw_arrow(screen, rect, alpha, arrow_on, complete):
    if not (complete and _arrow_visible(arrow_on)):
        return
    ax, ay = rect.right - 26, rect.bottom - 24
    tri = pygame.Surface((22, 15), pygame.SRCALPHA)
    pygame.draw.polygon(tri, (236, 236, 246, alpha), [(2, 2), (20, 2), (11, 13)])
    screen.blit(tri, (ax - 11, ay))


# ── 戦闘パネル（顔アイコン・省スペース） ──────────────────────────────

# 本文は 22pt（従来 26pt より一段小）。最長行 616px でも折返さず 1 行に収まり
# （全行 ≤ 使用可能幅 624px を実測確認）、セリフは最大 2 行。パネルは最初から
# 2 行ぶんの固定サイズにして自動拡張しない（サイズが暴れる違和感を避ける）。
_COMBAT_BODY_SIZE = 22
_COMBAT_PORTRAIT_SIZE = 68        # 顔アイコンは固定
COMBAT_PANEL_RECT = pygame.Rect(26, SCREEN_HEIGHT - 144, SCREEN_WIDTH - 52, 108)


def draw_combat_panel(screen, resources, speaker, lines, *, page_index=None,
                      total_pages=None, hint_text=None, style=COMBAT_RED_STYLE,
                      alpha=255, center=False, arrow_on=None, chars=None,
                      complete=None, text_transform=None, text_jitter=0,
                      show_portrait=True):
    rect = COMBAT_PANEL_RECT
    body = resources.pixelfont(_COMBAT_BODY_SIZE)
    # 本文の左端と使える横幅（顔アイコンぶんを差し引く）を先に確定する。
    text_x, text_w = rect.x + 22, rect.w - 44
    portrait = speaker_portrait(speaker) if show_portrait else None
    if portrait:
        text_x = rect.x + 14 + _COMBAT_PORTRAIT_SIZE + 20
        text_w = rect.right - 22 - text_x
    # 想定外に長い行だけ横幅で折り返す安全網（通常は 1 行に収まる）。
    wrapped: list[str] = []
    for ln in lines:
        wrapped.extend(_wrap_line(body, ln, text_w))
    wrapped = wrapped or [""]

    _draw_window(screen, rect, style, alpha)
    if portrait:
        size = _COMBAT_PORTRAIT_SIZE
        img = pygame.transform.smoothscale(resources.image(portrait), (size, size)).convert_alpha()
        img.set_alpha(alpha)
        px, py = rect.x + 14, rect.y + (rect.h - size) // 2
        pygame.draw.rect(screen, (6, 8, 16), (px - 3, py - 3, size + 6, size + 6))
        screen.blit(img, (px, py))
        pygame.draw.rect(screen, (*speaker_color(speaker), min(235, alpha)),
                         (px - 3, py - 3, size + 6, size + 6), 2)
    _draw_name_tab(screen, resources, rect, speaker, style, alpha)
    _draw_text(screen, resources, rect, wrapped, style, chars=chars, center=center,
               valign="center", body_size=_COMBAT_BODY_SIZE, min_body_size=_COMBAT_BODY_SIZE,
               text_x=text_x, text_w=text_w, alpha=alpha, text_transform=text_transform,
               text_color=None, text_jitter=text_jitter)
    if complete is None:
        complete = hint_text is not None
    _draw_arrow(screen, rect, alpha, arrow_on, complete=complete)


# ── ストーリーパネル（左右に立ち絵・上詰め） ──────────────────────────

def _tachie_image(resources, speaker, size, *, flip, active):
    path = speaker_tachie(speaker) or speaker_portrait(speaker)  # 立ち絵が無ければ顔素材流用
    if not path:
        return None
    img = pygame.transform.smoothscale(resources.image(path), (size, size)).convert_alpha()
    if flip:
        img = pygame.transform.flip(img, True, False)
    if not active:
        # 非発言側は「薄く」ではなく「暗く」（不透明のまま陰に落とす）
        shade = pygame.Surface((size, size), pygame.SRCALPHA)
        shade.fill((92, 94, 112))
        img.blit(shade, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    return img


def draw_story_panel(screen, resources, speaker, lines, *, chars=None, page_index=0,
                     total_pages=1, complete=True, blink=0.0, hint_last="", hint_next="",
                     style=DARK_STYLE, show_portrait=True, text_transform=None,
                     text_color=None, text_jitter=0, center=False, arrow_on=None,
                     left_speaker=None, right_speaker=None):
    rect = pygame.Rect(40, SCREEN_HEIGHT - 210, SCREEN_WIDTH - 80, 176)

    # 立ち絵（ウィンドウより先に描いて、ウィンドウ下部が重なる＝奥行き感）
    if show_portrait:
        size = 300                       # 少し小さく
        base_y = rect.y - size + 108
        if left_speaker is None and right_speaker is None:
            left_speaker, right_speaker = story_sides(speaker, None)
        if left_speaker:
            img = _tachie_image(resources, left_speaker, size, flip=False, active=(left_speaker == speaker))
            if img:
                screen.blit(img, (rect.x, base_y))                 # 画面端から余白＝中央寄り
        if right_speaker:
            img = _tachie_image(resources, right_speaker, size, flip=False, active=(right_speaker == speaker))
            if img:
                screen.blit(img, (rect.right - size, base_y))

    _draw_window(screen, rect, style, 255)
    _draw_name_tab(screen, resources, rect, speaker, style, 255)
    _draw_text(screen, resources, rect, lines, style, chars=chars, center=center,
               valign="center" if center else "top", body_size=27, min_body_size=21,
               text_x=rect.x + 26, text_w=rect.w - 52, alpha=255,
               text_transform=text_transform, text_color=text_color, text_jitter=text_jitter)
    _draw_arrow(screen, rect, 255, arrow_on, complete=complete)
