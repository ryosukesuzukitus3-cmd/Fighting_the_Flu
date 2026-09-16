# 効果音候補（差し替え検討用）

このフォルダは既存 SE の差し替え候補を集めたものです。**コードからは一切参照されていません。**
採用する場合は、選んだファイルを `assets/music/se/` 直下へ実際に使うファイル名でコピーし、
`src/story/aliases.py` などの SE エイリアス定義を更新してください（CLAUDE.md の SSOT 参照）。

## 出典サイトと利用規約の要旨

### 効果音ラボ（soundeffect-lab.info）
- 規約ページ: https://soundeffect-lab.info/agreement/
- 商用利用: 無料（個人・法人・公的機関問わず可）
- クレジット表記: **不要**（任意、禁止ではない）
- 加工: 可（改変版そのものの再配布は禁止）
- 補足: 「効果音を自由に選択・抜き出しできるアプリのデフォルト素材」としての組み込みは禁止だが、
  ゲームの固定演出音として組み込む用途（音源ファイルむき出しでも可、有料販売可）は規約上OKと明記。
  AI学習用途・音商標登録は禁止。

### 無料効果音で遊ぼう！（taira-komori.net、将棋駒音の出典）
- 規約ページ: https://taira-komori.net/welcome.html
- 商用利用: 可（「ゲーム・映画・テレビ・ラジオ・YouTube・ネット配信・CM・配信サイトなど、商業目的の使用OK」と明記）
- クレジット表記: 規約上の必須記載なし（**不要と判断**）
- 加工: 可（ファイルの編集・変換・音声加工OKと明記）
- 禁止事項: サイト内容の再配布、素材の再販売、Scratchでの使用

上記2サイトのみ使用。いずれもクレジット表記なしで利用可能なため、**このフォルダの候補は全てクレジット表記不要**です。
（OtoLogic は CC BY 4.0 でクレジット必須のため、WebFetch でのアクセスが403で規約再確認ができず、今回は候補に採用していません。）

## 候補一覧

各ファイルの「音の印象」は、出典サイトに掲載されていた日本語の説明文・音源名から判断したものです
（実際に試聴した上で最終選定してください）。

### 1. normalshot（通常弾の射撃音・本命差し替え候補）

| ファイル | 出典URL | ライセンス/クレジット | 音の印象 |
|---|---|---|---|
| `normalshot/01_soundeffectlab_shot1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/shot1.mp3 | 効果音ラボ・クレジット不要 | 「ショット」。SF系の汎用ショット音、軽め |
| `normalshot/02_soundeffectlab_laser1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/laser1.mp3 | 効果音ラボ・クレジット不要 | 「レーザー80年代風」。ピシュ系レトロレーザー |
| `normalshot/03_soundeffectlab_beamgun-shot1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/beamgun-shot1.mp3 | 効果音ラボ・クレジット不要 | 「ビームガン」。ビーム系の発射音 |

### 2. enemy_shot（雑魚・砲台の発射音、軽め）

| ファイル | 出典URL | ライセンス/クレジット | 音の印象 |
|---|---|---|---|
| `enemy_shot/01_soundeffectlab_handgun-firing1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/handgun-firing1.mp3 | 効果音ラボ・クレジット不要 | 「拳銃銃声」。パンという単発銃声 |
| `enemy_shot/02_soundeffectlab_machinegun-firing1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/machinegun-firing1.mp3 | 効果音ラボ・クレジット不要 | 「サブマシンガン発射1」。連射向きの軽い銃声 |
| `enemy_shot/03_soundeffectlab_beamgun3.mp3` | https://soundeffect-lab.info/sound/battle/mp3/beamgun3.mp3 | 効果音ラボ・クレジット不要 | 「ビーム砲3」。ビーム系の別バリエーション |

### 3. boss_shot（ボスの発射音、重め）

| ファイル | 出典URL | ライセンス/クレジット | 音の印象 |
|---|---|---|---|
| `boss_shot/01_soundeffectlab_cannon1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/cannon1.mp3 | 効果音ラボ・クレジット不要 | 「大砲1」。重い砲撃音 |
| `boss_shot/02_soundeffectlab_heavy-machine-gun1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/heavy-machine-gun1.mp3 | 効果音ラボ・クレジット不要 | 「重機関銃乱射1」。重厚な連射音 |
| `boss_shot/03_soundeffectlab_beamgun1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/beamgun1.mp3 | 効果音ラボ・クレジット不要 | 「ビーム砲1エネルギーがほとばしる」。厚みのあるビーム音 |

