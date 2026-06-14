# Claude 修正指示書: ゲーム改善タスク

## 目的

「インフルとの死闘」の現行仕様とプレイログ分析に基づき、初見プレイヤーが武器システムを理解しやすくし、2面以降の再挑戦体験とボス戦の納得感を改善する。

SSOT 原則を守ること。特に、敵・アイテム定義は `src/core/registries.py`、難易度スケールは `src/core/balance.py`、セリフ・説明文は該当する既存ソースだけを編集する。

## 採用する改善

### 1. チュートリアルを現仕様に合わせる

対象: `src/scenes/tutorial_scene.py`

現状の説明が古い。

- 通常射撃は `Z`
- レーザーは `SPACE`
- ウェポン選択は `V`
- ポーズは `X`
- `Bキー: ボム` は現仕様にないため削除
- `W(黄)で選択画面を開く` は誤り。`W` はアイテム表示で、取得後に `V` で選択画面を開く
- `+ は HP を1回復` は誤り。`HealItem` は `HEAL_AMOUNT`、現状 `+30`
- `S(青) 5秒間無敵` は今後ランダムドロップ対象外にするなら、通常チュートリアルから削除
- ボス説明の「HP50% → 5way、HP20% → 3way高速」は現行の `boss.py` と合っていないため、汎用説明にする

推奨説明:

- 操作: 矢印移動、`Z` 通常射撃、`SPACE` レーザー、`V` ウェポン選択、`X` ポーズ
- アイテム: `W` はウェポン在庫 +1、取得後 `V` → 左右で選択 → `ENTER` で強化
- 回復: `+` は HP 回復
- ボス: シールド、装甲、砲台などステージごとに弱点や攻撃チャンスが違う

可能なら、キー表示は `SettingsManager` の `key_bindings` から表示名を作るヘルパーに寄せ、今後キーバインド変更時に説明がずれないようにする。

### 2. コンティニュー時の HP を修正する

対象: `src/scenes/gameover.py`

現状:

```python
self.game.shared.carry_hp = 3
```

HP 最大100制に移行済みなのに、コンティニュー時 HP が 3 でほぼ瀕死になる。これはバグとして修正する。

推奨:

- `PLAYER_MAX_HP` を `src.core.balance` から参照する
- コンティニュー時は `PLAYER_MAX_HP` の 50% 以上にする
- 迷うなら `PLAYER_MAX_HP` 全回復でよい。残機を消費する時点で十分なペナルティがある

例:

```python
from src.core.balance import PLAYER_MAX_HP
self.game.shared.carry_hp = PLAYER_MAX_HP
```

### 3. ウェポン在庫の導線を強化する

対象候補:

- `src/scenes/game_scene.py`
- `src/entities/hud.py`
- `src/scenes/game/upgrade_mixin.py`

プレイログでは、2面死亡時に `main_level=0` のケースが多い。ウェポン取得後に `V` → `ENTER` で使う流れが伝わっていない可能性が高い。

改善案:

- `WeaponItem` 初取得時だけ、短いポップアップを強めに出す
  - 例: `WEAPON STOCK +1` / `Vで強化を選択`
- 在庫がある間、HUD の `WEAPON STOCK xN [V]` を点滅または明るい色で強調
- `V` で開いた選択UIのヒントに「1個消費して強化」と明記
- 初回取得直後のみ、選択UIを自動で開く案も可。ただし戦闘中に突然止まる違和感がある場合は、HUD強調だけでよい

注意:

- `WeaponItem.apply()` は現在ゲーム本編では直接使っていないが、デバッグや将来用途があるかもしれない。削除や挙動変更は慎重にする
- `weapon_stock` を消費する仕様は維持する

### 4. ボスギミックの可読性を上げる

対象候補:

- `src/entities/enemies/boss.py`
- `src/scenes/game_scene.py` の `_draw_boss_gimmick`
- `src/entities/hud.py`

現状、ボスごとのギミック自体は良いが、初見では「なぜダメージが通らないか」が分かりにくい。

改善案:

- shield:
  - シールド中に `SHIELD` または `GUARD` 表示
  - 無防備時間に `BREAK CHANCE` などを表示
- weakpoint:
  - 装甲がある間は `ARMOR` ゲージまたはラベルを出す
  - 弱点露出時は `WEAK POINT` 表示
- turrets:
  - 砲台が生きている間は `TURRET GUARD xN` 表示
  - 全滅スタン中は `STUN` / `DAMAGE UP` 表示

