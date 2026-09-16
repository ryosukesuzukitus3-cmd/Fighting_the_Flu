"""台詞を省略せず、本文・話者・操作欄を分けて表示する会話パネル。

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


DARK_STYLE = DialoguePanelStyle(fill=(12, 20, 37, 244), border=(110, 151, 198, 235), hint=(191, 207, 230))
LIGHT_STYLE = DialoguePanelStyle(fill=(250, 242, 214, 214), border=(150, 120, 86, 230),
                                 hint=(120, 96, 72), text=(54, 42, 32), light=True)
COMBAT_RED_STYLE = DialoguePanelStyle(fill=DARK_STYLE.fill, border=(202, 125, 135, 235), hint=DARK_STYLE.hint)
COMBAT_BLUE_STYLE = DialoguePanelStyle(fill=DARK_STYLE.fill, border=(105, 163, 214, 235),
                                       hint=DARK_STYLE.hint, text=(225, 237, 251))
COMBAT_PURPLE_STYLE = DialoguePanelStyle(fill=DARK_STYLE.fill, border=(189, 134, 204, 235),
                                         hint=DARK_STYLE.hint, text=(245, 232, 249))

_TEXT_TOP = 18
_TEXT_BOTTOM = 14
_FOOTER_SPACE = 48


def _line_height(font):
    return font.get_height() + 2


def _panel_for_text(base_rect, font, lines, footer_height=0):
    """Keep the lower edge stable and reserve separate space for instructions."""
    text_height = len(lines) * _line_height(font) - 2
    height = max(base_rect.h, _TEXT_TOP + text_height + max(footer_height, _TEXT_BOTTOM))
    return pygame.Rect(base_rect.x, base_rect.bottom - height, base_rect.w, height)


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
    # Avoid an orphaned Japanese particle/punctuation fragment on its own line.
    # When a line only barely exceeds the panel width, a balanced two-line break
    # reads much better than leaving e.g. ``よ。`` at the start of line two.
    if len(out) == 2 and len(out[-1]) <= 3 and len(text) >= 8:
        split = len(text) // 2
        while split < len(text) and text[split] in "。、！？!?）】」』":
            split += 1
        balanced = [text[:split], text[split:]]
        if all(font.size(part)[0] <= max_w for part in balanced):
            out = balanced
    return out


def _wrap_lines(font, lines, max_w):
    """論理行を表示行へ折り返す。文字は削除・追加しない。"""
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(_wrap_line(font, line, max_w))
    return wrapped or [""]


def _footer_text(page_index, total_pages, hint_text):
    """ページ表記と操作ヒントを分離し、旧呼び出しの重複表記を除く。"""
    page = ""
    if page_index is not None and total_pages is not None and total_pages > 0:
        page = f"{page_index + 1}/{total_pages}"

    hint = (hint_text or "").strip()
    if page and hint.startswith(page):
        hint = hint[len(page):].lstrip(" 　:：")
    return page, hint


def _footer_layout(resources, rect, page_index, total_pages, hint_text, text_x, font_size):
    page, hint = _footer_text(page_index, total_pages, hint_text)
    if not page and not hint:
        return page, [], 0
    font = resources.pixelfont(font_size)
    page_width = font.size(page)[0] + 22 if page else 0
    width = rect.right - 46 - text_x - page_width
    lines = _wrap_lines(font, (hint,), width) if hint else []
    return page, lines, max(_FOOTER_SPACE, len(lines) * font.get_height() + 16)


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
    nf = resources.pixelfont(20)
    label = nf.render(name, True, style.text if style.light else NAME_TEXT)
    label.set_alpha(alpha)
    pad, tab_h = 14, 38
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


def _text_rect(rect, text_x, text_w, reserved_bottom=0):
    return pygame.Rect(text_x, rect.y + _TEXT_TOP, text_w,
                       rect.h - _TEXT_TOP - _TEXT_BOTTOM - reserved_bottom)


def _draw_text(screen, resources, rect, lines, style, *, chars, center, valign,
               body_size, text_x, text_w, alpha,
               text_transform, text_color, text_jitter, reserved_bottom=0):
    visible = _visible_lines(lines, chars)
    body = resources.pixelfont(body_size)
    line_h = _line_height(body)
    total_h = len(lines) * line_h - 2
    content = _text_rect(rect, text_x, text_w, reserved_bottom)
    start_y = content.y + max(0, (content.h - total_h) // 2) if valign == "center" else content.y
    for i, ln in enumerate(visible):
        draw = text_transform(ln) if text_transform else ln
        surf = body.render(draw, True, text_color or style.text)
        surf.set_alpha(alpha)
        if center:
            x = text_x + (text_w - surf.get_width()) // 2
        else:
            j = random.randint(-text_jitter, text_jitter) if text_jitter > 0 else 0
            x = text_x + j
        screen.blit(surf, (x, start_y + i * line_h))


def _draw_footer(screen, resources, rect, style, *, page_index, total_pages,
                 hint_text, alpha, text_x, font_size):
    page, hints, height = _footer_layout(resources, rect, page_index, total_pages,
                                       hint_text, text_x, font_size)
    if not height:
        return

    font = resources.pixelfont(font_size)
    y = rect.bottom - max(1, len(hints)) * font.get_height() - 8
    pygame.draw.line(screen, style.border[:3], (text_x, rect.bottom - height + 5),
                     (rect.right - 22, rect.bottom - height + 5), 1)
    if page:
        surf = font.render(page, True, style.hint)
        surf.set_alpha(alpha)
        screen.blit(surf, (text_x, y))
    for index, hint in enumerate(hints):
        surf = font.render(hint, True, style.hint)
        surf.set_alpha(alpha)
        # 右下の送りマークと干渉させない。
        right = rect.right - 46
        screen.blit(surf, (right - surf.get_width(), y + index * font.get_height()))


def _draw_arrow(screen, rect, alpha, arrow_on, complete):
    if not (complete and _arrow_visible(arrow_on)):
        return
    ax, ay = rect.right - 26, rect.bottom - 24
    tri = pygame.Surface((22, 15), pygame.SRCALPHA)
    pygame.draw.polygon(tri, (236, 236, 246, alpha), [(2, 2), (20, 2), (11, 13)])
    screen.blit(tri, (ax - 11, ay))


# ── 戦闘パネル（顔アイコン・省スペース） ──────────────────────────────

# 通常の短い台詞は省スペースに保ち、折返しや操作欄があるときだけ上へ広げる。
_COMBAT_BODY_SIZE = 22
_COMBAT_PORTRAIT_SIZE = 68        # 顔アイコンは固定
# 下端はボスHPバー（y=564〜）直上の体幹ゲージ（y=555〜561）に掛からない位置に置く
# （実機FB: 旧 y=456..564 は体幹ゲージを完全に隠していた）。
COMBAT_PANEL_RECT = pygame.Rect(26, SCREEN_HEIGHT - 164, SCREEN_WIDTH - 52, 108)


def draw_combat_panel(screen, resources, speaker, lines, *, page_index=None,
                      total_pages=None, hint_text=None, style=COMBAT_RED_STYLE,
                      alpha=255, center=False, arrow_on=None, chars=None,
                      complete=None, text_transform=None, text_jitter=0,
                      show_portrait=True) -> pygame.Rect:
    """Draw the panel and return the body area, excluding its name/portrait/footer."""
    rect = COMBAT_PANEL_RECT
    body = resources.pixelfont(_COMBAT_BODY_SIZE)
    # 本文の左端と使える横幅（顔アイコンぶんを差し引く）を先に確定する。
    text_x, text_w = rect.x + 22, rect.w - 44
    portrait = speaker_portrait(speaker) if show_portrait else None
    if portrait:
        text_x = rect.x + 14 + _COMBAT_PORTRAIT_SIZE + 20
        text_w = rect.right - 22 - text_x
    # 想定外に長い行だけ横幅で折り返す安全網（通常は 1 行に収まる）。
    wrapped = _wrap_lines(body, lines, text_w)
    _, _, footer_height = _footer_layout(resources, rect, page_index, total_pages,
                                         hint_text, text_x, 16)
    rect = _panel_for_text(rect, body, wrapped, footer_height)

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
               valign="center", body_size=_COMBAT_BODY_SIZE,
               text_x=text_x, text_w=text_w, alpha=alpha, text_transform=text_transform,
               text_color=None, text_jitter=text_jitter,
               reserved_bottom=max(0, footer_height - _TEXT_BOTTOM))
    _draw_footer(screen, resources, rect, style, page_index=page_index,
                 total_pages=total_pages, hint_text=hint_text, alpha=alpha,
                 text_x=text_x, font_size=16)
    if complete is None:
        complete = hint_text is not None
    _draw_arrow(screen, rect, alpha, arrow_on, complete=complete)
    return _text_rect(rect, text_x, text_w, max(0, footer_height - _TEXT_BOTTOM))


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
    body = resources.pixelfont(26)
    text_w = SCREEN_WIDTH - 132
    wrapped = _wrap_lines(body, lines, text_w)
    hint = hint_next if page_index < total_pages - 1 else hint_last
    base_rect = pygame.Rect(40, SCREEN_HEIGHT - 218, SCREEN_WIDTH - 80, 184)
    _, _, footer_height = _footer_layout(resources, base_rect, page_index, total_pages,
                                         hint, base_rect.x + 26, 18)
    rect = _panel_for_text(base_rect, body, wrapped, footer_height)

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
    text_x = rect.x + 26
    text_w = rect.w - 52
    # 折返し位置・枠の高さは全文から決め、文字送り中にレイアウトを動かさない。
    _draw_text(screen, resources, rect, wrapped, style, chars=chars, center=center,
               valign="center" if center else "top", body_size=26,
               text_x=text_x, text_w=text_w, alpha=255,
               text_transform=text_transform, text_color=text_color, text_jitter=text_jitter,
               reserved_bottom=max(0, footer_height - _TEXT_BOTTOM))
    _draw_footer(screen, resources, rect, style, page_index=page_index,
                 total_pages=total_pages, hint_text=hint, alpha=255,
                 text_x=text_x, font_size=18)
    _draw_arrow(screen, rect, 255, arrow_on, complete=complete)
