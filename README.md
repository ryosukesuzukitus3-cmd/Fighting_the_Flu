# インフルとの死闘

2D 横スクロールシューティングゲーム。高熱でうなされる主人公 **澤口** が、相棒 **カロナール先輩** とともにインフルエンザ――そして現代を取り巻く厄介ごと――と戦う。全4ステージ、各ステージに固有ボス、最終決戦は **頑固王サワグチ**。

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
| レーザー（装備後） | `B`（押して発射・離して停止） |
| ウェポン選択 | `V` |
| ポーズ | `X` |
| メニュー決定 | `Enter` |
| メニューで戻る | `X`（設定画面では `Esc` も可） |

表は初期設定です。ゲーム操作とメニューの決定・戻るキーは設定画面で変更・初期化できます。HUDと強化画面も設定済みキーを表示します。初期値の唯一のソースは `src/managers/settings.py` です。
タイトルの開始には決定キーを使います。決定が初期設定のEnterの場合だけ、Spaceでも開始できます。

### 画面の使い方

ドット文字と余白を中心にした画面構成です。選択位置はコーラル色のカーソル（タイトルは下線）、強化の選択済みはミント色と文字で示します。会話のページ数・総数は表示しません。

- タイトルの「チュートリアル」から、移動・射撃・レーザーの冷却・実戦を練習できます。画面上部に現在の段階、設定済みのキー、達成状況を表示します。
- 設定は「音量」「ゲーム操作」「メニュー操作」の3分類です。Tabで切り替えます。矢印だけでも、項目の先頭から上へ進んで分類欄を選び、左右で切り替えられます。Tabを決定・戻るに割り当てた場合は矢印を使います。
- 音量は左右キーで5%ずつ調整します。キーの初期化は確認画面で選んだ後に実行し、設定から戻ると変更を保存します。Escは設定を離れるキーのため、決定キーには割り当てられません。
- 強化は「自機を選ぶ → 先輩を選ぶ → 内容を確認」の順に進みます。強化できる系統が未選択なら、その系統に戻ります。「保留して閉じる」では在庫を消費しません。
- 戦闘HUDはHPと体温を優先し、自機・先輩のどちらかに在庫があれば強化キーを表示します。各画面の下端には、その場で使える操作を表示します。

### 強化・継続

- **Wアイテム**を拾うと自機の強化在庫が増え、先輩が同行中なら先輩用の在庫も増えます。1プレイ中の初回取得では戦闘が止まり、強化画面を開きます。上段で自機、下段で先輩の強化を選び、最後に決定します。以後は在庫があるときにV（設定のウェポン選択キー）で開けます。
- 通常のメイン強化は**WIDE+まで**。**MEDIC**は最終決戦で先輩が復帰したときに得る3方向の貫通弾です。
- ポーズ中は戦闘とコンボの残り時間が止まります。強化画面や停止型会話中も戦闘操作は止まります。
- 死亡後の**継続**は有給を1日使い、現在の章の最初へHP全回復で戻ります。スコアは維持し、武器・先輩・物語の状態は章開始時に復元します。**最初からやり直す**は第一章へ戻り、スコア・強化・有給などを新規開始の状態に戻します。有給は最初に3日あり、0日になると継続できません。

デバッグ操作（ソースを最適化なしで起動した開発時のみ。配布版と `python -O` では除去）:

| キー | 効果 |
|---|---|
| `F1` | 無敵トグル |
| `F2` | ウェポンアイテムをドロップ |
| `F3` | 現在状態をコンソール出力 |
| `F4` | 押している間、ステージ中の進行を早送り |
| `F5` | 次ウェーブへスキップ |
| `F6` | ボスを即スポーン |
| `F7` | ウェポン状態を最大化 |
| `F8` | デバッグ情報の表示切替（通常ステージは既定で非表示） |
| `Ctrl+1`〜`Ctrl+9` | 登録済みステージへワープ（会話シーンなどでも有効） |

タイトル画面で `D` を押すとデバッグステージへ移動できる。ステージ内で `Tab` を開き、
`FX` タブを選ぶと、動画由来の全エフェクトを個別に再生確認できる。

通常ステージのデバッグ情報はF8で表示します。デバッグステージ（stage 99）では最初から表示されます。

詳細は [docs/tools.md](docs/tools.md) を参照。

## レビュー・改善項目

- [2026-09-16 プロジェクトレビュー・発見事項台帳](docs/review_20260916.md): 実プレイで見つけた不具合、既存PRとの対応関係、ストーリーとゲームシステムの評価。

---

## ステージとボス

| ステージ | 章 | ボス |
|---|---|---|
| 1 | 発熱回廊 | 悪寒大王インフルX |
| 2 | ミーム汚染地帯 | 情報汚染超人野獣ブロリー |
| 3 | 婚活・労働複合戦線 | 婚活要塞マッチング・ゼロ |
| 4 | 棋理深淵 | 棋理の化身 藤井竜王 → 赤眼の真・藤井四段 → 頑固王サワグチ |

