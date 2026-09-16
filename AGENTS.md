# AGENTS.md — インフルとの死闘 開発ガイド

<!-- 共有内容は docs/agent_guide_shared.md を編集し、tools/run.py docs で両ガイドへ反映する。 -->

## Codexの作業記憶

必要な場合に `.codex/memory/` を参照する。日付のあるroadmapや過去の状態は現在の計画・進捗として扱わず、コードとPRの状態を確認する。
メモリは補助資料であり、ユーザーの現在の依頼とこのガイドを優先する。メモリ構成を変更するときは先に提案する。

<!-- AUTOGEN:agent_guide START -->
## SSOT 原則（反映漏れ防止）

マスターデータは **1箇所だけ** に定義し、他は全てそこから導出する。

| データ種別 | 唯一のソース |
|---|---|
| 敵一覧・SE・ドロップ率・基本ステータス | `src/core/registries.py` > `ENEMY_DEFS` |
| アイテム一覧・ドロップ重み | `src/core/registries.py` > `ITEM_DEFS` |
| 敵・アイテム生成 | `src/core/factories.py` |
| ステージ数 | `data/stages/stage*.json` → `registries.stage_ids()` |
| ボス攻撃パターン一覧 | `src/entities/enemies/boss.py` > `_PHASE_CONFIGS`（`4f3`＝頑固王サワグチ含む） |
| 武器メインレベル | `src/entities/weapon.py` > `_MAIN_LEVELS` |
| 難易度スケール・バトルv2定数（体幹/体温/持ち駒/症状悪化） | `src/core/balance.py`（純ロジックは `src/core/battle_systems.py`） |
| ステージ名・ボス名 | `src/scenes/game/config.py` |
| セリフ・ナレーション・カットシーン | `src/story/script.py` |
| ステージ間会話・カットシーンの並び（物語タイムライン） | `src/story/script.py` > `STORY_BEATS`（再生は `src/scenes/story_flow.py`） |
| 最終決戦セリフ（頑固王サワグチ） | `src/story/script.py` > `BOSS_FORM3_INTRO`・`FINAL_SEQ`・`FINAL_BANNERS` |
| 話者（表示名・色） | `src/story/speakers.py` |
| BGM/SE エイリアス | `src/story/aliases.py` |
| ストーリー進行フラグ | `src/story/state.py`（`game.story`） |
| 相棒エンティティ（カロナール先輩） | `src/entities/companion.py` > `Karonaru` |
| 脚本（正典・全台本・演出注記。ユーザー編集の入力点） | `docs/story.md`（セリフ実装の SSOT は `src/story/script.py`。相互同期） |

## 作業原則

- ユーザーの目的と現在の依頼を起点にする。このガイド・設計書・過去のメモリも古くなり得るため、実装・実画面・検証結果と照合する。
- 自分で実装するか、独立した範囲を分担するかは、並列化の効果と作業量で判断する。特定モデルへの委任や、主担当の実装禁止は設けない。分担時は対象ファイルと責任範囲を明確にし、主担当が統合と最終確認を担う。
- 質問・評価の依頼には診断を返す。修正を任された場合は、既に与えられた権限の範囲で実装・検証を進める。ユーザー作業の破壊、依頼範囲の拡大、未提供の必須情報があるときに確認する。
- 例外分岐が増える、同じ概念が別々のデータに分かれる、ユーザーが構造を疑う場合は、局所修正の前にデータの所有先を見直す。既存テストは設計の根拠ではなく、守りたい振る舞いを検証するものとして扱う。
- 完了報告は実行結果を根拠にし、確認できた範囲、残る問題、未検証の範囲を区別する。失敗は理由を示し、成功として扱わない。

## 運用上の確定判断

- `.claude/hooks` と `.codex/hooks` の統合は見送り（2026-06-20）。各環境の起動方法に違いがあり、統合による条件分岐を増やさない。両方を残し、共通の不具合は個別に修正する。
- ローカルの自動フック登録は既定で空とする。自動生成・HTML確認ダイアログ・API呼び出し・ターン終了時の停止に開発を依存させない。検証は明示的なコマンドとCIで行う。

## 変更時に揃えるもの

