# AGENTS.md — インフルとの死闘 開発ガイド

<!-- このファイル固有の追記は AUTOGEN ブロックの外（このコメントの上、または END 以降）に書く。
     共有内容は docs/agent_guide_shared.md を編集し `tools/run.py docs` で両ガイドへ自動展開する。 -->

<!-- AUTOGEN:agent_guide START -->
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
| ステージ間会話・カットシーンの並び（物語タイムライン） | `src/story/script.py` > `STORY_BEATS`（再生は `src/scenes/story_flow.py`） |
| 最終決戦セリフ（投了王サワグチ） | `src/story/script.py` > `BOSS_FORM3_INTRO`・`FINAL_SEQ`・`FINAL_BANNERS` |
| 話者（表示名・色） | `src/story/speakers.py` |
| BGM/SE エイリアス | `src/story/aliases.py` |
| ストーリー進行フラグ | `src/story/state.py`（`game.story`） |
| 相棒エンティティ（カロナール先輩） | `src/entities/companion.py` > `Karonaru` |

## 設計判断の心得（distilled heuristics）

過去の振り返りから蒸留した「いつ・何をするか」の判断指針。哲学ではなく**トリガ**で書く。
新しい教訓が出たら、同じ「トリガ→対応→アンチパターン→実例」の形式でここに追記する。

### モデルを疑う前に band-aid を出さない

**トリガ**（次のどれかが出たら、局所修正の前にデータモデル自体を1段問い直す）:
- ユーザーが構造に疑問を向ける（「無駄に分割されている」「なんでこうなってる」「そもそも〜の必要ある？」）。
- 同じ概念が複数の入れ物／命名規則に割れている（例: 同じ会話が「前ステージ名の定数」と「次ステージ番号のキー」に跨る）。
- ある分類軸（ステージ番号など）で全ケースが綺麗に並ばず、例外を特殊分岐で足し続けている。
- 「整合性チェック／テストが要求するから現状維持」と言いたくなる。

**対応**:
- 「このデータはそもそも何に紐づくべきか」を先に問う。チェック／テストは設計の*帰結*であって*理由*ではない。設計が誤りならチェック側を直す前提で選択肢を出す。
- 「楽な案」と「筋の良い案」を分けて提示し、後者を率直に推す。実装は worktree＋PR で。

**アンチパターン**: 「整合性チェックが要求するから残すべき」のような、設計の*結果*を*理由*にすり替える循環論法。

**実例**: PR #70（ステージ間会話を `STAGE_INTRO[n]`／`INTERLUDE_*`＝ステージ所有 → 境界に紐づく `STORY_BEATS` タイムラインへ全面リファクタ）。最初に局所統合 #65 を出し、2回エスカレートされてやっと根本に到達 → #65 は無駄サイクルになった。

## エージェント運用ポリシー（モデル横断）

Anthropic の Claude Fable 5 プロンプティングガイド（https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5 ）から本プロジェクトに適用する運用指針。上位モデル（Fable 5 / Opus 級）向けの矯正が中心だが、明記のない項目はモデル・エージェントを問わず適用する。本プロジェクトは haiku / sonnet / opus / Fable 5 を併用する前提で書く。

### 役割分担（オーケストレーションと委任）

- この項はサブエージェント機構を持つ環境（Claude Code）向け。委任するかどうかは、タスク内容とメインエージェントのモデルに応じて判断する。
  - メインが上位モデル（Fable 5 / Opus 級）の場合: 計画・分解・統合・レビューに専念し、独立したサブタスク（調査・ドキュメント取得・定型実装・PR作成）は軽量モデルへ委任する（調査＝haiku（Explore）、実装・文書＝sonnet。opus はサブエージェントには基本使わない）。
  - メインが sonnet 級の場合: 中難易度までの実装は自分で実施してよい。委任は並列化や調査ファンアウトが効く場面に絞る。
- どう役割分担したか（自分で実施したか、どのモデルに何を委任したか）はユーザーに伝える。
- 委任は非同期で行い、完了を待つ間も自分の作業を続ける。サブエージェントが脱線している・文脈が不足していると気づいたら介入する。

### 進捗・完了報告の根拠付け