実装は既存の `_draw_boss_gimmick` に寄せる。新規UIを大きく作り込むより、ボスHPバー付近に短いラベルを足す程度でよい。

### 5. 統計画面に死亡ホットスポットと死亡時武器状態を追加する

対象:

- `src/scenes/stats_scene.py`
- 必要に応じて `src/managers/playlog.py`
- 参考: `tools/analyze_log.py`

`tools/analyze_log.py` には以下の分析がすでにある。

- ステージ別死亡タイミング分布
- 死亡時の武器状態
- ボス撃破時の武器状態

ゲーム内の `StatsScene` に、最低限以下を追加する。

- ステージ別死亡ホットスポット
  - 例: `Stage 2 death peak: 80-90s (4)`
  - 10秒刻みで最多ゾーンを出すだけでよい
- 死亡時の平均武器状態
  - `main_level`, `speed_level`, `laser_level`, `homing_level`, `magnet_level`, `has_barrier`
  - 画面が狭ければ `main/speed/laser/homing` 優先
- `main_level` が低い死亡が多い場合、調整用に分かる表示を入れる
  - 例: `low main deaths: 8/11`

注意:

- UIが詰まる場合はページ切り替え式にする
  - 1ページ目: 既存サマリー
  - 2ページ目: 死亡ホットスポット
  - 3ページ目: 死亡時武器状態
- 統計は開発・調整用途なので、見た目より読みやすさ優先でよい

### 6. 今後使わないアイテムを説明・定義から消す

対象:

- `src/core/registries.py`
- `src/scenes/game/debug_stage_panel.py`
- `src/entities/items/weapon_item.py`
- `src/entities/items/shield.py`
- `src/scenes/tutorial_scene.py`
- `docs/design.md` は手編集せず `tools/gen_docs.py` で更新

方針:

- `LaserItem` と `HomingItem` は今後使わないので削除する
- ランダムドロップ対象外で今後使わない説明も消す
- `ShieldItem` が通常ゲームで使われていないなら削除候補。ただしウェポン選択の `BARRIER` とは別物なので混同しない

具体作業:

- `ITEM_DEFS` から `LaserItem` / `HomingItem` を削除
- `src/entities/items/weapon_item.py` から `LaserItem` / `HomingItem` クラスを削除
- `debug_stage_panel._make_item()` から該当分岐を削除
- チュートリアルから該当アイテム説明を削除
- docs の AUTOGEN は手で触らず、最後に `gen_docs.py` を実行する

`random_item()` は `ITEM_DEFS` の `drop_weight > 0` から生成候補を決める。変更時は `ITEM_DEFS` と説明の整合性を必ず確認する。

## 検証手順

通常のローカル環境では以下を実行する。

```powershell
.venv/Scripts/python tools/gen_docs.py
.venv/Scripts/python tools/check_consistency.py
.venv/Scripts/pytest
```

可能ならゲームを起動して、最低限以下を手動確認する。

```powershell
.venv/Scripts/python main.py
```

確認項目:

- チュートリアルの操作説明が実操作と一致する
- `W` アイテム取得後、在庫表示と `V` 選択UIが分かりやすい
- コンティニュー時に HP が 3 ではなく適切な値で復帰する
- ボスの shield / weakpoint / turrets 状態が画面上で分かる
- 統計画面で死亡ホットスポットと死亡時武器状態が見られる
- `LaserItem` / `HomingItem` が docs とデバッグUIに残っていない

## 環境補足

Codex 側の同梱 Python では `analyze_log.py` は実行できたが、`balance_sheet.py` と `check_consistency.py` は `pygame` が無く失敗した。これはゲーム本体の不具合ではなく、実行環境の依存関係不足。

Claude はプロジェクトの `.venv` を優先して使うこと。

もし `.venv/Scripts/python` が壊れている、または `pygame` が見つからない場合は、ローカル環境で依存関係を直してから検証する。

```powershell
py -3.11 -m venv .venv
.venv/Scripts/python -m pip install -U pip
.venv/Scripts/python -m pip install -e .
```

その後、上記の検証手順を再実行する。

## 触らないこと

- `docs/design.md` の `<!-- AUTOGEN:* -->` 内を手編集しない
- SSOT を増やさない
- ストーリー本文の大改変はしない
- 難易度全体を大きく下げる調整は今回の主目的ではない
- 未採用の「2面そのものの難易度調整」は今回は行わない。ただし、ウェポン導線改善後のログで再判断できるよう統計表示を強化する
