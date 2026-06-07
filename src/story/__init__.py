"""ストーリー（セリフ・ナレーション・カットシーン）の SSOT パッケージ。

台本 `docs/fighting_the_flu_script.md` の内容をここに集約する。
ゲーム本編のセリフ・話者・BGM/SE エイリアス・進行フラグは、すべてこの
パッケージを単一ソースとして参照する（registries.py と同じ SSOT 方針）。

- speakers : 話者定義（表示名・色）
- lines    : Line / Page データ構造
- script   : 全セリフ内容（SSOT）
- aliases  : BGM_* / SE_* エイリアス → 実ファイルパス
- state    : StoryState（進行フラグ）
"""
