## SSOT 原則（反映漏れ防止）

マスターデータは **1箇所だけ** に定義し、他は全てそこから導出する。

| データ種別 | 唯一のソース |
|---|---|
| 敵一覧・SE・ドロップ率・基本ステータス | `src/core/registries.py` > `ENEMY_DEFS` |
| アイテム一覧・ドロップ重み | `src/core/registries.py` > `ITEM_DEFS` |
| 敵・アイテム生成 | `src/core/factories.py` |
| ステージ数 | `data/stages/stage*.json` → `registries.stage_ids()` |
| ボス攻撃パターン一覧 | `src/entities/enemies/boss.py` > `_PHASE_CONFIGS`（`4f3`＝投了王サワグチ含む） |
| 武器メインレベル | `src/entities/weapon.py` > `_MAIN_LEVELS` |
| 難易度スケール | `src/core/balance.py` |
| ステージ名・ボス名 | `src/scenes/game/config.py` |
| セリフ・ナレーション・カットシーン | `src/story/script.py` |
| 最終決戦セリフ（投了王サワグチ） | `src/story/script.py` > `BOSS_FORM3_INTRO`・`FINAL_SEQ`・`FINAL_BANNERS` |
| 話者（表示名・色） | `src/story/speakers.py` |
| BGM/SE エイリアス | `src/story/aliases.py` |
| ストーリー進行フラグ | `src/story/state.py`（`game.story`） |
| 相棒エンティティ（カロナール先輩） | `src/entities/companion.py` > `Karonaru` |

## 機能変更チェックリスト

### 敵を追加するとき

1. `src/entities/enemies/{name}.py` を作成
2. `src/core/registries.py` > `ENEMY_DEFS` に1行追加（se / drop_chance / stats / doc_movement / doc_notes を設定）
3. `src/core/factories.py` に生成分岐を追加
4. `python tools/gen_docs.py` を実行（design.md の敵一覧表が自動更新される）
5. `python tools/check_consistency.py` で全項目パスを確認

### ステージを追加するとき

1. `data/stages/stage{N}.json` を作成（`stage_id`・`bgm`・`events` を記述）
2. `src/scenes/game/config.py` > `STAGE_NAMES`・`BOSS_NAMES` に追加
3. `src/story/script.py` > `STAGE_INTRO`・`BOSS_INTRO`・`BOSS_MID`・`BOSS_DEFEAT` にセリフを追加
4. `src/entities/enemies/boss.py` > `_BOSS_CONFIG`・`_PHASE_CONFIGS` に追加
5. `python tools/check_consistency.py` で確認

### アイテムを追加するとき

1. `src/entities/items/{name}.py` を作成
2. `src/core/registries.py` > `ITEM_DEFS` に1行追加（`drop_weight > 0` でランダムドロップ対象）
3. `src/core/factories.py` に生成分岐を追加
4. `python tools/check_consistency.py` で確認

### 武器レベルを変更するとき

1. `src/entities/weapon.py` > `_MAIN_LEVELS` を変更（唯一のソース）
2. `src/scenes/game/config.py` > `MAIN_NEXT_NAMES` の長さを合わせる
3. `python tools/check_consistency.py` で段数一致を確認

### セリフ・ストーリーを変更するとき

1. セリフ／ナレーション／カットシーンの内容は `src/story/script.py` だけを編集（唯一のソース）
2. 新しい話者を出す場合は `src/story/speakers.py` > `SPEAKERS` に追加（表示名・色）
3. 新しい BGM/SE エイリアスは `src/story/aliases.py` に追加（未用意なら `None`＝ダミー扱い）
4. `python tools/check_consistency.py --section story` で話者登録・ステージ網羅・実ファイル存在を確認

## docs の更新方針

- `docs/design.md` の `<!-- AUTOGEN:* -->` 内は **手で書かない**
- gen_docs.py が自動更新する（ターン終了時の Stop フックでも自動実行）
- 散文・設計説明・セクション見出しは手書き

## 自動化されている仕組み

| タイミング | 動作 |
|---|---|
| ターン終了時（Stopフック） | `gen_docs.py` 実行 → `check_consistency.py` 実行 |
| 不整合があった場合 | フックが exit 2 で差し戻し、{{AGENT}} がその場で修正 |
| `pytest` | `tests/test_consistency.py` で同じ整合性を検証 |

## {{AGENT}} PR運用フロー

問題調査からPR作成までを任せる依頼では、{{AGENT}} は以下を標準手順にする。