---

## 動作確認のしかた

### 通常プレイで確認
上の「セットアップと起動」のとおり `main.py`（または `tools/run.py game`）を起動して確認します。

### PR の内容をローカルで確認する
本リポジトリは Claude / Codex が **git worktree** で分担作業します（同時編集の事故防止）。PR を手元で試すときは次の方針が安全です。

- **マージ前**: そのPRの作業ツリー（`..\01_Fighting_the_Flu-worktrees\flu-<agent>-<task>`）で専用 `.venv` を用意して起動する。既にある場合はその環境を使う:
  ```powershell
  cd C:\02_work\01_Fighting_the_Flu-worktrees\flu-claude-<task>
  .venv\Scripts\python main.py
  ```
- **マージ後**: 管理用mainを同期し、検証用worktreeを最新のmainから用意して起動する。ゲーム実行は設定・プレイログ等を書き込むため、読み取りだけの操作ではない。
- 管理用フォルダで **PR ブランチを `git checkout` するのは避ける**（worktree 運用と衝突するため）。

### 見た目だけを素早く確認（ヘッドレス）
ウィンドウを開かずに任意の状態を PNG で撮れます:

```powershell
.venv\Scripts\python tools\run.py capture --stage 4 --boss --form 3
```

オプションの詳細は [docs/tools.md](docs/tools.md) の「C-2 任意状態の画面キャプチャ」を参照。

### 配布EXEの確認

`game.spec` で作成したEXEは、リポジトリ外の一時フォルダから検査します。

```powershell
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\python -m PyInstaller game.spec --noconfirm
.venv\Scripts\python tools\run_packaged_smoke.py
```

`build-reports/packaged-smoke.json` に、全章の地形読込・初期化・描画・次章判定と、隔離したユーザー領域での設定・スコア・ログの保存確認を出力します。配布EXEの検査であり、通しプレイや全ボス撃破の確認とは別です。通常の配布版の保存先はWindowsでは `%APPDATA%\InfuruToNoShito\` です。

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
| `docs-check` | 生成済み資料が最新か、書き換えずに検査 |
| `game` | ゲーム起動 |
| `playtest` | 実ウインドウへの通常入力を補助する任意ツール |
| `capture` | 任意状態のヘッドレス画面キャプチャ |
| `preview-boss` | ボス弾幕プレビュー |
| `stage-rect-preview` | ステージ地形素材 rect の全体/グループ別プレビュー画像とHTML一覧を生成（旧名 `stage3-rect-preview` も使用可） |
| `stage-rect-editor` | ステージ地形素材 rect を画像上でドラッグ編集してJSON保存（旧名 `stage3-rect-editor` も使用可） |
| `stage-alpha-mask-editor` | ステージ地形素材 rect ごとの手動透明マスクをペイント編集してPNG保存（旧名 `stage3-alpha-mask-editor` も使用可） |
| `stage-terrain-composer` | `--stage 1` / `--stage 2` / `--stage 3` の地形素材を実寸のまま組み合わせたプレビュー画像とHTML一覧を生成（旧名 `stage3-terrain-composer` も使用可） |
| `stage-composer-report` | 選択ステージのruntime表示・衝突面・composer表示を同じ座標で比較するHTMLレポートを生成（旧名 `stage3-composer-report` も使用可） |
| `stage-designer` | `--stage 1` / `--stage 2` / `--stage 3` の地形・固定イベントを共通profileから編集 |
| `balance` | バランスシート出力 |
| `pr-media` / `pr-html` / `pr-report` | 任意の外部公開ツール。画像/HTML等を `media` ブランチへ上げる（PR作成の必須手順ではない） |

Stage1〜Stage4 の主経路は `TerrainPieces.pieces` を個別配置SSOTとして使う。`stage-designer --stage N` で素材種類・`x` / `y`・`role`・`collision`・反転を個別調整できる。Stage1 の Guide自動充填は通路側surfaceと少し重なる有機素材の外側2層を生成する。編集ビューはステージ上端（y=0）と下端（y=540）を常時表示する。Ctrl+クリックまたは空白ドラッグで複数選択し、Ctrl+ドラッグまたはCtrl+Dで複製、Delで一括削除できる。Ctrl+[ / Ctrl+]は通常TerrainPieceと破壊可能terrain eventをまたいで1段背面/前面へ、Shift併用で最背面/最前面へ移動する。BossGateとBoss出現もStage1/2イベントパレットから再配置できる。Boss用fallbackの `TerrainStrip` と、破壊可能な `world_events` は従来どおり残す。

### 設計原則（SSOT）
マスターデータは1箇所だけに定義し、他はそこから導出します（反映漏れ防止）。詳細と機能追加チェックリストは **[CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md)**（共有ソースは `docs/agent_guide_shared.md`）を参照。自動フック登録は既定で空です。変更に応じて `tools/run.py docs` で再生成し、`docs-check` / `check`、関連テスト、CIで整合性を確認します。画像添付やHTML化は必要なときだけ行います。

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
