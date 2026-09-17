"""台詞全文と操作案内を、単一の外枠に収める会話パネル。

話者名は枠の内側に置き、ページ数や最後のページを示す情報は受け取らない。
戦闘は顔アイコン、ストーリーは左右の立ち絵で話者を示す。
"""
from __future__ import annotations

import random
from dataclasses import dataclass

import pygame

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from src.core.frame_clock import ticks_ms
from src.scenes.meta_ui import BG, TEXT, TEXT_MUTED
from src.story.speakers import (
    speaker_color,
    speaker_name,
    speaker_portrait,
    speaker_tachie,
)

_BORDER_W = 2
_RADIUS = 0                    # 角ばり（レトロ）


@dataclass(frozen=True)
class DialoguePanelStyle:
    fill: tuple[int, int, int, int]
    border: tuple[int, int, int, int]
    hint: tuple[int, int, int]
    text: tuple[int, int, int] = TEXT


DARK_STYLE = DialoguePanelStyle(fill=(*BG, 255), border=(*TEXT, 255), hint=TEXT_MUTED)
# Existing scene names remain valid; speaker names carry the character colour.
LIGHT_STYLE = DARK_STYLE
COMBAT_RED_STYLE = DARK_STYLE
COMBAT_BLUE_STYLE = DARK_STYLE
COMBAT_PURPLE_STYLE = DARK_STYLE

_TEXT_TOP = 18
_TEXT_BOTTOM = 14
_FOOTER_SPACE = 48


def _line_height(font):
    return font.get_height() + 2


def _panel_for_text(base_rect, font, lines, footer_height=0, name_height=0):
    """Keep the lower edge stable and reserve separate space for instructions."""
    text_height = len(lines) * _line_height(font) - 2
    height = max(base_rect.h, _TEXT_TOP + name_height + text_height + max(footer_height, _TEXT_BOTTOM))
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


def _footer_layout(resources, rect, hint_text, text_x, font_size):
    hint = (hint_text or "").strip()
    if not hint:
        return [], 0
    font = resources.pixelfont(font_size)
    width = rect.right - 46 - text_x
    lines = _wrap_lines(font, (hint,), width)
    return lines, max(_FOOTER_SPACE, len(lines) * font.get_height() + 16)


