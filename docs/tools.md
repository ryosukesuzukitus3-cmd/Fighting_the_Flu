# 補助ツール 使い方ガイド

Python 3.11以上を使い、作業するworktreeのルート（`main.py` と同じ場所）で実行する。
ゲームの初期操作は [README](../README.md#操作方法) を参照。通常操作のキーは初期設定を記載しており、設定画面で変更した場合はそのキーを使う。

## A. 戦闘中の強化・持駒・停止

- Wアイテムは自機と、同行している先輩にそれぞれ強化在庫を与える。各新規プレイの初回取得では自動で戦闘が止まり、2段の選択画面を開く。以後は在庫があるときにウェポン選択キー（初期値V）で開く。
- メイン武器の通常強化はWIDE+まで。MEDICは最終決戦の先輩復帰時に解禁する3方向の貫通弾。
- レーザーは装備後に設定のレーザーキー（初期値Space）で使用する。HUDのレーザー・強化・持駒のキー表示も現在の設定に従う。
- 持駒キー（初期値B）は歩・金・龍を取得順に消費し、追尾弾を発射する。全画面弾消しではない。金・龍には短い無敵時間がある。
- ポーズ中はコンボ時間も停止する。強化・停止型会話中にも持駒を消費しない。
- ゲームオーバーの継続は有給を1日減らして現在章から再開し、スコアを維持する。武器・先輩・物語は章開始時、HPは全回復。「最初からやり直す」は第一章から新規開始し、有給・スコア・強化などを初期化する。有給0日では継続できない。

---

## B. デバッグモード（ゲーム内）

ソースを最適化なしで起動（`python main.py`）した開発時だけ、以下のキーが使える。
`python -O main.py` と配布EXEではデバッグ機能が除去される。

| キー | 効果 |
|------|------|
| `F1` | 無敵トグル（情報表示中は右上に `INV:ON` 表示） |
| `F2` | ウェポンアイテムを自機前方にドロップ |
| `F3` | 現在の状態をターミナルに出力（HP・武器・コンボ・IntroState 等） |
| `F4` | 押している間、ステージ中の進行を早送り（右上オーバーレイに `FFx6` 表示） |
| `F5` | 現在のウェーブをスキップして次ウェーブを即スポーン（ボス演出中は無効） |
| `F6` | 残りウェーブを全スキップしてボスを即スポーン（ALERT なし） |
| `F7` | ウェポン状態を最大化 |
| `F8` | デバッグ情報の表示・非表示を切り替える |
| `Ctrl+1` ～ `Ctrl+9` | 登録済みステージへ即ワープ（会話シーンなどでも有効） |

右上のデバッグ情報（ステージ・HP・武器レベル・コンボ状態など）は通常ステージでは既定で非表示。F8で切り替える。stage 99では最初から表示する。

### タイトル画面のデバッグジャンプ

タイトル画面では以下のキーで各画面へ直接ジャンプできる（`python -O` で除去）。

| キー | 効果 |
|------|------|
| `D` | デバッグステージ（stage 99）へワープ |
| `C` | スタッフロール（エンドロール）へ直行 |
| `V` | ラスボス撃破後のクリア画面へ直行（そのまま `ENTER` でスタッフロールへ続く。ハイスコア・プレイログは記録しない） |

### デバッグステージのエフェクト確認

タイトル画面で `D` を押して stage 99 へ入り、`Tab` でデバッグパネルを開く。
左右キーで `FX` タブへ移動し、上下キーで素材を選んで `Enter` を押すと、
12本の動画由来エフェクトを1つずつその場で再生できる。通常プレイでの発火条件を
待たずに、透過・大きさ・コマ送りを確認するためのギャラリーとして使う。
`Enter` で再生した後に `Tab` でパネルを閉じると、画面全体を遮らず確認できる。

---

## F-2. コンボカウンター（ゲーム内）

追加機能のため操作は不要。ゲームプレイ中に自動で動作する。

- 撃破ごとにコンボ数+1
- 敵（雑魚・ボス）に攻撃が命中している間はタイマー（`COMBO_WINDOW`=3秒）がリフレッシュされ、コンボ継続
- **3連続**からコンボ表示開始
- コンボ数に応じてスコアに倍率がかかる

| コンボ数 | スコア倍率 |
|---------|-----------|
| 3〜4 | ×1（表示のみ） |
| 5〜9 | ×2 |
| 10〜19 | ×4 |
| 20以上 | ×8 |

命中が途切れて `COMBO_WINDOW` 秒経過するとタイムアウトし「COMBO BREAK」が表示される。
定数は `src/scenes/game/config.py` の `COMBO_WINDOW` / `COMBO_MIN` で調整可能。

---

## C. 弾幕パターン プレビューツール

```bash
python tools/preview_boss.py [オプション]
```

### オプション

| オプション | 説明 |
|-----------|------|
| `--stage N` | ステージ番号 1〜4（省略時: 4） |
| `--pattern NAME` | 表示するパターン名（省略時: フェーズ追従） |
| `--all` | 全パターンを `AUTO_CYCLE` 秒（4秒）ごとに自動切替 |
| `--list` | 利用可能なパターン一覧を表示して終了 |

### 操作

| キー | 効果 |
|------|------|
| マウス移動 | プレイヤー位置が追従（ボスの狙い打ち方向が変わる） |
| `SPACE` | 次のパターンへ手動切替 |
| `R` | 現在のパターンをリセット（弾をクリア） |
| `[` | 射撃間隔を 0.1秒 延長 |
| `]` | 射撃間隔を 0.1秒 短縮 |
| `ESC` | 終了 |

### 使用例

```bash
# Stage 4 の chaos パターンをプレビュー
python tools/preview_boss.py --stage 4 --pattern chaos

# Stage 2 を実際のフェーズ遷移通りに再現
python tools/preview_boss.py --stage 2

# 全パターンを 4 秒ごとに自動切替
python tools/preview_boss.py --all

# パターン一覧表示
python tools/preview_boss.py --list
```

### 利用可能なパターン

`fan5` / `fan7` / `aimed` / `dbl_aimed` / `ring8` / `ring12` / `ring16` /
`aimring6` / `aimring8` / `scatter` / `cross` / `spiral` / `vortex2` / `vortex3` /
`chaos` / `burst3` / `wall_gap` / `fever_lunge` / `mega_laser` / `drone_cross` /
`rock_fall` / `shogi_file` / `dash_knives` / `curtain`

---

## C-1. ボスコンセプト静止画キャプチャ

```bash
python tools/capture_boss_concepts.py
```

Boss2 の装甲/弱点露出、Boss3 の要塞シールド、Form2 の高速形態、Form3 の鈍重オーラを
`captures/boss*_*.png` に出力する。見た目調整の確認用。

---

## C-2. 任意状態の画面キャプチャ

本物の `GameScene` をヘッドレス（`SDL_VIDEODRIVER=dummy`）で駆動し、実プレイ画面・HUD・UI・ボス演出・
弾幕をそのまま PNG 保存する汎用ツール。ステージ・武器・ボスフォームなどを指定して任意の瞬間を撮れる。

```bash
python tools/capture.py [オプション]
```

### オプション

| オプション | 説明 |
|-----------|------|
| `--stage N` | ステージID（既定1） |
| `--boss` | ボス戦へ即移行（演出を自動スキップして戦闘状態に） |
| `--form {1,2,3}` | ボスのフォーム（ステージ4＝頑固王サワグチで有効） |
| `--pattern NAME` | 指定したボス攻撃だけを固定再生（`--boss` と併用） |
| `--main / --laser / --homing / --speed / --magnet N` | 武器強化レベル |
| `--barrier` | バリア付与 |
| `--frames N` | 最初の撮影までに進めるフレーム数（既定60） |
| `--shots N` / `--interval N` | 連番の枚数とフレーム間隔（既定 1 / 12） |
| `--hold fire,up,...` | 保持する操作名（fire/laser/up/down/left/right、既定fire）。ゲームの現在のキー設定へ解決する |
| `--invincible` / `--no-invincible` | 撮影中の死亡・点滅を防ぐ（既定 ON） |
| `--dt SEC` | 1フレームの経過秒（既定 1/60） |
| `--out PATH` | 出力先プレフィックス（既定 `captures/shot`） |

### 使用例

```bash
# ステージ4 ボス第3形態を武器フル強化で撮影
python tools/capture.py --stage 4 --boss --form 3 --main 5 --laser 6 --homing 7

# 藤井の巨大破壊光線だけを固定し、4フレーム間隔で連番撮影
python tools/capture.py --stage 4 --boss --form 3 --pattern mega_beam --shots 30 --interval 4

# 弾幕の連番（8フレームおきに5枚）
python tools/capture.py --stage 2 --shots 5 --interval 8 --out captures/seq

# ステージ1 の章バナーを撮る
python tools/capture.py --stage 1 --frames 120 --out captures/stage1_intro
```

出力PNGで変更した場面を確認できる。capture/clipの操作保持は各Gameの設定キーへ変換し、保持しないフレームでは解除する。画像のPR添付やbefore/after一式の作成は必須ではない。
連続アニメーションの体感は静止画では確認しきれないので、その場合は `--shots` の連番で複数フレームを並べる。

---

## C-3. 実画面プレイ用の入力補助

デスクトップ操作ツールからキー入力が届かない場合に、通常ウィンドウで起動したゲームへ
pygame の押下・解放イベントを渡す。ゲームの進行・描画には通常の `Game.run()` を使う。

```powershell
.venv\Scripts\python tools\run.py playtest
```

起動したプロセスの標準入力へ、JSONを1行ずつ送る。PowerShellの新しいコマンドとして
実行するものではない。キー名は pygame の名前（`return`、`space`、`z`、`right` など）で、
`enter` も使える。ゲーム内設定を変更している場合は、その設定の実キーを指定する。

| 入力例 | 操作 |
|---|---|
| `{"press":["return"],"seconds":0.15}` | 決定キーを押して解放 |
| `{"press":["z","right"],"seconds":1.0}` | 射撃しながら右へ移動 |
| `{"release":["right"]}` | 右だけを解放（他の保持キーは継続） |
| `{"release_all":true}` | 補助ツールの全保持キーを解放 |
| `{"status":true}` | 現在のシーン・保持キー・自機の状態を取得 |
| `{"capture":"movement"}` | `captures/playtest/` に現在画面をPNG保存 |
| `{"quit":true}` | 保持キーを解放してゲームを終了 |

保持時間は0.05〜5秒。同じキーを再指定すると期限を更新する。標準入力が閉じられた場合も
全キーを解放して終了する。不正な入力はエラーを返し、ゲームは継続する。
状態はシーン切替と保持期限の処理後、入力イベント処理・ゲーム更新前に取得する。
自機の射撃状態などは前回更新時の値で、保持キーとは1フレームずれることがある。
画像は直近の描画結果なので、シーン切替直後には状態と画像のシーンが異なることがある。

このツールは無敵化・自動会話送り・ステージ直行・時間変更を行わない。
確認結果は「操作補助を介した実画面検証」として扱い、OS経由のキー入力が直った証拠にはしない。
通常の起動・配布版には、この入力経路は追加されない。

---

## A-1. バランスシート

pygame をウィンドウなしで起動して数値テーブルを出力する。

```bash
python tools/balance_sheet.py [--section SECTION]
```

### オプション

| `--section` | 出力内容 |
|-------------|---------|
| `all`（省略時） | 全テーブル |
| `enemy` | 敵 HP / Speed テーブル |
| `weapon` | レーザー・ホーミング・メインウェポン DPS テーブル |
| `boss` | ボス HP と理論撃破時間テーブル |

### 出力例

```
=== ENEMY HP TABLE ===
+------------------+---------+---------+----------------------------+
| Enemy            | BaseHP  | EnhHP   | 備考                       |
+------------------+---------+---------+----------------------------+
| EnemyVirus       | 1       | 3       | 直進                       |
| EnemyTakeshi     | 2       | 6       | sin波                      |
| EnemyBroly       | 5       | 14      | 突進(charge:520→650)       |
| EnemyPachemon    | 3       | 8       | ジグザグ+狙撃              |
| EnemyBilly       | 18      | 18      | 高HP・鈍足・確定W(強化なし)|
+------------------+---------+---------+----------------------------+

=== ENEMY SPEED TABLE (px/s) ===
+------------------+------------+------------+
| Enemy            | BaseSpd    | EnhSpd     |
...

=== BOSS KILL TIME (理論値) ===
             L1       L2       L3    ...
  S4 Form1   15.0s    ...
  S4 Form2   18.0s    ...
```

強化個体（`enhanced=true`）は赤いグロウエフェクトで識別できる。
ステージJSONの各ウェーブに `"enhanced": true` を付けることで強化個体として出現する。

---

## D. プレイログ分析ツール

`data/playlogs/session_*.jsonl` を読み込んで統計を出力する。

```bash
python tools/analyze_log.py [オプション]
```

### オプション

| オプション | 説明 |
|-----------|------|
| `--since YYYYMMDD` | 指定日以降のログのみ対象 |
| `--graph` | matplotlib でグラフを表示（要 `pip install matplotlib`） |
| `--export csv` | `data/playlog_export.csv` にエクスポート |

### テキスト出力内容

1. **SURVIVAL STATS** — ステージ別 到達率・クリア率
2. **DEATH HOTSPOT** — ステージ内の死亡タイミング分布（10秒ゾーン別）
3. **BOSS KILL TIME** — ボス撃破タイムの avg / med / min / max とボス生存時間
4. **WEAPON STATE AT DEATH** — 死亡時の武器レベル平均値と未取得数
5. **WEAPON STATE AT BOSS KILL** — ボス撃破時の武器状態（新ログから記録開始）

### グラフ表示（`--graph`）

- ステージ到達・クリア率の棒グラフ
- 死亡タイミングのヒストグラム（ステージ別）
- ボス撃破タイムの箱ひげ図

### 使用例

```bash
# 全ログのサマリーを表示
python tools/analyze_log.py

# 3/24 以降のログのみ
python tools/analyze_log.py --since 20260324

# グラフも合わせて表示
python tools/analyze_log.py --graph

# CSV にエクスポート
python tools/analyze_log.py --export csv
```

### ログデータについて

- 保存場所: 開発時は `data/playlogs/session_YYYYMMDD.jsonl`、Windows配布版は `%APPDATA%\InfuruToNoShito\playlogs\session_YYYYMMDD.jsonl`（1行1ラン）。実際の保存先は `user_data_dir()` に従う
- `boss_killed` イベントへの weapon snapshot は今回のバージョンから記録開始。
  旧ログは WEAPON STATE AT BOSS KILL セクションが空になる。


---

## 配布EXEの実行検査

`game.spec` でビルドしたEXEを対象にする。Pythonからのソース起動だけでは、この検査の代わりにならない。

```powershell
.venv/Scripts/python tools/run_packaged_smoke.py

# 別の配布物とレポート保存先を指定する例
.venv/Scripts/python tools/run_packaged_smoke.py --exe dist/InfuruToNoShito/InfuruToNoShito.exe --report build-reports/packaged-smoke.json
```

このツールはリポジトリ外の一時フォルダを作ってEXEを起動し、全章の地形・マスク読込、初期化・描画、次章判定、設定・ハイスコア・プレイログの保存と再読込を確認する。
ユーザーデータも別の一時領域に隔離し、通常のプレイヤー保存データを変更しない。
既定のレポートは `build-reports/packaged-smoke.json`。失敗はプロセス終了コードとJSONの両方で判定する。
検査はヘッドレスであり、実ウインドウの入力・音・全編クリアは別途確認する。

---

## 開発用の任意チェック・HTMLレビュー

`.codex/hooks.json` と `.claude/settings.json` の自動フック登録は空にしている。
編集のたびのHTMLダイアログ、API呼び出し、ターン終了時の生成・停止は行わない。
整合性は `tools/run.py docs-check` / `check` と関連テスト、CIで確認する。

既存の `check_sync.py` は手動ツールとして使える。実行したスクリプトのあるworktreeを検査し、
別の `CLAUDE_PROJECT_DIR` や実行時フォルダでは対象を変更しない。Gitや検査の失敗は診断と終了コード2を返す。

```powershell
# 文書生成差分と整合性を検査する。書き換えは行わない
.venv/Scripts/python .codex/hooks/check_sync.py

# 明示的に生成してから検査する
.venv/Scripts/python .codex/hooks/check_sync.py --write

# 監視対象の作業差分がない場合は省略する
.venv/Scripts/python .codex/hooks/check_sync.py --changed-only
```

`.claude/hooks/check_sync.py` も同じオプションを持つ。
どちらもホストアプリのフック対応状況には依存せず、手動実行できる。

MarkdownのローカルHTML化も任意。ファイルを明示した場合だけ生成し、既定ではブラウザやAPIを呼ばない。

```powershell
.venv/Scripts/python .codex/hooks/md_to_html.py --file docs/design.md
.venv/Scripts/python .codex/hooks/md_to_html.py --file docs/design.md --open
```

出力先は同じworktreeの `.html/`。失敗はstderrと非ゼロの終了コードで確認できる。
`.claude/hooks/md_to_html.py` も同じ使い方。
`--mode fancy` は有料APIを使う明示オプションで、追加依存 `anthropic` と環境変数 `FLU_HTML_MODEL` に利用するモデルの指定が必要。
モデルを自動選択しない。通常のplainモードにはAPIキーも追加依存も不要。

`tools/run.py pr-media` / `pr-html` / `pr-report` はリモートへ公開する別の任意ツールであり、
ローカルHTML化だけではアップロードしない。PRに画像やHTMLを付けることは必須ではない。
