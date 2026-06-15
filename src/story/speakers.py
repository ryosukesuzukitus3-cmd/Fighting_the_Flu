"""話者（speaker）定義の SSOT。

台本中の `[澤口]` `[カロナール先輩]` `[Narration]` などの発言主を、
表示名と色で一元管理する。セリフボックスのネームプレート表示に使う。
"""
from __future__ import annotations
from dataclasses import dataclass

# ── 話者キー定数（台本の発言主ラベルと一致させる）─────────────────
SAWAGUCHI      = "澤口"
KARONARU       = "カロナール先輩"
KARONARU_MAX   = "カロナール先輩・薬効最大"
NARRATION      = "Narration"
UNKNOWN        = "???"
SYSTEM         = "SYSTEM"

# ボス（BOSS_NAMES と一致）
BOSS1          = "悪寒大王インフルX"
BOSS2          = "情報汚染超人野獣ブロリー"
BOSS3          = "婚活要塞マッチング・ゼロ"
BOSS4          = "棋理の化身　藤井竜王"
BOSS4_FORM2    = "赤眼の真・藤井四段"
BOSS_SAWAGUCHI = "投了王サワグチ"


# ダミーポートレート（tools/gen_dummy_portraits.py で生成。専用素材が来たら差し替え）
_KARONARU_PORTRAIT     = "graphic/portrait_karonaru_dummy.png"
_KARONARU_MAX_PORTRAIT = "graphic/portrait_karonaru_max_dummy.png"
_MATCHING_ZERO_PORTRAIT = "graphic/portrait_matching_zero_dummy.png"


@dataclass(frozen=True)
class Speaker:
    key:     str
    name:    str                      # ネームプレート表示名（""=非表示）
    color:   tuple[int, int, int]
    portrait: str | None = None       # 顔アイコン画像（戦闘パネル等。None=非表示）
    tachie:   str | None = None       # 立ち絵（全身）画像。ストーリーパネルで優先使用。
                                      # None のときは portrait（顔）にフォールバックする。


# key → Speaker。name が "" の話者はネームプレートを描画しない。
# portrait はゲーム内スプライト/プレイヤー画像を流用。未設定の話者は画像非表示。
SPEAKERS: dict[str, Speaker] = {
    SAWAGUCHI:      Speaker(SAWAGUCHI,      "澤口",                 (180, 210, 255), "graphic/sawaguchi_49_64.png"),
    KARONARU:       Speaker(KARONARU,       "カロナール先輩",        (140, 230, 150), _KARONARU_PORTRAIT),
    KARONARU_MAX:   Speaker(KARONARU_MAX,   "カロナール先輩・薬効最大", (200, 255, 210), _KARONARU_MAX_PORTRAIT),
    NARRATION:      Speaker(NARRATION,      "",                    (205, 205, 215)),
    UNKNOWN:        Speaker(UNKNOWN,        "？？？",               (210, 90, 90)),
    SYSTEM:         Speaker(SYSTEM,         "",                    (255, 220, 80)),
    BOSS1:          Speaker(BOSS1,          BOSS1,                 (255, 90, 90),  "graphic/enemy_バイキンマン68x80.png"),
    BOSS2:          Speaker(BOSS2,          BOSS2,                 (255, 90, 90),  "graphic/enemy_ブロリー.png"),
    BOSS3:          Speaker(BOSS3,          BOSS3,                 (255, 120, 170), _MATCHING_ZERO_PORTRAIT),
    BOSS4:          Speaker(BOSS4,          BOSS4,                 (255, 110, 90), "graphic/enemy_fujii4dan.png"),
    BOSS4_FORM2:    Speaker(BOSS4_FORM2,    BOSS4_FORM2,           (255, 60, 60),  "graphic/藤井四段第二形態_もう一度.png"),
    BOSS_SAWAGUCHI: Speaker(BOSS_SAWAGUCHI, BOSS_SAWAGUCHI,        (200, 60, 200), "graphic/sawaguchi_49_64.png"),
}

# テキスト本体の既定色（ネームプレートとは別。読みやすさ優先で統一）
DEFAULT_TEXT_COLOR = (255, 240, 200)


def speaker_name(key: str) -> str:
    """ネームプレート表示名を返す（未登録キーはそのまま、""=非表示）。"""
    sp = SPEAKERS.get(key)
    return sp.name if sp is not None else key


def speaker_color(key: str) -> tuple[int, int, int]:
    """話者のネームプレート色を返す（未登録キーは白）。"""
    sp = SPEAKERS.get(key)
    return sp.color if sp is not None else (230, 230, 230)


def speaker_portrait(key: str) -> str | None:
    """話者の顔アイコン画像パスを返す（未設定/未登録は None=非表示）。"""
    sp = SPEAKERS.get(key)
    return sp.portrait if sp is not None else None


def speaker_tachie(key: str) -> str | None:
    """話者の立ち絵画像パスを返す（未設定は None＝顔アイコンにフォールバック）。"""
    sp = SPEAKERS.get(key)
    return sp.tachie if sp is not None else None


# ── 陣営（立ち絵の左右割り当て用） ────────────────────────────────
# 味方は左、敵は右。味方同士は主人公(澤口)を左、先輩を右に置く。
ALLY_SPEAKERS = {SAWAGUCHI, KARONARU, KARONARU_MAX}


def is_ally(key: str) -> bool:
    return key in ALLY_SPEAKERS


def is_character(key: str) -> bool:
    """立ち絵/顔を持つ登場人物か（Narration/SYSTEM 等は False）。"""
    sp = SPEAKERS.get(key)
    return bool(sp and (sp.portrait or sp.tachie))
