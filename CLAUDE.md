# CLAUDE.md — インフルとの死闘 開発ガイド

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
| 不整合があった場合 | フックが exit 2 で差し戻し、Claude がその場で修正 |
| `pytest` | `tests/test_consistency.py` で同じ整合性を検証 |

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
.venv/Scripts/python main.py

# バランスシート確認
.venv/Scripts/python tools/balance_sheet.py

# ボス弾幕プレビュー
.venv/Scripts/python tools/preview_boss.py --stage 4 --pattern all
```