### 4. karonaru_hit（先輩被弾、コミカル可）

| ファイル | 出典URL | ライセンス/クレジット | 音の印象 |
|---|---|---|---|
| `karonaru_hit/01_soundeffectlab_boyoyon1.mp3` | https://soundeffect-lab.info/sound/anime/mp3/boyoyon1.mp3 | 効果音ラボ・クレジット不要 | 「ボヨヨーン」。びっくり箱風のギャグ音 |
| `karonaru_hit/02_soundeffectlab_boyon1.mp3` | https://soundeffect-lab.info/sound/anime/mp3/boyon1.mp3 | 効果音ラボ・クレジット不要 | 「ボヨン」。何かに弾き返される音、短め |
| `karonaru_hit/03_soundeffectlab_fall-down1.mp3` | https://soundeffect-lab.info/sound/anime/mp3/fall-down1.mp3 | 効果音ラボ・クレジット不要 | 「ずっこけるドテーン」。コミカルな転倒音 |

### 5. karonaru_retire（先輩退場、ポフッ/シュン系）

| ファイル | 出典URL | ライセンス/クレジット | 音の印象 |
|---|---|---|---|
| `karonaru_retire/01_soundeffectlab_flee1.mp3` | https://soundeffect-lab.info/sound/anime/mp3/flee1.mp3 | 効果音ラボ・クレジット不要 | 「ピューンと逃げる」。一瞬で視界から消え去るイメージ |
| `karonaru_retire/02_soundeffectlab_magic-worp1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/magic-worp1.mp3 | 効果音ラボ・クレジット不要 | 「ワープ消えるイメージ」。シュンと消える系 |

### 6. karonaru_arrive（先輩登場、シュタッ/キラーン系）

| ファイル | 出典URL | ライセンス/クレジット | 音の印象 |
|---|---|---|---|
| `karonaru_arrive/01_soundeffectlab_shakin1.mp3` | https://soundeffect-lab.info/sound/anime/mp3/shakin1.mp3 | 効果音ラボ・クレジット不要 | 「シャキーン1」。ポーズを決める音、登場向き |
| `karonaru_arrive/02_soundeffectlab_shakin2.mp3` | https://soundeffect-lab.info/sound/anime/mp3/shakin2.mp3 | 効果音ラボ・クレジット不要 | 「シャキーン2」。光る演出にも使える版 |

### 7. shogi_place（将棋の駒を打つ「ピシッ」音）

| ファイル | 出典URL | ライセンス/クレジット | 音の印象 |
|---|---|---|---|
| `shogi_place/01_tairakomori_Shogi1.mp3` | https://taira-komori.net/sound/playing01/Shogi1.mp3 | 無料効果音で遊ぼう！・クレジット不要 | 将棋の駒を打つ「パチン」音（Shogiシリーズ1） |
| `shogi_place/02_tairakomori_Shogi3.mp3` | https://taira-komori.net/sound/playing01/Shogi3.mp3 | 無料効果音で遊ぼう！・クレジット不要 | 将棋の駒を打つ「パチン」音（Shogiシリーズ3、別バリエーション） |
| `shogi_place/03_tairakomori_drop_Shogi_piece1.mp3` | https://taira-komori.net/sound/playing01/drop_Shogi_piece1.mp3 | 無料効果音で遊ぼう！・クレジット不要 | 駒を置く音の別テイク |

### 8. light（神々しい光・キラーン、最終決戦の白閃光用）

| ファイル | 出典URL | ライセンス/クレジット | 音の印象 |
|---|---|---|---|
| `light/01_soundeffectlab_eye-shine1.mp3` | https://soundeffect-lab.info/sound/anime/mp3/eye-shine1.mp3 | 効果音ラボ・クレジット不要 | 「きらーん1」。目が光るような短いキラーン音 |
| `light/02_soundeffectlab_shine1.mp3` | https://soundeffect-lab.info/sound/anime/mp3/shine1.mp3 | 効果音ラボ・クレジット不要 | 「きらきら輝く1」。汎用の輝きSE |
| `light/03_soundeffectlab_magic-attack-holy1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/magic-attack-holy1.mp3 | 効果音ラボ・クレジット不要 | 「聖魔法」。悪を浄化する裁きの光、やや長め・荘厳系 |

