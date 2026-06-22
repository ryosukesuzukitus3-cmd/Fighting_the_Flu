"""セリフ・カットシーンのデータ構造。

台本 §9.1 の id/speaker/text/se/fx 構造に対応する。

- Line      : インゲームに差し込む 1 行のセリフ（ボス intro/mid/defeat 用）。
- Page      : 全画面カットシーンの 1 ページ（複数行＋話者）。プロローグ/幕間/
              エピローグ/エンドロール用。
- StoryBeat : 物語タイムラインの 1 ノード（ゲームプレイ間に挟まる会話シーン）。
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Line:
    """インゲームのセリフ 1 行（画面下部ボックスに 1 行表示）。"""
    speaker: str
    text:    str
    se:      str | None = None          # SE エイリアス（aliases.py で解決）
    fx:      tuple[str, ...] = ()        # FX エイリアス


@dataclass(frozen=True)
class Page:
    """全画面カットシーンの 1 ページ（複数行をまとめてタイプライター表示）。"""
    speaker: str
    lines:   tuple[str, ...]
    se:      str | None = None
    fx:      tuple[str, ...] = ()
    last:    bool = False               # 最終ページ（ヒント文言切替に使用）


def page(speaker: str, *lines: str, se: str | None = None,
         fx: tuple[str, ...] = (), last: bool = False) -> Page:
    """Page を簡潔に作るヘルパ。"""
    return Page(speaker, tuple(lines), se=se, fx=fx, last=last)


@dataclass(frozen=True)
class StoryBeat:
    """物語タイムラインの 1 ノード（ゲームプレイの合間に挟まる全画面会話）。

    会話は「ステージの属性」ではなく「並びの中の遷移」として扱う。
    ``before_stage`` は *この後に始まるゲームプレイのステージ* を指し、
    会話そのものをステージ番号に束縛しない。再生は
    ``src/scenes/story_flow.py`` が駆動する。
    """
    key:     str                         # 一意キー（"prologue" / "1->2" / ...）
    pages:   tuple[Page, ...]
    before_stage: int | None = None      # 直後に始まるステージ（無ければ None）
    theme:   str = "dark"                # 背景テーマ: dark / window / blackhole
    bgm:     str | None = None           # BGM エイリアス/パス（None=変更しない）
    stop_bgm: bool = False               # 入場時に BGM を停止する
    scene:   str = "cutscene"            # 再生シーン種別: cutscene / blackhole / credits
    fade_out_on_finish: bool = True      # 完了時に黒フェードを挟むか
    on_finish: str | None = None         # 完了時に走らせるフラグ更新フック名
