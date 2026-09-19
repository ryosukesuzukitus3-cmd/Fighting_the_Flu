# 補助ツール 使い方ガイド

Python 3.11以上を使い、作業するworktreeのルート（`main.py` と同じ場所）で実行する。
ゲームの初期操作は [README](../README.md#操作方法) を参照。通常操作のキーは初期設定を記載しており、設定画面で変更した場合はそのキーを使う。

## A. 戦闘中の強化・停止

- Wアイテムは自機と、同行している先輩にそれぞれ強化在庫を与える。各新規プレイの初回取得では自動で戦闘が止まり、2段の選択画面を開く。以後は在庫があるときにウェポン選択キー（初期値V）で開く。
- メイン武器の通常強化はWIDE+まで。MEDICは最終決戦の先輩復帰時に解禁する3方向の貫通弾。
- レーザーは装備後に設定のレーザーキー（初期値Space）で使用する。HUDのレーザー・強化のキー表示も現在の設定に従う。
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
| `F6` | 残りウェーブを全スキップし、ALERT → 通常の入場演出・会話を経てボス戦へ進む（中ボスが残っている場合は撃破待ち） |
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

## C-4. 時間を止めて操作する検証モード

反応待ちの間に敵や弾が進まない、開発専用の入力口。通常ゲームと同じ `Game.step` を毎フレーム呼び、タイトルから会話・強化・継続・エンディングまで通常の入力で進める。別のシミュレーターではない。

```powershell
.venv\Scripts\python tools\run.py agent-playtest --output captures/agent-session --seed 17
```

新規または空の出力フォルダーを指定する。既定は画面・音声とも非表示で、実際のキーボードや他のアプリへ入力しない。標準入力から1行1件のJSONを送り、標準出力から結果を受け取る。

| 入力 | 動作 |
|---|---|
| `{"step":12,"actions":["fire","move_right"]}` | その操作集合を保持し、最大12フレーム（0.2秒）進める |
| `{"step":1,"actions":[]}` | 全キーを離し、1フレーム進める |
| `{"tap":"ui_accept"}` | 決定を押して離す。既に保持中なら先に離す |
| `{"observe":true}` | 最後に完了したフレームの状態・画像を返す。時間・乱数を進めない |
| `{"capture":"boss-start"}` | 同じフレームを名前付きPNGへ保存する |
| `{"quit":true}` | キー保持を解除して終了する。入力終了（EOF）でも終了 |

`step` は1〜600フレーム。場面・会話ページ・ポーズなどが変わると早めに停止するため、応答の `advanced` を確認する。場面遷移はゲーム本来の次フレームで反映される。未反映の遷移があるときは、空操作で1フレーム進める。

`actions` は追加操作ではなく**保持する全操作の集合**。同じ集合を続けて送っても押し直しにならない。レーザーは `laser` を含む間だけ発射し、集合から外すと停止・冷却する。移動・射撃等は設定の割当を使い、メニュー固定矢印は `menu_up/down/left/right`、その他 `escape` / `tab` を使う。

応答の `frame` と `elapsed` は保存画像と同じ時点。`latest.png` と `observation.json` は直近の観測、`capture-名前.png` は保存用。未表示の会話や総ページ数は通常観測に含めない。`--diagnostic` を明示すると敵の内部HP等も返す。この条件での判断を人間の通常プレイと混同しない。

出力先の `user-data/` に設定・スコア・プレイログを隔離し、通常データを読み書きしない。無敵、装備付与、強制撃破、デバッグ直行は入力APIに含めず、ゲームのデバッグキーも無効にする。

### 再現と等速再生

```powershell
# 同じバージョン・実行環境で入力を再実行し、各操作後の状態と画像を照合
.venv\Scripts\python tools\run.py agent-playtest --replay captures/agent-session --output captures/agent-replay
# ゲーム専用ウインドウを開き、60FPSで入力履歴を再生
.venv\Scripts\python tools\run.py agent-playtest --replay captures/agent-session --output captures/agent-visible --visible
```

`session.json` はseed・コミット・未コミット変更の有無・環境・観測条件を、`actions.jsonl` は操作と照合値を保存する。コード・素材・フォント・ライブラリが違うと再生の一致は保証しない。思考・通信の待ち時間は履歴に含めず、等速再生で判断する。

このモードで確認できるのは、実ルールに従う攻略、進行の詰まり、説明との整合、入力や場面遷移の不具合。人間の反射速度での難易度や音楽との同期は、別途等速で確認する。

### 診断用の自動プレイ

```powershell
.venv\Scripts\python tools\run.py agent-campaign --output captures/campaign-seed1 --seed 1 --interval 12
```

現在の敵・弾・地形・予告等を読み、12フレーム（0.2秒）以上の間隔で通常入力を選ぶ。通常のタイトルから出発し、自然に取得したWで強化、有給でコンティニューする。ゲーム状態の書換えによる無敵・回復・装備付与・強制勝利は行わない。`rule_overrides: []` はルール改変なしを表し、内部状態を読む診断条件は別に記録する。

- `campaign-summary.json`: 到達場面、被弾・死亡、装備変更、観測した会話、終了理由。
- `campaign.jsonl`: 各判断の入力・HP・体温・ボス状態。被弾時には原因候補と画像を保存する。
- `actions.jsonl` / `session.json`: 手動モードと共通の入力再生記録。実装のハッシュも診断側で保存する。
- 停止するときは出力先に `stop.request` という空ファイルを作る。次の判断で記録を保存して終了する。

`victory_reached` はクリア画面到達、`completed` は勝利後のスタッフロールを経てタイトルへ戻ったことを表す。最後まで到達した場合だけ終了コード0。時間上限・有給切れ・停止・例外を、全章完了として報告しない。

この自動操作は内部座標を読むため、人間の平均的な上手さ・反応速度を再現するものではない。勝敗だけで難易度を変えず、被弾状況や予告から回避できる時間を別に再現して判断する。


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


## C-5. アクションを比較する検証場

`combat-lab` は実ゲームのボスを指定装備で比較する。既定は空のアリーナ。
`--arena authored` は本編のボス配置座標から、地形付きのボス部屋を用意する。
`--speed 0..3` で移動速度の強化も指定できる。
準備した状態は `session.json` の `scenario_setup` へ記録する。
その後は通常のキー入力・HP・当たり判定で進み、試行中の回復や強制撃破は行わない。
通常キャンペーンや、その入力履歴の再生とは区別する。
自動キャンペーン・検証場では各入力後のPNG上書きだけを省く。全フレームのゲーム更新・描画・乱数・画像ハッシュは通常どおりで、場面切替や被弾、明示的なcaptureでは画像を保存する。

```powershell
.venv\Scripts\python tools/run.py combat-lab --stage 2 --main 4 --laser 3 --output captures/counter
.venv\Scripts\python tools/run.py combat-lab --stage 2 --main 4 --laser 3 --policy hold --output captures/hold
.venv\Scripts\python tools/run.py stage-report --stage 3 --output captures/stage3.json
```

- `adaptive`: 予告を回避し、ブロリーの隙へレーザーを使う。子機を優先して狙う。
- `hold`: 同じ回避方針で通常弾とレーザーを押し続ける。
- `main`: 同じ回避方針で通常弾・装備済み追尾弾を使う。
- `reckless`: 移動せず両攻撃を押し続ける。危険な射線の対照実験。
- `trial.json` / `samples.json`: 戦闘時間、被弾、過熱、攻撃段階、入力を保存する。被弾時には移動候補の評価も記録する。
- 判断は指定間隔ごと。移動キーを途中で離す時刻も判断時に決め、短い移動のために反応速度を上げない。吸引は本編と共通の計算で予測する。
- `capture-cue-*.png`: 予告・攻撃・反撃の切り替わりを保存する。
- `source-fingerprints.json`: ゲーム・操作ツール・章JSONのSHA-256。未コミットの試行も版を特定する。
- 出力先に `stop.request` を置くと記録を保存して停止する。撃破以外の終了は終了コード1。
- 戦闘時間は入力区間の開始時モードで集計するため、区切りには判断間隔分の誤差がある。

`stage-report` は章JSONを800pxごとの敵数・確定強化報酬と座標順のイベントに整理する。
`--window` で区間幅を指定できる。人向け設計ツールと同じJSONを読み、別の配置データを作らない。
集計は配置数であり、同時に生きている敵数や通路の安全性ではない。実プレイで裏付ける。
