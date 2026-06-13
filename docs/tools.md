# 補助ツール 使い方ガイド

プロジェクトルート（`main.py` と同じ場所）で実行する。

---

## B. デバッグモード（ゲーム内）

ゲームを **通常起動**（`python main.py`）した状態で以下のキーが使える。
`python -O main.py` で起動すると全デバッグ機能が除去される。

| キー | 効果 |
|------|------|
| `F1` | 無敵トグル（ON 中は右上オーバーレイに `INV:ON` 表示） |
| `F2` | ウェポンアイテムを自機前方にドロップ |
| `F3` | 現在の状態をターミナルに出力（HP・武器・コンボ・IntroState 等） |
| `F5` | 現在のウェーブをスキップして次ウェーブを即スポーン（ボス演出中は無効） |
| `F6` | 残りウェーブを全スキップしてボスを即スポーン（ALERT なし） |
| `Ctrl+1` ～ `Ctrl+4` | 指定ステージへ即ワープ |

右上にデバッグオーバーレイが表示される（ステージ・HP・武器レベル・コンボ状態など）。

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

- 保存場所: `data/playlogs/session_YYYYMMDD.jsonl`（1行1ラン）
- `boss_killed` イベントへの weapon snapshot は今回のバージョンから記録開始。
  旧ログは WEAPON STATE AT BOSS KILL セクションが空になる。