1. 管理用フォルダ `C:\02_work\01_Fighting_the_Flu` では編集せず、タスク別 worktree で作業する
2. `git status --short --branch` で未コミット変更を確認し、ユーザー作業を巻き込まない
3. 作業ブランチは担当エージェントの小文字prefixで切る（Claude→`claude/{短い内容}`、Codex→`codex/{短い内容}`。例: `claude/fix-stage4-boss-ui`）
4. worktree フォルダは `C:\02_work\01_Fighting_the_Flu-worktrees\flu-{agent}-{短い内容}` に作る
5. worktree ごとに `.venv` を作成し、管理用フォルダの `.venv` は標準運用では共用しない
6. `rg`・コード読解・`docs/design.md` で仕様とSSOTを確認し、必要なら `data/stages/*.json` も見る
7. 見た目や挙動の疑いがある場合は `tools/run.py capture ...` でPNGを取り、必要なら `tools/run.py game` か `tools/run.py preview-boss ...` で実プレイ確認する
8. 修正はSSOTに沿って最小範囲に入れ、手動生成が必要な資料は `tools/run.py docs` で再生成する
9. `tools/run.py check` と、影響範囲に応じて `tools/run.py test` / `tools/run.py pycompile` / 再キャプチャを実行する
10. 差分・検証結果・確認したキャプチャをPR本文にまとめ、GitHub CLI が使える環境では push してPRを作成する

再現に使ったキャプチャは `captures/` 配下に出力する。調査用の一時画像をPRに含めない場合は、最終差分へ混ぜず、PR本文やコメントでファイル名だけ共有する。

### worktree 運用

`C:\02_work\01_Fighting_the_Flu` は管理用 main フォルダとして扱い、`main` の同期・worktree 作成・worktree 削除だけに使う。実作業は必ず `C:\02_work\01_Fighting_the_Flu-worktrees` 配下のタスク別 worktree で行う。

```powershell
# Codex の新規タスク
cd C:\02_work\01_Fighting_the_Flu
git fetch --prune origin
git worktree add C:\02_work\01_Fighting_the_Flu-worktrees\flu-codex-some-task -b codex/some-task origin/main

# Claude の新規タスク
cd C:\02_work\01_Fighting_the_Flu
git fetch --prune origin
git worktree add C:\02_work\01_Fighting_the_Flu-worktrees\flu-claude-some-task -b claude/some-task origin/main
```

各 worktree の初回セットアップは、その worktree 内で行う。

```powershell
cd C:\02_work\01_Fighting_the_Flu-worktrees\flu-codex-some-task
py -3 -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\python -m pip install -e ".[dev]" markdown
.venv\Scripts\python tools\run.py check
```

`tools\run.py pr-report --fancy` を使うタスクだけ、追加で `anthropic` を入れる。

```powershell
.venv\Scripts\python -m pip install anthropic
```

PR がマージされたら、該当 worktree とマージ済みブランチを削除する。未コミット変更がある worktree は削除しない。

```powershell
cd C:\02_work\01_Fighting_the_Flu
git worktree remove C:\02_work\01_Fighting_the_Flu-worktrees\flu-codex-some-task
git branch -d codex/some-task
git push origin --delete codex/some-task
```

### PR 可視化

PR 本文に載せる画像やHTMLは `media` ブランチへアップロードする。`media` はホスティング専用ブランチで、`main` にはマージしない。

```powershell
.venv\Scripts\python tools\run.py pr-media captures\before.png captures\after.png
.venv\Scripts\python tools\run.py pr-html .html\report.html
.venv\Scripts\python tools\run.py pr-report docs\design.md
```

`gh` は `PATH` を優先し、見つからない場合は `GH_EXE`、`~/bin/gh.exe`、`C:\Program Files\GitHub CLI\gh.exe`、現在の venv の `Scripts\gh.exe` の順に探す。

## ツール使用方法

実行環境・文字化け事故を避けるため、可能なら直接 `python` を叩かず `tools/run.py` を使う。
`tools/run.py` はローカル `.venv` を優先し、UTF-8 出力と pygame のヘッドレス設定を揃える。

```powershell
# 推奨ラッパー
.venv/Scripts/python tools/run.py check
.venv/Scripts/python tools/run.py test
.venv/Scripts/python tools/run.py docs
.venv/Scripts/python tools/run.py game

# docs を手動更新
.venv/Scripts/python tools/gen_docs.py

# 整合性チェック
.venv/Scripts/python tools/check_consistency.py

# テスト
.venv/Scripts/pytest

# ゲーム起動
.venv/Scripts/python tools/run.py game

# 任意状態の画面キャプチャ
.venv/Scripts/python tools/run.py capture --stage 4 --boss --form 3

# ボス弾幕プレビュー
.venv/Scripts/python tools/run.py preview-boss --stage 4 --pattern all

# バランスシート確認
.venv/Scripts/python tools/run.py balance
```