| 変更 | 同じ変更で確認・同期する箇所 |
|---|---|
| 敵 | `src/entities/enemies/`、`ENEMY_DEFS`（SE・ドロップ・ステータス・説明）、`factories.py` |
| アイテム | `src/entities/items/`、`ITEM_DEFS`（ドロップ重み）、`factories.py` |
| ステージ | `data/stages/stage{N}.json`、`STAGE_NAMES` / `BOSS_NAMES`、`STORY_BEATS` と各ボス会話、`_BOSS_CONFIG` / `_PHASE_CONFIGS`。配布時に使う地形・マスクの同梱も確認する |
| 武器の段階 | `weapon.py` の `_MAIN_LEVELS`、`config.py` の `MAIN_NEXT_NAMES` |
| 会話・ストーリー | `script.py` と `docs/story.md` の該当台本を逐語同期する。新しい話者は `speakers.py`、BGM/SE別名は `aliases.py` に登録する |
| 共有ガイド | この `docs/agent_guide_shared.md` を変更し、`tools/run.py docs` で `AGENTS.md` / `CLAUDE.md` へ反映する |

ストーリー変更の前に `docs/story.md` 冒頭の正典を読む。内輪ネタや弄りの線引きを守り、正典そのものを変える判断はユーザーの許可範囲で行う。台本に存在するだけでなく、実際の再生経路へ届くことも確認する。

`docs/design.md` と両ガイドの `<!-- AUTOGEN:* -->` 内は手書きしない。`tools/run.py docs` で生成し、手書きの説明は同じ変更で整合させる。

## 作業場所とPR

- `C:\02_work\01_Fighting_the_Flu` は管理用mainとし、同期・worktree管理に使う。実装や修正は `C:\02_work\01_Fighting_the_Flu-worktrees` 配下のタスク別worktreeで行う。
- 作業前に `git status --short --branch` とworktree一覧を確認し、未コミットのユーザー作業や他タスクを巻き込まない。ブランチは `codex/{短い内容}` または `claude/{短い内容}` を使う。
- worktreeごとに `.venv` を用意し、対応Pythonの下限は `pyproject.toml` に従う。同じタスクの継続は既存worktreeの状態を確認して再開できる。
- PRには変更理由、結果、実行した検証と未確認事項を書く。公開済みPRの判断では、検証したコミットがPR先端と一致しているかを確認する。
- マージはユーザーの許可範囲で行う。マージ後の削除は、そのタスクのworktree・ブランチであること、未コミット変更がないこと、必要な証拠を保存したことを確認してから行う。他タスクは削除しない。

```powershell
# 管理用mainから、最新のmainを起点に作業場所を用意する例
git fetch --prune origin
git worktree add C:\02_work\01_Fighting_the_Flu-worktrees\flu-codex-some-task -b codex/some-task origin/main

# 新しいworktree内で実行する
py -3 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

## 検証と証拠

基本の確認は以下のとおり。テストは影響範囲に合わせ、結果が揃った後の同じ確認を理由なく繰り返さない。CIでは構文・整合性・テストを確認する。

```powershell
.venv\Scripts\python tools\run.py docs-check
.venv\Scripts\python tools\run.py check
.venv\Scripts\python tools\run.py test
.venv\Scripts\python tools\run.py pycompile
```

- 生成データを変更した場合は `tools/run.py docs` を実行してから差分を確認する。
- 見た目・操作・進行に関する変更は、必要な画面や実際の振る舞いを確認する。画像のbefore/afterやPR添付を一律の必須条件にはしない。
- 実プレイ報告には対象バージョン、入力方法、到達範囲を記録する。自動キャプチャ、デバッグ直行、通常操作の通しプレイは区別し、ウインドウへの入力が届いたことを確認する。
- 再現画像は `captures/` などへ保存する。調査用の一時画像は通常のソース差分へ混ぜず、役立つ場合だけPRに添付する。
- `pr-media` / `pr-html` / `pr-report` は外部へアップロードする任意ツール。PR作成のたびに実行しない。使用時はアップロード内容と公開範囲を確認する。ホスティング用 `media` ブランチはmainへマージしない。
- HTMLレビューや有料APIによる装飾も任意。通常のMarkdownレビューで足りる場合は追加処理を行わない。

## よく使うコマンド

`tools/run.py` は実行したworktreeの `.venv` を優先し、UTF-8と必要なヘッドレス設定を揃える。補助ツールの詳細は `docs/tools.md` を参照する。

```powershell
.venv\Scripts\python tools\run.py game
.venv\Scripts\python tools\run.py playtest
.venv\Scripts\python tools\run.py capture --stage 4 --boss --form 3
.venv\Scripts\python tools\run.py preview-boss --stage 4 --pattern all
.venv\Scripts\python tools\run.py balance
```

`gh` はPATHを優先し、見つからない場合は `GH_EXE`、`~/bin/gh.exe`、`C:\Program Files\GitHub CLI\gh.exe`、現在のvenvの `Scripts\gh.exe` を確認する。
<!-- AUTOGEN:agent_guide END -->
