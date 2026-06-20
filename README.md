# インフルとの死闘

2D 横スクロールシューティングゲーム。高熱でうなされる主人公 **澤口** が、相棒 **カロナール先輩** とともにインフルエンザ――そして現代を取り巻く厄介ごと――と戦う。全4ステージ、各ステージに固有ボス、最終決戦は **投了王サワグチ**。

- 言語/エンジン: Python + [pygame-ce](https://pyga.me/)
- 対応 Python: 3.11 以上
- バージョン: 0.2.0

---

## セットアップと起動

Windows / PowerShell の例（リポジトリ直下で実行）:

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python main.py
```

`tools/run.py` 経由でも起動できます（`.venv` 優先・UTF-8/headless 設定を揃えるラッパー）:

```powershell
.venv\Scripts\python tools\run.py game
```

> デバッグ機能を無効化して起動するには `python -O main.py`。

---

## 操作方法

| 操作 | キー |
|---|---|
| 移動 | ↑ ↓ ← → |
| ショット | `Z` |
| レーザー | `Space` |
| ウェポン選択 | `V` |
| ポーズ | `X` |

キーバインドは設定で変更できます（唯一のソースは `src/managers/settings.py`）。

デバッグ操作（通常起動時のみ。`python -O` で完全に除去）:

| キー | 効果 |
|---|---|
| `F1` | 無敵トグル |
| `F2` | ウェポンアイテムをドロップ |
| `F3` | 現在状態をコンソール出力 |
| `F5` | 次ウェーブへスキップ |
| `F6` | ボスを即スポーン |
| `Ctrl+1`〜`Ctrl+4` | 指定ステージへワープ |

詳細は [docs/tools.md](docs/tools.md) を参照。

---

## ステージとボス

| ステージ | 章 | ボス |
|---|---|---|
| 1 | 発熱回廊 | 悪寒大王インフルX |
| 2 | ミーム汚染地帯 | 情報汚染超人野獣ブロリー |
| 3 | 婚活・労働複合戦線 | 婚活要塞マッチング・ゼロ |
| 4 | 棋理深淵 | 棋理の化身 藤井竜王 → 赤眼の真・藤井四段 → 投了王サワグチ |

---

## 動作確認のしかた

### 通常プレイで確認
上の「セットアップと起動」のとおり `main.py`（または `tools/run.py game`）を起動して確認します。

### PR の内容をローカルで確認する
本リポジトリは Claude / Codex が **git worktree** で分担作業します（同時編集の事故防止）。PR を手元で試すときは次の方針が安全です。

- **マージ前**: その PR の作業ツリー（`..\01_Fighting_the_Flu-worktrees\flu-<agent>-<task>`）には専用 `.venv` が用意済みなので、そこで起動する:
  ```powershell
  cd C:\02_work\01_Fighting_the_Flu-worktrees\flu-claude-<task>
  .venv\Scripts\python main.py
  ```
- **マージ後**: 管理用フォルダの `main` を同期して起動する（ゲームの実行は読み取り操作なので管理用フォルダでも可）:
  ```powershell
  cd C:\02_work\01_Fighting_the_Flu
  git pull --ff-only
  .venv\Scripts\python main.py
  ```
- 管理用フォルダで **PR ブランチを `git checkout` するのは避ける**（worktree 運用と衝突するため）。

### 見た目だけを素早く確認（ヘッドレス）
ウィンドウを開かずに任意の状態を PNG で撮れます:

```powershell
.venv\Scripts\python tools\run.py capture --stage 4 --boss --form 3
```

オプションの詳細は [docs/tools.md](docs/tools.md) の「C-2 任意状態の画面キャプチャ」を参照。

---

## 開発

```powershell
.venv\Scripts\python -m pip install -e ".[dev]"   # pytest 等の開発依存も入れる
```

`tools/run.py` の主なサブコマンド:

| コマンド | 内容 |
|---|---|
| `check` | 整合性チェック（`tools/check_consistency.py`） |
| `test` | pytest |
| `docs` | `docs/design.md` ほか AUTOGEN ブロック再生成 |
| `game` | ゲーム起動 |
| `capture` | 任意状態のヘッドレス画面キャプチャ |
| `preview-boss` | ボス弾幕プレビュー |
| `stage3-rect-preview` | Stage3 地形素材 rect の全体/グループ別プレビュー画像とHTML一覧を生成（対話実行では自動表示） |
| `stage3-rect-editor` | Stage3 地形素材 rect を画像上でドラッグ編集してJSON保存 |
| `stage3-terrain-composer` | Stage3 地形素材を実寸のまま組み合わせた地形構成プレビュー画像とHTML一覧を生成 |
| `balance` | バランスシート出力 |
| `pr-media` / `pr-html` / `pr-report` | PR 用に画像/HTML/レポートを `media` ブランチへ上げて貼り付けリンクを出力 |

### 設計原則（SSOT）
マスターデータは1箇所だけに定義し、他はそこから導出します（反映漏れ防止）。詳細と機能追加チェックリストは **[CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md)**（共有ソースは `docs/agent_guide_shared.md`）を参照。ターン終了時の Stop フックで `gen_docs.py` → `check_consistency.py` が自動実行され、`tests/test_consistency.py` でも同じ整合性を検証します。

### ブランチ運用
- エージェントの作業は専用 worktree で行い、ブランチは Claude=`claude/<task>` / Codex=`codex/<task>`。
- 管理用フォルダ `C:\02_work\01_Fighting_the_Flu` は main 同期・worktree 作成/削除のみ（編集・コミットはしない）。

---

## プロジェクト構成

```
main.py                  エントリーポイント
src/
  core/                  ゲーム基盤（registries=SSOT, factories, balance, game ループ）
  entities/              プレイヤー・敵・ボス・弾・アイテム・相棒
  scenes/                タイトル / ゲーム / カットシーン / リザルト 等
  stages/                ステージ進行・スポーナー
  story/                 セリフ・話者・カットシーン（src/story が台本の SSOT）
  managers/              リソース / 入力 / サウンド / 設定
data/stages/             ステージ定義 JSON（ステージ数の唯一のソース）
assets/                  画像・音源
tools/                   補助ツール（run.py ほか）
tests/                   pytest（整合性テスト含む）
docs/                    design.md（設計・自動生成表）/ tools.md（ツール解説）
```

---

## ドキュメント
- [docs/design.md](docs/design.md) — 設計と自動生成のデータ表
- [docs/tools.md](docs/tools.md) — 補助ツールの使い方
- [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md) — 開発ガイド・SSOT 原則・機能追加チェックリスト