- 進捗や完了を報告する前に、各主張を今セッションのツール実行結果と突き合わせる。証拠を指せる作業だけを完了と報告し、未検証のものは未検証と明示する。
- テストが落ちたら出力ごと報告する。スキップした手順はスキップしたと書く。検証済みで完了したものは断定で書く（ヘッジしない）。
- 離席開発（ユーザーがリアルタイムで見ていない）前提の本プロジェクトでは特に厳守する。

### スコープ境界（余計な作業をしない・気付きは提案で返す）

- ユーザーが問題を説明・質問しているだけのときの成果物は「診断」。所見を報告して止まり、修正は依頼されてから行う。
- タスクに必要な範囲を超えた機能追加・リファクタ・抽象化を勝手に実行しない。バグ修正に周辺の清掃は不要。将来の仮定要件のための設計をしない。
- ただし、作業中に気付いた改善点・リスク・違和感は黙殺しない。実行はせず、提案・提言としてユーザーに知らせる。
- 状態を変えるコマンド（削除・設定変更・リセット）の前に、証拠がその操作を支持しているか確認する。既知の障害にパターンが似ているだけで原因が同じとは限らない。

### 完了報告の書き方

- 結果から書く。最初の1文は「何が起きたか／何が分かったか」。詳細と経緯はその後。
- 作業中の速記（矢印連鎖・略語・自作ラベル）を最終報告に持ち込まない。ファイル・コミット・フラグに言及するときは、それが何か／何が変わったかを平文で1つずつ書く。

### 自律実行時（離席開発）の心得

- ユーザーに確認して止まるのは、破壊的・不可逆な操作、実質的なスコープ変更、ユーザーにしか出せない入力が必要なときだけ。該当したら質問してターンを終える。それ以外は「〜しましょうか？」で止まらず進める。
- ターンの最後の段落が「計画・次にやることリスト・約束（あとで〜します）」になっていたら、いま実行してから終える。

### 指示文の書き方（このガイド自体を編集するとき）

- 上位モデル（Fable 5 / Opus 級）には、目的と制約を書き、手順の逐一指定はしない。過剰に規範的な指示（CRITICAL / MUST の乱用、手順の細分化）はかえって出力品質を下げる。
- 本ガイドのチェックリストは「プロジェクト固有の事実・制約（SSOT の場所、必須の同期手順）」であり、思考手順の指定ではない。この性質を保ったまま追記する。
- 軽量モデル（haiku 級）に委任するタスクの指示は逆に明示的・具体的に書く。

## 機能変更チェックリスト

### 敵を追加するとき

1. `src/entities/enemies/{name}.py` を作成
2. `src/core/registries.py` > `ENEMY_DEFS` に1行追加（se / drop_chance / stats / doc_movement / doc_notes を設定）
3. `src/core/factories.py` に生成分岐を追加
4. `python tools/gen_docs.py` を実行（design.md の敵一覧表が自動更新される）
5. `python tools/check_consistency.py` で全項目パスを確認

### ステージを追加するとき

1. `data/stages/stage{N}.json` を作成（`stage_id`・`bgm`・`terrain_layout`・`events` / `world_events` を記述）
2. `src/scenes/game/config.py` > `STAGE_NAMES`・`BOSS_NAMES` に追加
3. `src/story/script.py` > `STORY_BEATS`（ステージ間会話。`before_stage={N}` の遷移ビートを追加）・`BOSS_INTRO`・`BOSS_MID`・`BOSS_DEFEAT` にセリフを追加
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
| 不整合があった場合 | フックが exit 2 で差し戻し、Codex がその場で修正 |
| `pytest` | `tests/test_consistency.py` で同じ整合性を検証 |

## Codex PR運用フロー

問題調査からPR作成までを任せる依頼では、Codex は以下を標準手順にする。

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

# プレイ動画(GIF)を生成（PR添付・離席レビュー向け）
.venv/Scripts/python tools/run.py clip --stage 1 --out captures/stage1.gif

# ビジュアル回帰（baseline と差分HTML。見た目変更を確定したら --update で baseline 更新）
.venv/Scripts/python tools/run.py visual-regress
.venv/Scripts/python tools/run.py visual-regress --update

# ボス弾幕プレビュー
.venv/Scripts/python tools/run.py preview-boss --stage 4 --pattern all

# バランスシート確認
.venv/Scripts/python tools/run.py balance
```
<!-- AUTOGEN:agent_guide END -->