### 9. error（システムエラー/ブブー音）

| ファイル | 出典URL | ライセンス/クレジット | 音の印象 |
|---|---|---|---|
| `error/01_soundeffectlab_beep4.mp3` | https://soundeffect-lab.info/sound/button/mp3/beep4.mp3 | 効果音ラボ・クレジット不要 | 「ビープ音4」＝説明文そのまま「ブブー」。本命候補 |
| `error/02_soundeffectlab_beep1.mp3` | https://soundeffect-lab.info/sound/button/mp3/beep1.mp3 | 効果音ラボ・クレジット不要 | 「ビープ音1」。選択不可項目を押した時のエラー音 |

### 10. boss_transform（ボス形態変化のスティンガー）

| ファイル | 出典URL | ライセンス/クレジット | 音の印象 |
|---|---|---|---|
| `boss_transform/01_soundeffectlab_doon1.mp3` | https://soundeffect-lab.info/sound/anime/mp3/doon1.mp3 | 効果音ラボ・クレジット不要 | 「ドーン」。和太鼓・ビブラスラップ系の決めスティンガー |
| `boss_transform/02_soundeffectlab_hero1.mp3` | https://soundeffect-lab.info/sound/anime/mp3/hero1.mp3 | 効果音ラボ・クレジット不要 | 「ヒーローの決めポーズ」。かっこよく決まる系 |

候補2件のみ（3件目は「ズコー」寄りの音しか見つからず、変身スティンガーとして不適と判断し除外）。

### 11. blackhole_rumble（重低音のゴゴゴ/地鳴り）

| ファイル | 出典URL | ライセンス/クレジット | 音の印象 |
|---|---|---|---|
| `blackhole_rumble/01_soundeffectlab_earth-tremor1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/earth-tremor1.mp3 | 効果音ラボ・クレジット不要 | 「地響き」。体重で地割れ発生、重量感のある地鳴り |
| `blackhole_rumble/02_soundeffectlab_magic-quake1.mp3` | https://soundeffect-lab.info/sound/battle/mp3/magic-quake1.mp3 | 効果音ラボ・クレジット不要 | 「地震魔法1地響き」。魔法寄りのゴゴゴ音 |
| `blackhole_rumble/03_soundeffectlab_cliff-failure1.mp3` | https://soundeffect-lab.info/sound/various/mp3/cliff-failure1.mp3 | 効果音ラボ・クレジット不要 | 「崖崩れ」。地盤沈下・地割れ・地震、やや長尺 |

いずれも単発の効果音で、シームレスループ用素材ではありません。ループさせる場合はゲーム側でクロスフェード等の対応が必要です。
（OpenGameArt の CC0 ループ素材集 `30 CC0 SFX loops` も調査しましたが、ファイル名から音の性質を判別できず
　試聴確認なしでは選定できなかったため、今回は候補に含めていません。）

## 未取得のスロット

なし。全11スロットで候補を確保しました。