def _arrow_visible(arrow_on):
    if arrow_on is not None:
        return arrow_on
    return (ticks_ms() // 480) % 2 == 0


def _draw_window(screen, rect, style, alpha):
    win = pygame.Surface(rect.size, pygame.SRCALPHA)
    win.fill(_sa(style.fill, alpha))
    pygame.draw.rect(win, _sa(style.border, alpha), win.get_rect(), _BORDER_W, border_radius=_RADIUS)
    screen.blit(win, rect.topleft)


def _name_height(resources, speaker):
    return resources.pixelfont(20).get_height() + 10 if speaker_name(speaker) else 0


def _draw_name(screen, resources, rect, speaker, alpha, text_x):
    name = speaker_name(speaker)
    if not name:
        return
    label = resources.pixelfont(20).render(name, False, speaker_color(speaker))
    label.set_alpha(alpha)
    screen.blit(label, (text_x, rect.y + _TEXT_TOP))


def _text_rect(rect, text_x, text_w, reserved_bottom=0, name_height=0):
    return pygame.Rect(text_x, rect.y + _TEXT_TOP + name_height, text_w,
                       rect.h - _TEXT_TOP - name_height - _TEXT_BOTTOM - reserved_bottom)


def _draw_text(screen, resources, rect, lines, style, *, chars, center, valign,
               body_size, text_x, text_w, alpha,
               text_transform, text_color, text_jitter, reserved_bottom=0, name_height=0):
    visible = _visible_lines(lines, chars)
    body = resources.pixelfont(body_size)
    line_h = _line_height(body)
    total_h = len(lines) * line_h - 2
    content = _text_rect(rect, text_x, text_w, reserved_bottom, name_height)
    start_y = content.y + max(0, (content.h - total_h) // 2) if valign == "center" else content.y
    for i, ln in enumerate(visible):
        draw = text_transform(ln) if text_transform else ln
        surf = body.render(draw, False, text_color or style.text)
        surf.set_alpha(alpha)
        if center:
            x = text_x + (text_w - surf.get_width()) // 2
        else:
            j = random.randint(-text_jitter, text_jitter) if text_jitter > 0 else 0
            x = text_x + j
        screen.blit(surf, (x, start_y + i * line_h))


def _draw_footer(screen, resources, rect, style, *, hint_text, alpha, text_x, font_size):
    hints, height = _footer_layout(resources, rect, hint_text, text_x, font_size)
    if not height:
        return
    font = resources.pixelfont(font_size)
    y = rect.bottom - len(hints) * font.get_height() - 8
    for index, hint in enumerate(hints):
        surf = font.render(hint, False, style.hint)
        surf.set_alpha(alpha)
        # Keep the ready-to-advance arrow separate from the control labels.
        right = rect.right - 46
        screen.blit(surf, (right - surf.get_width(), y + index * font.get_height()))


def _draw_arrow(screen, rect, alpha, arrow_on, complete):
    if not (complete and _arrow_visible(arrow_on)):
        return
    ax, ay = rect.right - 26, rect.bottom - 24
    tri = pygame.Surface((22, 15), pygame.SRCALPHA)
    pygame.draw.polygon(tri, (*TEXT_MUTED, alpha), [(2, 2), (20, 2), (11, 13)])
    screen.blit(tri, (ax - 11, ay))


# ── 戦闘パネル（顔アイコン・省スペース） ──────────────────────────────

# 通常の短い台詞は省スペースに保ち、折返しや操作欄があるときだけ上へ広げる。
_COMBAT_BODY_SIZE = 22
_COMBAT_PORTRAIT_SIZE = 68        # 顔アイコンは固定
# 下端はボスHPバー（y=564〜）直上の体幹ゲージ（y=555〜561）に掛からない位置に置く
# （実機FB: 旧 y=456..564 は体幹ゲージを完全に隠していた）。
COMBAT_PANEL_RECT = pygame.Rect(26, SCREEN_HEIGHT - 164, SCREEN_WIDTH - 52, 108)


def draw_combat_panel(screen, resources, speaker, lines, *, hint_text=None, style=COMBAT_RED_STYLE,
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
    _, footer_height = _footer_layout(resources, rect, hint_text, text_x, 16)
    name_height = _name_height(resources, speaker)
    rect = _panel_for_text(rect, body, wrapped, footer_height, name_height)

    _draw_window(screen, rect, style, alpha)
    if portrait:
        size = _COMBAT_PORTRAIT_SIZE
        img = pygame.transform.smoothscale(resources.image(portrait), (size, size)).convert_alpha()
        img.set_alpha(alpha)
        px, py = rect.x + 14, rect.y + (rect.h - size) // 2
        screen.blit(img, (px, py))
    _draw_name(screen, resources, rect, speaker, alpha, text_x)
    _draw_text(screen, resources, rect, wrapped, style, chars=chars, center=center,
               valign="center", body_size=_COMBAT_BODY_SIZE,
               text_x=text_x, text_w=text_w, alpha=alpha, text_transform=text_transform,
               text_color=None, text_jitter=text_jitter,
               reserved_bottom=max(0, footer_height - _TEXT_BOTTOM), name_height=name_height)
    _draw_footer(screen, resources, rect, style, hint_text=hint_text, alpha=alpha,
                 text_x=text_x, font_size=16)
    if complete is None:
        complete = hint_text is not None
    _draw_arrow(screen, rect, alpha, arrow_on, complete=complete)
    return _text_rect(rect, text_x, text_w, max(0, footer_height - _TEXT_BOTTOM), name_height)


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


def draw_story_panel(screen, resources, speaker, lines, *, chars=None, complete=True, hint_text="",
                     style=DARK_STYLE, show_portrait=True, text_transform=None,
                     text_color=None, text_jitter=0, center=False, arrow_on=None,
                     left_speaker=None, right_speaker=None):
    # A stable stage for every page: portraits, speaker and footer never jump.
    rect = pygame.Rect(40, SCREEN_HEIGHT - 258, SCREEN_WIDTH - 80, 224)
    text_w = rect.w - 52
    _, footer_height = _footer_layout(resources, rect, hint_text, rect.x + 26, 18)
    name_height = resources.pixelfont(20).get_height() + 10
    available = rect.h - _TEXT_TOP - name_height - max(footer_height, _TEXT_BOTTOM)
    for body_size in (26, 24, 22, 20, 18, 16):
        body = resources.pixelfont(body_size)
        wrapped = _wrap_lines(body, lines, text_w)
        if len(wrapped) * _line_height(body) - 2 <= available:
            break

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
    text_x = rect.x + 26
    _draw_name(screen, resources, rect, speaker, 255, text_x)
    text_w = rect.w - 52
    # 固定枠内の折返しと文字サイズは全文から決め、文字送り中も動かさない。
    _draw_text(screen, resources, rect, wrapped, style, chars=chars, center=center,
               valign="center" if center else "top", body_size=body_size,
               text_x=text_x, text_w=text_w, alpha=255,
               text_transform=text_transform, text_color=text_color, text_jitter=text_jitter,
               reserved_bottom=max(0, footer_height - _TEXT_BOTTOM), name_height=name_height)
    _draw_footer(screen, resources, rect, style, hint_text=hint_text, alpha=255,
                 text_x=text_x, font_size=18)
    _draw_arrow(screen, rect, 255, arrow_on, complete=complete)
