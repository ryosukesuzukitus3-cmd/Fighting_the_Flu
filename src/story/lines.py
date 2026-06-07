"""セリフ・カットシーンのデータ構造。

台本 §9.1 の id/speaker/text/se/fx 構造に対応する。

- Line : インゲームに差し込む 1 行のセリフ（ボス intro/mid/defeat 用）。
- Page : 全画面カットシーンの 1 ページ（複数行＋話者）。プロローグ/幕間/
         エピローグ/エンドロール用。
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
