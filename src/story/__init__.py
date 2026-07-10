"""ストーリー（セリフ・ナレーション・カットシーン）の SSOT パッケージ。

セリフ・演出の唯一のソースはこのパッケージ（特に script.py）。
読み物としての脚本（正典・全台本・演出注記）は `docs/story.md`。
ゲーム本編のセリフ・話者・BGM/SE エイリアス・進行フラグは、すべてこの
パッケージを単一ソースとして参照する（registries.py と同じ SSOT 方針）。

- speakers : 話者定義（表示名・色）
- lines    : Line / Page データ構造
- script   : 全セリフ内容（SSOT）
- aliases  : BGM_* / SE_* エイリアス → 実ファイルパス
- state    : StoryState（進行フラグ）
"""
