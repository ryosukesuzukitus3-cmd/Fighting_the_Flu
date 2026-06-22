# Fighting the Flu — ゲーム設計書

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [要件定義](#2-要件定義)
3. [技術方針](#3-技術方針)
4. [アーキテクチャ](#4-アーキテクチャ)
5. [クラス設計](#5-クラス設計)
6. [フォルダ構成](#6-フォルダ構成)
7. [ステージデータ仕様](#7-ステージデータ仕様)
8. [データ保存仕様](#8-データ保存仕様)
9. [ビルド方法](#9-ビルド方法)
10. [サウンド・演出仕様（実装リファレンス）](#10-サウンド演出仕様実装リファレンス)

---

## 1. プロジェクト概要

| 項目 | 内容 |
|---|---|
| タイトル | インフルとの死闘 |
| ジャンル | 横スクロールシューティング |
| 参考作品 | グラディウス・R-TYPE系 |
| 開発言語 | Python 3.10+ |
| ゲームライブラリ | Pygame-CE |

---

## 2. 要件定義

### 2.1 ゲームの流れ

```
タイトル画面
    → チュートリアル（初回のみ）
    → プロローグ / ステージイントロ（各ステージ前のモノローグ）
        → ゲーム開始
            → ステージ進行（全4ステージ）
                → ボス戦
                → ステージクリア
            → エピローグ
        → ゲームクリア or ゲームオーバー
    → ハイスコア画面
```

### 2.2 プレイヤー

- 上下左右の移動（画面内制限あり）
- HPゲージ（最大100の多段階・残機制）。被弾源ごとに被ダメージ量が異なる（`balance.py` の `PLAYER_DMG_*`：雑魚接触15 / 敵弾10 / ボス接触25 / 地形8）
- 被弾でHP減少、0でゲームオーバー
- 被弾後は一定時間無敵（点滅で表現）
- 地形（壁・岩・デブリ）に接触してもダメージ。弾は地形で跳ね返り、レーザーは地形で遮られる。破壊可能地形は一定ダメージで壊れてアイテムを落とすことがある
- HUDにHPゲージ・スコア・ウェポン状態・ウェポン在庫を表示

### 2.3 武器システム（グラディウス式スロット選択）

WeaponItem を取得すると**在庫**に加算され、任意のタイミングで **V キー**を押すとウェポン選択画面が開く
（1 回押下につき 1 選択・在庫を 1 消費）。レーザーとホーミングは**併用可能**（択一ではない）。
レーザー発射は **SPACE キー**。なお HP ゲージ制移行に伴い、被弾時の自動ダウングレードは廃止。

#### メインウェポン（順に強化）

<!-- AUTOGEN:weapon_main START -->
| レベル | 種別 | 効果 |
|---|---|---|
| 0 | single | 正面に弾1発（発射間隔0.25s） |
| 1 | rapid1 | 連射（発射間隔0.15s） |
| 2 | rapid2 | 超連射（発射間隔0.12s） |
| 3 | wide1 | 正面＋斜め 2本発射 |
| 4 | wide2 | 正面＋斜め 3本発射 |
| 5 | medic | 回復弾追加（メディックモード） |
<!-- AUTOGEN:weapon_main END -->

#### アドオンスロット（独立管理）

| スロット | 内容 |
|---|---|
| speed_level | 弾速UP（+20%/段、最大5段＝2倍） |
| laser_level | チャージレーザー（0=なし、1〜6段階で幅・威力・冷却が変化） |
| homing_level | ホーミング弾追加（0=なし、1〜7段階） |
| magnet_level | アイテム引き寄せ（0=なし、1=弱 / 2=中 / 3=強） |
| has_barrier | バリア（弾を1発相殺） |

### 2.4 敵

- 複数の敵が同時出現
- 敵ごとに異なるHP・移動パターン
- 隊列を組んだ編隊出現
- 敵も弾を撃つ（反撃あり）
- ステージ最後にボス（高HP・フェーズ制の特殊攻撃）
- ステージが進むほどHP・速度がスケーリング（`balance.py` で管理）

<!-- AUTOGEN:enemies START -->
| 敵種別 | 移動パターン | 備考 |
|---|---|---|
| EnemyVirus | 直進 | — |
| EnemyTakeshi | 波状移動 | — |
| EnemyBroly | プレイヤーへ突進 | — |
| EnemyPachemon | ジグザグ＋狙い撃ち | 中強度、弾を撃つ |
| EnemyCoughSprayer | 右前方に滞空（hover/sweep/zigzagを巡回） | 大型中ボス（約2倍）。扇・リング・螺旋・連射を時間で巡回射撃 |
| EnemySporeSplitter | 右前方に滞空（drift/wide/quiverを巡回） | 大型中ボス（約2倍）。胞子弾を吐き、撃破で胞子ポッドに分裂 |
| EnemySporePod | 分裂時の慣性で飛散 | 胞子分裂型の撃破後に残る二次目標 |
| EnemyBilly | 低速直進 | HP高い、撃破必ずWeaponItemドロップ |
| EnemyTurret | 固定（地形にスクロール追従） | 自機を狙い撃ち、SE_ENEMY_SHOT |
| EnemyCrawler | 地形表面を走行 | 上下地形に吸着して移動しながら狙い撃ち |
| EnemyDebrisLarge | 回転しながら直進 | 撃破時に小デブリへ分裂、接触ダメージ |
| EnemyDebrisShard | 分裂時の慣性で飛散 | 大型デブリ破壊後に残る二次目標 |
| Boss | フェーズ制（HPに応じて攻撃パターン変化） | ステージごとに固有セリフ・演出 |
<!-- AUTOGEN:enemies END -->

#### ボスギミック（ステージ別の特色）

弾幕に加え、ボスごとに異なるギミックと移動コンセプトを持つ（`boss.py` の `_GIMMICKS` / `_MOVE_STYLES` / `_PHASE_CONFIGS`）:

| ステージ/形態 | ギミック | 内容 |
|---|---|---|
| Boss1 | shield | 前進突進＋シールド。距離を詰めてから扇弾/狙撃を重ね、解除中が攻撃猶予 |
| Boss2 | weakpoint | 強化済みの重量級レーザー砲台。移動は鈍いが耐久とレーザー圧が高く、装甲を割るか巨大レーザー後の後隙で弱点露出 |
| Boss3 | turrets | AI生成素材を本体/3子機に分割した大型要塞。シールド子機が健在中は本体ダメージ無効、奥の子機はレーザーでのみ破壊可能、全滅でスタン（被ダメ増） |
| Boss4 第一形態 | shield | 将棋盤のマスをゆっくり渡る位置替え＋将棋駒列弾。シールド解除中に攻める |
| Boss4 第二形態 | weakpoint | 赤眼ダッシュ形態。急接近と高速刺し込み弾、装甲破壊で弱点露出 |
| Boss4 第三形態 | （専用演出） | 強化済みの鈍重な巨大影。画面全域弾幕、落石、反芻再生・フェイクアウト等のスクリプト演出 |

### 2.5 アイテム

- WeaponItem は取得すると在庫に加算され、V キーで選択UIを開いて消費（1回1選択）
- HealItem は取得即適用
- 通常ステージでの雑魚撃破時にもドロップあり（確率制）

<!-- AUTOGEN:items START -->
| 種別 | 効果 |
|---|---|
| WeaponItem | 武器スロット選択 |
| HealItem | HP回復（+30） |
<!-- AUTOGEN:items END -->

### 2.6 ステージ

- 全4ステージ構成
- ステージごとに敵の種類・出現パターン・BGMが変化
- ステージクリア条件: ボス撃破
- ステージ開始時: 直前の物語ビート（CutsceneScene／story_flow）→ ラウンドSE → ゲーム開始

### 2.7 スコア・ランキング

- 敵撃破でスコア加算
- コンボシステム: 撃破で倍率UP。敵に攻撃が命中している間はタイマー（COMBO_WINDOW秒）が継続し、命中が途切れると終了
- ハイスコアをローカルにJSON保存
- プレイ終了後にランキング画面を表示（10位まで）

### 2.8 演出

- 爆発アニメーション（パーティクル）
- 画面シェイク（被弾・爆発・ボス登場・レーザー発射時）
- スロー演出（ボス撃破時：通常0.35倍、ラスボス0.18倍）
- BGM: ステージごとに切替
- SE: 発射・爆発・アイテム取得・ボイス等
- 横スクロール背景（視差スクロール対応）
- タイプライター演出（ボスセリフ・イントロ・エピローグ）

### 2.9 UI / UX

- タイトル画面
- チュートリアル（初回起動時）
- ステージイントロ（各ステージ前のモノローグ）
- ポーズ機能（Xキー）
- 設定画面（音量調整）
- ゲームオーバー画面
- エピローグ（3ページ、タイプライター）
- ゲームクリア画面
- ハイスコア画面

---

## 3. 技術方針

### 3.1 ライブラリ

| 項目 | 選択 | 理由 |
|---|---|---|
| 言語 | Python 3.10+ | 既存環境を踏襲 |
| ゲームライブラリ | Pygame-CE | 公式Pygameの後継フォーク、API互換・高速 |
| データ保存 | JSON / JSONL | ハイスコア・設定・ステージ・プレイログの管理 |

Pygame-CEの導入:
```
pip install pygame-ce
```

### 3.2 フレームレートとデルタタイム

フレームレートに依存しない動きを実現するため、すべての速度計算にデルタタイムを使用する。

```python
# NG: フレーム数に依存する
player.x += 5

# OK: 経過時間に依存する
player.x += speed * delta_time  # speed の単位は px/秒
```

### 3.3 座標系

ワールド座標とスクリーン座標を `Camera` クラスで変換する。
ゲームオブジェクトはすべてワールド座標で管理し、描画時のみスクリーン座標に変換する。

### 3.4 衝突判定

`pygame.sprite.Group` を活用し、グループ単位で一括処理する。

```python
# プレイヤー弾 vs 敵 の衝突を一括処理
hits = pygame.sprite.groupcollide(player_bullets, enemies, True, False)
```

### 3.5 エンティティ間通信

エンティティ同士の直接参照を避けるため、イベントバスを導入する。

```python
# Player側（送信）
event_bus.emit("player_hit", damage=1)

# HUD側（受信）
event_bus.on("player_hit", self.update_hp)
```

### 3.6 オブジェクトプール

弾とパーティクルは頻繁に生成・破棄されるため、プールで再利用してパフォーマンスを確保する。

```python
# 弾の取得（新規生成ではなく再利用）
bullet = bullet_pool.acquire()

# 弾の返却（破棄ではなくプールに戻す）
bullet_pool.release(bullet)
```

---

## 4. アーキテクチャ

### 4.1 シーン管理

`Game` クラスがシーンを管理し、シーンの切替を担う。

```
Game（メインループ・シーン管理）
├── TitleScene              タイトル画面
│   └── StatsScene          プレイ統計表示（タイトルから遷移）
├── TutorialScene           チュートリアル
├── PrologueScene           橋渡し（story_flow.start_stage へ委譲）
├── GameScene               メインゲーム（Mixin構成）
│   ├── DebugMixin          デバッグモード（-O フラグで除去）
│   ├── PostBossMixin       ボス撃破後演出・遷移
│   ├── OverlayMixin        ステージバナー・ボス演出
│   ├── UpgradeMixin        ウェポン選択UI（ボス撃破後）
│   └── PauseMixin          ポーズUI（Xキー）
├── StageClearScene         ステージクリア
├── EpilogueScene           エンディング（全クリア後）
├── GameClearScene          ゲームクリア画面
├── GameOverScene           ゲームオーバー
├── HighScoreScene          ハイスコア一覧
└── SettingsScene           設定（音量調整）
```

### 4.2 GameScene の Mixin 構成

`GameScene` は巨大化を防ぐため Mixin で責務を分割する。MRO順:

```python
class GameScene(
    GameSceneDebugMixin,
    GameScenePostBossMixin,
    GameSceneOverlayMixin,
    GameSceneUpgradeMixin,
    GameScenePauseMixin,
    Scene,
):
    ...
```

| Mixin | 責務 |
|---|---|
| DebugMixin | デバッグコマンド（F1〜F6, Ctrl+N: ステージワープ） |
| PostBossMixin | ボス撃破後のスロー・追加爆発・マグネット・セリフ・遷移 |
| OverlayMixin | ステージバナー・ALERT・ボス名・FIGHT!バナー・ボス戦中セリフ |
| UpgradeMixin | ボス撃破後のウェポンスロット選択UI |
| PauseMixin | ポーズメニュー（戻る / 設定 / タイトル） |

### 4.3 シーン間のデータ受け渡し

`Game` クラスが `GameState` dataclass を保持し、シーンはこれを経由してデータを読み書きする。シーン同士の直接参照は禁止。

```python
@dataclass
class GameState:
    score:              int        = 0
    kill_count:         int        = 0
    stage:              int        = 1
    lives:              int        = 3
    carry_hp:           int | None = None   # ボス撃破→StageClear 間のHP引き継ぎ
    carry_weapon:      dict | None = None   # 同上・ウェポン引き継ぎ
    stage_start_weapon: dict | None = None  # コンティニュー用ウェポン記録

    def take_carry(self) -> tuple[int | None, dict | None]:
        """引き継ぎデータを原子的に取り出す（pop相当）"""
```

### 4.4 イベントフロー（被弾の例）

```
Player.update()
    → event_bus.emit("player_hit", damage=1)
        → HUD.update_hp()            HP を画面更新
        → SoundManager.play_se()     SE を再生
        → ParticleSystem.spawn()     爆発エフェクトを生成
        → Player.start_invincible()  無敵時間を開始
```

### 4.5 ユーザーデータパス

`user_data_dir()` がOS別にパスを解決する。開発時は `data/`、インストール版はOSのユーザーデータ領域を使用。

| 環境 | パス |
|---|---|
| 開発（プロジェクト直下が書き込み可能） | `data/` |
| Windows インストール版 | `%APPDATA%\InfuruToNoShito\` |
| macOS インストール版 | `~/Library/Application Support/InfuruToNoShito/` |
| Linux インストール版 | `~/.local/share/InfuruToNoShito/` |

---

## 5. クラス設計

### 5.1 管理系（core / managers）

| クラス | ファイル | 責務 |
|---|---|---|
| `Game` | core/game.py | メインループ・シーン切替・マネージャー初期化 |
| `GameState` | core/game_state.py | シーン間共有の型安全な状態 dataclass |
| `Scene` | core/scene.py | シーンの基底クラス（抽象） |
| `Camera` | core/camera.py | ワールド座標→スクリーン座標の変換・スクロール管理 |
| `EventBus` | core/event_bus.py | イベントの発行と購読 |
| `balance` | core/balance.py | ステージ別HP・速度スケーリング定数 |
| `ENEMY_DEFS`, `ITEM_DEFS`, `stage_ids()` | core/registries.py | 敵/アイテム/ステージのマスターデータ単一定義ソース（SSOT） |
| `make_enemy`, `make_item`, `random_item` | core/factories.py | 敵・アイテム生成の共通ファクトリ |
| `user_data_dir()` | core/user_data.py | OS別ユーザーデータパス解決 |
| `ResourceManager` | managers/resource.py | 画像・音声のロードとキャッシュ（二重ロード防止） |
| `SoundManager` | managers/sound.py | BGM（ストリーミング）・SE（チャンネルベース）再生管理 |
| `InputManager` | managers/input.py | キー入力の状態管理・アクションAPIの提供 |
| `HighScoreManager` | managers/highscore.py | ハイスコアのJSON読み書き |
| `SettingsManager` | managers/settings.py | 設定（音量）のJSON読み書き・遅延保存 |
| `PlayLogger` | managers/playlog.py | プレイログをJSONL形式でローカル保存（バランス調整用） |

### 5.2 ゲームオブジェクト系（entities）

| クラス | ファイル | 責務 |
|---|---|---|
| `Player` | entities/player.py | 移動・HP管理・無敵時間・スプライト描画 |
| `Weapon` | entities/weapon.py | 武器スロット・レベル管理・弾生成・アップ/ダウングレード |
| `Bullet` | entities/bullet.py | 弾の基底クラス |
| `LaserBeam` | entities/laser_beam.py | チャージレーザー（6段階、状態機械、3層描画） |
| `PlayerBullet` | entities/bullets/player_bullet.py | プレイヤーの弾（Normal / Wide / Pierce / Homing） |
| `EnemyBullet` | entities/bullets/enemy_bullet.py | 敵の弾 |
| `Enemy` | entities/enemies/base.py | 敵の基底クラス（HP・移動・弾の発射） |
| `EnemyVirus` | entities/enemies/virus.py | 直進型 |
| `EnemyTakeshi` | entities/enemies/takeshi.py | 波状移動型 |
| `EnemyBroly` | entities/enemies/broly.py | 突進型 |
| `EnemyPachemon` | entities/enemies/pachemon.py | ジグザグ＋狙い撃ち型（中強度） |
| `EnemyBilly` | entities/enemies/billy.py | 低速・高HP・必ずWeaponItemドロップ |
| `Boss` | entities/enemies/boss.py | フェーズ制・特殊攻撃・固有演出 |
| `Item` | entities/items/base.py | アイテムの基底クラス |
| `WeaponItem` | entities/items/weapon_item.py | ウェポン在庫+1（取得後に強化選択UIで消費） |
| `HealItem` | entities/items/heal.py | HP回復 |
| `Particle` | entities/particle.py | 爆発エフェクトの粒子 |
| `ParticleSystem` | entities/particle.py | Particle をまとめて管理 |
| `ScrollingBackground` | entities/background.py | 視差スクロール背景（複数レイヤー） |
| `HUD` | entities/hud.py | HP・スコア・コンボ倍率・ウェポン状態の画面表示 |

### 5.3 ステージ系（stages）

| クラス | ファイル | 責務 |
|---|---|---|
| `Stage` | stages/stage.py | ステージ全体の管理（JSONロード・クリア判定） |
| `EnemySpawner` | stages/spawner.py | ステージJSONに基づく time / world_x イベント管理 |

### 5.4 プール系（core/pools）

| クラス | ファイル | 責務 |
|---|---|---|
| `BulletPool` | core/pools/bullet_pool.py | 弾オブジェクトの再利用プール |
| `ParticlePool` | core/pools/particle_pool.py | パーティクルオブジェクトの再利用プール |

### 5.5 Weapon クラスの詳細

```python
class Weapon:
    main_level:   int   # 0〜5（single/rapid1/rapid2/wide1/wide2/medic）
    speed_level:  int   # 0〜5（+20%/段、最大2倍）
    laser_level:  int   # 0=なし、1〜6
    homing_level: int   # 0=なし、1〜7
    magnet_level: int   # 0=なし、1〜3
    has_barrier:  bool

    def upgrade(self, item_type: str) -> None: ...   # アイテム取得時
    def downgrade(self) -> None: ...                  # 被弾時（1段階降格）
    def get_bullets(self, x, y) -> list[Bullet]: ... # 現在の武器で弾を生成
```

### 5.6 Boss クラスの詳細

ボスはフェーズリストを持ち、HPに応じて攻撃パターンが変化する。

```python
_PHASE_CONFIGS = {
    1: [(1.00, "fan5", 1.7), (0.70, "fever_lunge", 1.25), ...],
    2: [(1.00, "fan7", 1.28), (0.74, "mega_laser", 1.90), ...],
    3: [(1.00, "drone_cross", 1.35), (0.72, "rock_fall", 1.10), ...],
    4: [(1.00, "shogi_file", 1.25), (0.72, "wall_gap", 0.86), ...],
    "4f2": [(1.00, "dash_knives", 0.55), (0.72, "vortex3", 0.36), ...],
    "4f3": [(1.00, "curtain", 0.52), (0.78, "ring16", 0.38), ...],
}
```

ボスの静止画確認は `tools/capture_boss_concepts.py` で `captures/boss*_*.png` に出力できる。
Boss3 の要塞スプライトは built-in 画像生成で作成し、`assets/graphic/boss_matching_zero.png` を原画として保存している。戦闘中は `boss_matching_zero_body.png` と3枚の `boss_matching_zero_drone_*.png` に分割した素材を使い、子機は破壊可能なシールドノードとして本体防御に関わる。奥の子機は本体の陰に隠れている扱いで通常弾を弾き、`LaserBeam` の貫通ダメージでのみ破壊できる。`rock_fall` の落石は地形反射/衝突演出を出さない貫通弾として扱う。

### 5.7 balance.py（ステージ別スケーリング定数）

<!-- AUTOGEN:balance START -->
| ステージ | HPスケール | 速度スケール |
|---|---|---|
| Stage1 | 1.0× | 1.0× |
| Stage2 | 2.0× | 1.3× |
| Stage3 | 3.0× | 1.7× |
| Stage4 | 5.0× | 2.0× |
<!-- AUTOGEN:balance END -->

---

## 6. フォルダ構成

```
/
├── main.py                             エントリーポイント（def main() -> None: Game().run()）
├── pyproject.toml                      PEP517 ビルド設定（エントリポイント: infuru）
├── requirements.txt
├── src/
│   ├── core/
│   │   ├── game.py                     Gameクラス・メインループ・マネージャー初期化
│   │   ├── scene.py                    Scene基底クラス（抽象）
│   │   ├── camera.py                   カメラ（座標変換・スクロール）
│   │   ├── event_bus.py                イベントバス
│   │   ├── constants.py                定数（画面サイズ・FPS・速度等）
│   │   ├── game_state.py               GameState dataclass（シーン間共有状態）
│   │   ├── registries.py               敵・アイテム・ステージIDのSSOT
│   │   ├── factories.py                敵・アイテム生成の共通ファクトリ
│   │   ├── balance.py                  ステージ別難易度スケーリング定数
│   │   ├── user_data.py                OS別ユーザーデータパス解決
│   │   └── pools/
│   │       ├── bullet_pool.py          BulletPool
│   │       └── particle_pool.py        ParticlePool
│   ├── scenes/
│   │   ├── title.py                    タイトル画面
│   │   ├── tutorial_scene.py           チュートリアル（3ページ）
│   │   ├── prologue_scene.py           橋渡し（story_flow へ委譲）
│   │   ├── story_flow.py               物語タイムライン駆動（STORY_BEATS 再生）
│   │   ├── game_scene.py               メインゲーム（Mixin継承）
│   │   ├── stageclear.py               ステージクリア
│   │   ├── epilogue_scene.py           エンディング（3ページ、タイプライター）
│   │   ├── gameclear.py                ゲームクリア画面
│   │   ├── gameover.py                 ゲームオーバー画面
│   │   ├── highscore_scene.py          ハイスコア一覧（10位まで）
│   │   ├── settings_scene.py           設定画面（音量調整）
│   │   └── game/                       GameScene 責務分割 Mixin
│   │       ├── config.py               GameScene 用定数・ユーティリティ
│   │       ├── pause_mixin.py          ポーズUI
│   │       ├── upgrade_mixin.py        ウェポンスロット選択UI
│   │       ├── overlay_mixin.py        ステージバナー・ボス演出
│   │       ├── post_boss_mixin.py      ボス撃破後演出・遷移
│   │       └── debug_mixin.py          デバッグコマンド（-O で除去）
│   ├── entities/
│   │   ├── player.py                   Player
│   │   ├── weapon.py                   Weapon
│   │   ├── bullet.py                   Bullet 基底クラス
│   │   ├── laser_beam.py               LaserBeam（状態機械・6段階・3層描画）
│   │   ├── background.py               ScrollingBackground
│   │   ├── particle.py                 Particle・ParticleSystem
│   │   ├── hud.py                      HUD（HP・スコア・コンボ・ウェポン表示）
│   │   ├── enemies/
│   │   │   ├── base.py                 Enemy 基底クラス
│   │   │   ├── virus.py                EnemyVirus（直進型）
│   │   │   ├── takeshi.py              EnemyTakeshi（波状移動型）
│   │   │   ├── broly.py                EnemyBroly（突進型）
│   │   │   ├── pachemon.py             EnemyPachemon（ジグザグ＋狙い撃ち）
│   │   │   ├── billy.py                EnemyBilly（低速・高HP・必ずドロップ）
│   │   │   └── boss.py                 Boss（フェーズ制・独立）
│   │   ├── bullets/
│   │   │   ├── player_bullet.py        PlayerBullet 各種（Normal/Wide/Pierce/Homing）
│   │   │   └── enemy_bullet.py         EnemyBullet
│   │   └── items/
│   │       ├── base.py                 Item 基底クラス
│   │       ├── weapon_item.py          WeaponItem（武器スロット選択）
│   │       └── heal.py                 HealItem（HP回復）
│   ├── stages/
│   │   ├── stage.py                    Stage（JSONロード・クリア判定）
│   │   └── spawner.py                  EnemySpawner（time / world_x イベント管理）
│   └── managers/
│       ├── resource.py                 ResourceManager（素材ロード・キャッシュ）
│       ├── sound.py                    SoundManager（BGMストリーミング・SE再生）
│       ├── input.py                    InputManager（キー入力・アクションAPI）
│       ├── highscore.py                HighScoreManager（JSON読み書き）
│       ├── settings.py                 SettingsManager（JSON読み書き・遅延保存）
│       └── playlog.py                  PlayLogger（JSONL形式でローカル保存）
├── assets/
│   ├── graphic/                        画像素材
│   ├── music/                          サウンド素材
│   │   ├── bgm/                        BGM（ストリーミング再生）
│   │   ├── se/                         効果音・ボイス（SE再生）
│   │   └── rounds/                     ラウンドSE（round1.wav〜、final.wav）
│   └── font/                           フォント
├── data/
│   ├── stages/                         ステージデータ（JSON）
│   │   ├── stage1.json
│   │   ├── stage2.json
│   │   ├── stage3.json
│   │   └── stage4.json
│   ├── playlogs/                       プレイログ（JSONL、日付別）
│   │   └── session_YYYYMMDD.jsonl
│   ├── highscore.json                  ハイスコア保存データ
│   └── settings.json                   設定保存データ
├── docs/
│   └── design.md                       本設計書
├── tests/
│   └── test_consistency.py             整合性テスト（pytest）
└── tools/
    ├── gen_docs.py                      design.md の AUTOGEN ブロック再生成
    ├── check_consistency.py             コード間整合性チェッカ（CI用）
    ├── balance_sheet.py                 武器DPS・敵HP・ボス想定撃破時間一覧
    ├── preview_boss.py                  ボス弾幕パターンのインタラクティブプレビュー
    ├── analyze_log.py                   プレイログ統計分析
    ├── gen_hit_sound.py                 効果音生成（hit.wav）
    ├── gen_boss_alert.py                ボス登場SE生成（boss_alert.wav）
    ├── gen_virus.py                     ウイルス敵画像生成
    ├── split_rounds.py                  ラウンドSE分割（round1〜9.wav, final.wav）
    ├── remove_bg.py                     敵画像背景除去
    └── download_bgm.py                  BGM一括ダウンロード（要 yt-dlp）
```

---

## 7. ステージデータ仕様

ステージデータはJSONファイルで管理し、コードを変更せずにステージを追加・調整できる。

```json
{
  "stage_id": 1,
  "bgm": "The_world_of_spirit_short.mp3",
  "random_drop_scale": 1.0,
  "terrain_layout": [
    {
      "type": "TerrainStrip",
      "theme": "fever_cave",
      "length": 4400,
      "gap_min": 380,
      "gap_max": 480,
      "start_offset": -90,
      "breakable_chance": 0.1
    }
  ],
  "world_events": [
    {"type": "EnemyTurret", "x": 2770, "count": 1, "surface": "bottom", "surface_offset": 20}
  ],
  "events": [
    {
      "time": 3.0,
      "type": "EnemyVirus",
      "count": 3,
      "formation": "line"
    },
    {
      "time": 10.0,
      "type": "EnemyPachemon",
      "count": 2,
      "formation": "v_shape",
      "enhanced": true
    },
    {
      "time": 38.0,
      "type": "Boss",
      "count": 1,
      "formation": "single"
    }
  ]
}
```

地形や固定配置は `terrain_layout` / `world_events` に `world_x` 基準で書く。これにより、山・砦・ゲート・砲台足場・中ボス戦闘エリアを、時間経過ではなくステージ座標に固定して設計できる。
既存互換として、スクロールに依存しない通常ウェーブやボス登場は `events` の `time` スケジュールを使える。
`random_drop_scale` は敵・破壊可能地形のランダムアイテムドロップ率に掛けるステージ倍率。`fixed_drop` やビリー撃破時の確定報酬には影響しない。

#### 時間イベント（`events`）

| フィールド | 必須 | 説明 |
|---|---|---|
| `time` | ○ | ステージ開始からの経過秒数（出現タイミング） |
| `type` | ○ | 敵の種別（EnemyVirus / EnemyTakeshi / EnemyBroly / EnemyPachemon / EnemyBilly / EnemyTurret / EnemyCrawler / EnemyDebrisLarge / EnemyDebrisShard / Boss / **Terrain** / **AuthoredTerrain** / **TerrainStrip**） |
| `count` | △ | 出現数（Terrain / AuthoredTerrain / TerrainStrip では不要） |
| `formation` | △ | 編隊の並び方（`line` / `v_shape` / `random` / `single`）。`y` / `surface` 指定時・Terrain / AuthoredTerrain / TerrainStrip では不要 |
| `y` | — | 出現Y座標を固定（指定時は formation 省略可） |
| `surface` | — | 地形表面に吸着して出現（`top` / `bottom`）。砲台などの足場配置に使う |
| `surface_offset` / `surface_step` | — | `surface` 指定時の表面からの中心オフセット・複数出現時の横間隔 |
| `enhanced` | — | `true` で強化版パラメータを使用（省略時は通常版） |
| `fixed_drop` | — | 撃破時に必ず出すアイテム名。中ボスなど、ご褒美配置の確定報酬に使う |

#### world_xイベント（`world_events`）

`world_events` は画面右端が対象Xに近づいたタイミングで出現する。`x` / `world_x` は配置座標、`trigger_x` は発火判定だけを別にしたい場合に使う。

| フィールド | 必須 | 説明 |
|---|---|---|
| `type` | ○ | 敵の種別。`EnemyTurret` など固定配置したい敵に使う |
| `x` / `world_x` | △ | 配置X座標。`trigger_x` だけを使う場合以外は指定する |
| `trigger_x` | — | 出現判定X。省略時は `x` / `world_x` |
| `count` | — | 出現数（既定1） |
| `formation` | △ | `line` / `v_shape` / `random`。`y` / `surface` 指定時は省略可 |
| `y` | — | 配置Y座標を固定 |
| `surface` | — | `top` / `bottom`。AuthoredTerrain / TerrainStrip や固定地形ブロックの表面に吸着する |
| `preload` / `spawn_margin` | — | 画面右端から何px手前で生成するか（既定80px） |
| `fixed_drop` | — | 撃破時に必ず出すアイテム名。中ボスなど、ご褒美配置の確定報酬に使う |

#### 地形レイアウト（`terrain_layout`）

`terrain_layout` はステージ開始時にまとめて生成する地形定義。未指定の場合は既存互換の `initial_terrain` を使う。
固定ブロックは `Terrain` のほか、意図が読みやすい別名として `solid` / `platform` / `gate` / `breakable_gate` / `weapon_gate` / `turret_mount` を使える。`gate` / `breakable_gate` / `weapon_gate` は既定で破壊可能になる。
`weapon_gate` は報酬用の血栓ゲートで、未指定でも `fixed_drop: "WeaponItem"` として扱われ、内部に青白い報酬コアを描く。
連続地形の新規作成は `AuthoredTerrain` を優先する。`AuthoredTerrain` は `top` / `bottom` の制御点で移動可能領域を直接指定する形式で、ステージ設計の主導権を乱数から手書きデータへ戻すための正式ルートとする。
`TerrainStrip` / `cave_section` / `corridor` は既存ステージ移行用の旧形式として扱う。

#### 地形イベント（`type: "Terrain"`）

上下の壁・障害物・デブリをステージごとに配置する（宇宙系はデブリまばら、岩石系は壁・岩が多い等、
ステージで濃淡を変える）。接触で自機にダメージ。砲台（EnemyTurret）の設置足場にも使う。

| フィールド | 必須 | 説明 |
|---|---|---|
| `time` | △ | `events` に書く場合の出現タイミング（秒）。`terrain_layout` では不要 |
| `type` | ○ | `"Terrain"` / `"solid"` / `"platform"` / `"gate"` / `"breakable_gate"` / `"weapon_gate"` / `"turret_mount"` |
| `x` / `world_x` | — | ワールドX座標。省略時は `screen_x` / `start_offset` / 画面右端基準 |
| `screen_x` / `start_offset` | — | カメラ位置からの相対配置 |
| `y` | ○ | 配置Y座標（左上基準） |
| `w` / `h` | ○ | 幅・高さ（px） |
| `kind` | ○ | 見た目種別（`wall` / `rock` / `debris`） |
| `destructible` | — | `true` で破壊可能地形にする（城門・封鎖壁など）。`gate` / `breakable_gate` / `weapon_gate` は既定で `true` |
| `hp` | — | 破壊可能地形のHP |
| `drop_chance` | — | 破壊時のランダムアイテムドロップ率 |
| `fixed_drop` | — | 破壊時に必ず出すアイテム名。血栓ゲートなど、ご褒美配置の確定報酬に使う |

#### 手書き連続地形イベント（`type: "AuthoredTerrain"`）

上下境界を明示して、通路幅・圧迫地点・戦闘エリアの広さを直接設計する。`top` は上側地形の下端Y、`bottom` は下側地形の上端Yを表す。プレイヤーが動ける領域は `top` と `bottom` の間になる。

| フィールド | 必須 | 説明 |
|---|---|---|
| `time` | △ | `events` に書く場合の生成タイミング（秒）。`terrain_layout` では不要 |
| `type` | ○ | `"AuthoredTerrain"` |
| `theme` | ○ | 見た目テーマ（`fever_cave` / `debris` / `meme_static` / `fortress` / `shogi_void`） |
| `top` | ○ | `[[x, y], ...]`。上側地形の下端Y制御点 |
| `bottom` | ○ | `[[x, y], ...]`。下側地形の上端Y制御点 |
| `length` | — | 生成する横幅（省略時は制御点の最大X） |
| `segment_w` | — | 1セグメントの横幅（既定64px） |
| `min_gap` | — | 上下境界の最低通路幅（既定160px） |
| `curve` | — | `"smooth"` / `"linear"`。省略時は `"smooth"` |
| `renderer` | — | Stage3 では `"stage3_composer"` を指定して素材composer描画を使う |

#### 旧連続地形イベント（`type: "TerrainStrip"`）

グラディウス風の上下壁・洞窟・要塞回廊をセグメント列として生成する。接触判定は矩形セグメントごとに行い、
見た目はテーマ別の手続き描画で表現する。Stage1 では `fever_cave` を使い、発熱回廊の上下壁を構成する。

| フィールド | 必須 | 説明 |
|---|---|---|
| `time` | △ | `events` に書く場合の生成タイミング（秒）。`terrain_layout` では不要 |
| `type` | ○ | `"TerrainStrip"` / `"cave_section"` / `"corridor"` |
| `theme` | ○ | 見た目テーマ（`fever_cave` / `debris` / `meme_static` / `fortress` / `shogi_void`） |
| `length` | ○ | 生成する横幅（px） |
| `segment_w` | — | 1セグメントの横幅（既定64px） |
| `gap_min` / `gap_max` | — | 上下壁の通路幅レンジ（px） |
| `center_y` / `center_wave` | — | 通路中心と上下揺れ幅 |
| `top_min` / `bottom_min` | — | 上下壁の最低厚み |
| `irregularity` | — | セグメントごとの局所的な凹凸量 |
| `profile` | — | 形状プロファイル（`normal` / `mountain` / `ceiling`）。山斜面・天井せり出しを作る |
| `breakable_chance` | — | 通路側に張り出した破壊可能岩の出現率（0.0〜1.0）。壁全体は消えない |
| `breakable_hp` | — | 破壊可能岩のHP |
| `breakable_drop_chance` | — | 破壊時のランダムアイテムドロップ率 |
| `x` / `world_x` | — | ワールドX座標。省略時は `start_offset` 基準 |
| `start_offset` | — | 生成開始Xの補正（画面左から始める場合は負値） |
| `seed` | — | 形状・模様の固定乱数シード |

---

## 8. データ保存仕様

### 8.1 ハイスコア（data/highscore.json）

```json
[
  { "rank": 1, "name": "AAA", "score": 98500, "stage": 3 },
  { "rank": 2, "name": "BBB", "score": 72000, "stage": 2 }
]
```

### 8.2 設定（data/settings.json）

```json
{
  "bgm_volume": 0.8,
  "se_volume": 1.0,
  "key_bindings": {
    "move_up":       "K_UP",
    "move_down":     "K_DOWN",
    "move_left":     "K_LEFT",
    "move_right":    "K_RIGHT",
    "fire":          "K_z",
    "laser":         "K_SPACE",
    "weapon_select": "K_v",
    "pause":         "K_x"
  }
}
```

### 8.3 プレイログ（data/playlogs/session_YYYYMMDD.jsonl）

ゲームバランス調整用のローカルログ。外部送信はしない。1プレイセッション1レコード（JSONL形式）。

```json
{
  "started_at": "2026-04-01T02:34:18",
  "stage_reached": 4,
  "cleared": true,
  "score": 178700,
  "kill_count": 319,
  "events": [
    {"type": "stage_start", "ts": "...", "stage": 1},
    {"type": "boss_killed", "ts": "...", "stage": 1, "elapsed_sec": 71.0, "weapon": {...}},
    {"type": "player_death", "ts": "...", "stage": 2, "elapsed_sec": 34.5, "hp": 1, "weapon": {...}}
  ],
  "ended_at": "2026-04-01T02:40:58"
}
```

| イベント type | 記録タイミング |
|---|---|
| `stage_start` | ステージ開始時 |
| `boss_killed` | ボス撃破時（経過秒・武器状態を記録） |
| `player_death` | プレイヤー死亡時（経過秒・HP・武器状態を記録） |

---

## 9. ビルド方法

### 9.1 仮想環境

```powershell
# アクティベート
.venv/Scripts/Activate.ps1
```

### 9.2 実行

```bash
python main.py
```

### 9.3 PyInstaller で exe ビルド

PyInstaller はソースからビルドする必要がある（Windows 環境での互換性確保のため）。

```bash
# 1. VC Build Tools のインストール（初回のみ）
choco install -y visualstudio2019-workload-vctools

# 2. PyInstaller リポジトリをクローン
git clone https://github.com/pyinstaller/pyinstaller

# 3. ブートローダーをビルド
cd pyinstaller/bootloader
python ./waf all

# 4. ゲームをビルド
cd ../../
pyinstaller game.spec --onefile
```

参考: https://pyinstaller.org/en/latest/bootloader-building.html

---

## 10. サウンド・演出仕様（実装リファレンス）

> 本セクションは現在の実装に基づく仕様です。BGM/SEファイルは `assets/music/` に配置。

### 10.1 BGM一覧

| シーン / タイミング | BGM ファイル | 備考 |
|------------------|------------|------|
| タイトル画面 | `bgm/The_Final_Battle_short.mp3` | 既にそのBGMが流れている場合は再起動しない |
| S1 通常 | `bgm/The_world_of_spirit_short.mp3` | ラウンドSE終了後に再生（冒頭18秒カット版） |
| S2 通常 | `bgm/戦艦ハルバード：甲板.mp3` | 同上 |
| S3 通常 | `bgm/MEGALOVANIA.mp3` | 同上 |
| S4 通常 | `bgm/ビッグブリッヂの死闘.mp3` | 同上 |
| S1 ボス戦 | `bgm/決戦.mp3` | ボス名バナーで切替 |
| S2・S3 ボス戦 | `bgm/決戦_FF10.mp3` | 同上 |
| S4 ボス戦（ラスボス） | `bgm/決戦！N.mp3` | 同上 |
| S4 先輩復帰（白閃光） | `bgm/Rebirth_the_edge.mp3` | カロナール先輩復帰の盛り上がりで切替（音量は基準の0.7倍） |
| S1クリア幕間（先輩会話） | `bgm/Death_by_Glamour.mp3` | CutsceneScene の bgm_alias で再生 |
| ゲームクリア | `bgm/FFVI_勝利のファンファーレ.mp3` | loops=0（1回再生） |
| ゲームオーバー | `se/gameover.mp3` | SE扱い（BGMは stop してから再生） |

ボス戦BGMは `src/scenes/game/config.py` の `BOSS_BGM`（ステージ別）を単一ソースとする。

ステージ開始時はラウンドSE（`assets/music/rounds/round{N}.wav`）を先に再生し、その長さ + 0.3秒後にBGM再生開始。ファイルが存在しない場合は `final.wav` を使用。

### 10.2 効果音（SE）一覧

#### プレイヤー操作

| イベント | SE ファイル | vol | 付随演出 |
|---------|------------|-----|---------|
| 通常弾発射 | `ウェポン：normalshot_shot.mp3` | 0.4 | — |
| ホーミング弾発射 | `ウェポン：missile_shot.mp3` | 0.5 | — |
| レーザーチャージ開始 | `ウェポン：laser_charge.mp3` | 0.75 | 1.5倍に増量 |
| レーザー発射（Lv1〜4） | `ウェポン：laser1_shot.mp3` | 0.225 | カメラシェイク・1.5倍に増量 |
| レーザー発射（Lv5+） | `ウェポン：laser2_shot.mp3` | 0.225 | カメラシェイク・1.5倍に増量 |
| レーザー命中 | `ウェポン：laser_hit.mp3` | 0.12 | ヒットパーティクル |
| 被弾（残機あり） | `shout.wav` | 0.6 | 無敵時間開始 |
| バリアで弾を相殺 | `hit.wav` | 0.9 | パーティクル + シェイク |
| ウェポンアイテム取得 | `item_weapon_pickup.wav`（SE_ITEM_WEAPON） | 0.75 | 通常時・ボス撃破後の WeaponItem 取得 |
| 回復アイテム取得 | `item_heal_pickup.wav`（SE_ITEM_HEAL / SE_HEAL） | 0.75 | HealItem 取得 |
| その他アイテム取得 | `item_pickup.wav`（SE_ITEM） | 0.7 | 将来追加アイテム向けのフォールバック |

> **注**: `laser.wav` はポストボスフェーズ（`post_boss_mixin.py`）の試し撃ちのみで使用。通常ゲーム中は上記ウェポン SE を使う。

#### 敵・ヒット

| イベント | SE ファイル | vol | 備考 |
|---------|------------|-----|------|
| 通常弾が雑魚に命中 | `ウェポン：normalshot_hit.mp3` | 0.4 | — |
| ホーミング弾が雑魚に命中 | `ウェポン：missile_hit.mp3` | 0.4 | — |
| 通常弾がボスに命中 | `ウェポン：normalshot_hit.mp3` | 0.3 | + カメラシェイク |
| ホーミング弾がボスに命中 | `ウェポン：missile_hit.mp3` | 0.3 | + カメラシェイク |
| 雑魚撃破（全敵共通） | `game_explosion9.mp3` | 0.3 | + 爆発パーティクル + シェイク |
| EnemyVirus 撃破 | `game_explosion9.mp3` | 0.9 | 共通SEに追加で再生 |
| EnemyTakeshi 撃破 | `お前ら人間じゃねぇ!.mp3` | 0.45 | 同上 |
| EnemyBroly 撃破 | `ブロリー_ヘェア！.mp3` | 0.9 | 同上 |
| EnemyPachemon 撃破 | `でたぁ.mp3` | 0.45 | 同上 |
| EnemyBilly 撃破 | `アｯー♂.mp3` | 1.0 | 同上 |
| ボス撃破 | `game_explosion9.mp3` + `でたぁ.mp3` | 0.8 / 1.0 | BGM fadeout と同時 |
| ボス追加爆発（演出） | `game_explosion9.mp3` | 0.5 | 撃破後の時間差爆発 |
| ボス戦開始バナー | `fight.wav` | 0.5 | FIGHT! バナー表示時 |
| 雑魚/砲台 攻撃（dummy） | `dummy_enemy_shot.wav`（SE_ENEMY_SHOT） | 0.6 | パチえもん・砲台の発射 |
| ボス 攻撃（dummy） | `dummy_boss_shot.wav`（SE_BOSS_SHOT） | 0.4 | 0.25秒間隔で再生制御 |
| 先輩 被弾（dummy） | `dummy_karonaru_hit.wav`（SE_KARONARU_HIT） | — | カロナール先輩 被弾時 |
| 先輩 退場（dummy） | `dummy_karonaru_retire.wav`（SE_KARONARU_RETIRE） | — | カロナール先輩 撤退時 |

#### UI・演出

| イベント | SE ファイル | vol | 使用シーン |
|---------|------------|-----|----------|
| タイプライター | `type.wav`（SE_TYPE） | 0.16 | CutsceneScene / BlackholeScene |

#### メニュー操作

| イベント | SE ファイル | vol | 使用シーン |
|---------|------------|-----|----------|
| カーソル移動 | `メニュー操作SE：カーソル移動.mp3` | 0.5 | タイトル・ポーズ・設定・チュートリアル・アップグレード |
| 決定 | `メニュー操作SE：決定.mp3` | 0.6 | 全メニューシーン |
| キャンセル / 戻る | `メニュー操作SE：キャンセル.mp3` | 0.5 | ゲームオーバー・設定・ポーズ・ハイスコア・チュートリアル等 |

### 10.3 ボス演出・セリフ仕様

#### ボス名・セリフ

| S | ボス名 | 登場セリフ | 戦闘中セリフ | 撃破後セリフ |
|---|--------|-----------|------------|------------|
| 1 | 悪寒大王インフルX | 「眠れ。考えるな。」<br>「弱った脳に世界を処理する資格はない。」 | なし | 「よし……倒した。」<br>「なのに、まだ目が覚めない。」<br>「ただの風邪の夢にしては、妙に話ができすぎている。」 |
| 2 | 情報汚染超人野獣ブロリー | 「みんな暮らしをやってる。」<br>「暮らしをやってないのはお前だけ。」 | なし | 「ミームは消えた。」<br>「だが「やってないのはお前だけ」という声は」<br>「まだ耳の奥に残っている。」 |
| 3 | 婚活要塞マッチング・ゼロ | 「けれどね、私にも、」<br>「寂しい時が、あるのです。」 | なし | 「俺は、そんなに駄目か？」<br>「いや……駄目かどうかを決めるために、」<br>「ずっと他人の評価盤面ばかり見ていたのかもしれない。」 |
| 4 | 棋理の化身　藤井竜王 | 「盤の外で負け続けたから、」<br>「盤の上に逃げてきたのか。」 | Form1半減時:「お前は才能に負けるのではない。比較に酔った自我に負けるのだ。」<br>Form2開始時:「乗り越えて見せろ、さあ。」 | 「そうか。」<br>「お前だったのか。」<br>「俺がずっと勝てないと思い込んでいた相手は。」 |

セリフはENTER/SPACEで送り。撃破後セリフの表示開始は爆発演出後2.5秒遅延（セリフのないステージは遅延なし）。

#### 撃破演出パラメータ

| | 通常ボス（S1〜3） | ラスボス（S4） |
|--|----------------|--------------|
| スロー倍率 | 0.35 | 0.18 |
| スロー解除 | 爆発演出終了後 約1.3秒で線形に1.0へ | 同左 |
| 追加爆発タイミング | 0.4 / 0.9 / 1.5秒後（3回） | 0.5 / 1.0 / 1.6 / 2.4秒後（4回） |
| ドロップ | WeaponItem×1 + HealItem×4 | なし（エピローグへ遷移） |
| 自動遷移タイムアウト | 30秒（右端移動でも遷移） | 4.5秒 |
