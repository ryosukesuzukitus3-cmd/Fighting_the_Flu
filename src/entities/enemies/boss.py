from __future__ import annotations
import math
import random
from typing import TYPE_CHECKING
import pygame
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.entities.bullets.enemy_bullet import EnemyBullet
from src.entities.bullets.shogi_bullet import ShogiBullet, ThrownBoardBullet

if TYPE_CHECKING:
    from src.core.game import Game
    from src.entities.player import Player

# ─── ステージ別フェーズ設定: (HPしきい値, 攻撃パターン, 射撃間隔) ──────────────
# パターン一覧:
#   fan5      : 5-way ±40° 扇形（薄い）
#   fan7      : 7-way ±54° 扇形（広め）
#   aimed     : 単発 超高速 狙い打ち
#   dbl_aimed : 2-way ±12° 高速 狙い打ち
#   ring8     : 8方向 全方位 等間隔
#   ring12    : 12方向 全方位 等間隔
#   ring16    : 16方向 全方位 密度高（激難）
#   aimring6  : 6方向 45°毎 + プレイヤー方向に位相合わせ
#   aimring8  : 8方向 45°毎 + プレイヤー方向に位相合わせ
#   scatter   : 12発 ランダム広角 散弾
#   cross     : 5-way 十字気味 (-90,-30,0,+30,+90)
#   spiral    : 6アームスパイラル（回転角ずれあり）
#   vortex2   : 2アームスパイラル（高速回転）
#   vortex3   : 3アームスパイラル（高速弾・激難）
#   chaos     : カオス弾幕（aimring8 + vortex2 + ランダムオフセット）
#   burst3    : 3連狙撃（速度差つき）
#   wall_gap  : 縦の弾壁。毎回違う位置に抜け道
#   fever_lunge : 前進圧力をかける突進連動弾
#   mega_laser  : 太い横レーザー＋弱点露出の後隙
#   drone_cross : 子機/砲台と噛み合う交差狙撃
#   rock_fall   : 上方から落石
#   shogi_file  : 将棋駒の隊列弾（Form1）。歩の隊列が主、たまに香/桂/銀/金が混じる
#   shogi_storm : 将棋駒の猛攻（Form2）。角/飛/龍が解禁され隊列に混ざる
#   shogi_drop  : 持ち駒打ち（Form2/3）。任意マスへ上/左/右/斜めから差し着駒して攻める
#   board_throw : 将棋盤を回転させて投げつける（Form3「ちゃぶ台返し」）
#   mega_beam   : 巨大破壊光線（チャージ警告→極太レーザー、Form3）
#   void_break  : 時空破壊。外周から収縮する弾＋内側から拡散する弾（Form3）
#   dash_knives : 高速移動と噛み合う刺し込み弾
#   curtain     : 画面を広く埋める終盤弾幕
# 将棋駒の駒種別の軌道は src/entities/bullets/shogi_bullet.py に定義（歩=直進ほか）
_PHASE_CONFIGS: dict[str | int, list[tuple]] = {
    1: [   # 悪寒大王インフルX（ステージ1 入門ボス）
        (1.00, "fan5",        1.7),
        (0.70, "fever_lunge", 1.25),
        (0.45, "cross",       0.9),
        (0.20, "dbl_aimed",   0.52),
    ],
    2: [   # 情報汚染超人野獣ブロリー（ステージ2 中級ボス）
        (1.00, "fan7",       1.28),
        (0.74, "mega_laser", 1.90),
        (0.54, "wall_gap",   0.72),
        (0.34, "burst3",     0.58),
        (0.16, "scatter",    0.28),
    ],
    3: [   # 婚活要塞マッチング・ゼロ（ステージ3 中上級ボス）
        (1.00, "drone_cross", 1.35),
        (0.72, "rock_fall",   1.10),
        (0.50, "wall_gap",    0.78),
        (0.30, "scatter",     0.34),
        (0.12, "spiral",      0.55),
    ],
    4: [   # 藤井竜王 Form1（ステージ4 ラスボス）
        (1.00, "shogi_file", 1.25),
        (0.72, "wall_gap",   0.86),
        (0.52, "spiral",     0.50),
        (0.32, "aimring8",   0.58),
        (0.15, "vortex2",    0.28),
    ],
    "4f2": [  # 藤井竜王 Form2（激難・角/飛/龍 解禁。将棋攻撃を主軸に）
        (1.00, "shogi_storm", 0.78),
        (0.80, "shogi_drop",  1.05),
        (0.62, "dash_knives", 0.55),
        (0.46, "shogi_storm", 0.72),
        (0.30, "vortex3",     0.36),
        (0.16, "shogi_drop",  0.95),
    ],
    "4f3": [  # 投了王サワグチ Form3（最終形態・盤面崩壊の大技）
        (1.00, "board_throw", 1.35),
        (0.82, "shogi_drop",  0.95),
        (0.64, "mega_beam",   1.90),
        (0.48, "void_break",  0.80),
        (0.30, "chaos",       0.22),
        (0.16, "vortex3",     0.18),
    ],
}

# ステージ別ボス設定: (image_path, scale, max_hp)
_BOSS_CONFIG = {
    1: ("graphic/enemy_バイキンマン68x80.png", 1.0,  80),
    2: ("graphic/enemy_ブロリー.png",          2.0, 200),
    3: ("graphic/boss_matching_zero_body.png", 0.25, 200),
    4: ("graphic/enemy_fujii4dan.png",         1.2, 250),
}

# 第二形態設定（ステージ4のみ）: (image_path, scale, max_hp)
_FORM2_CONFIG = {
    4: ("graphic/藤井四段第二形態_もう一度.png", 0.2266, 300),
}

# 第三形態（投了王サワグチ）: max_hp（スプライトはダミー生成）
#   ※専用画像なし。台本「澤口の影が巨大化」に沿いプレイヤー画像を暗紫・拡大したダミー。
_FORM3_MAX_HP   = 260   # Act1（反芻再生あり）
_FORM3_ACT2_HP  = 240   # Act2（最終ゲージ・反芻再生なし）
_FORM3_SCALE    = 2.4   # プレイヤー画像に対する拡大率（影が巨大化）

_TARGET_SX    = 580.0
_ENTER_SPEED  = 200.0
_MOVE_SPEED_Y = 100.0
_BOUNDS_TOP   = 60.0
_BOUNDS_BOT   = SCREEN_HEIGHT - 60.0
_BOUNDS_LEFT  = SCREEN_WIDTH * 0.48
_BOUNDS_RIGHT = SCREEN_WIDTH - 70.0
_BULLET_SPEED = 220.0

_MOVE_STYLES: dict[str | int, str] = {
    1:     "fever_lunge",  # 前に出てプレイヤーを押し込む
    2:     "heavy_laser",  # 重い横移動から大技レーザー
    3:     "fortress",     # 盤面を広く使う子機要塞
    4:     "shogi_board",  # 将棋盤の目を渡るように位置替え
    "4f2": "dash",         # 赤眼化後は急接近と離脱
    "4f3": "nightmare",    # 最終形態は画面全域を揺さぶる
}

# ─── ボス固有ギミック（ステージ/形態ごとに別特色）────────────────────
#   shield    : 周期シールド＋反撃。シールド中は無敵＋強攻撃、解除中が大ダメージ猶予。
#   weakpoint : 装甲＋弱点露出。装甲がある間は被ダメ無効、装甲を割ると弱点露出で被ダメ2倍。
#   turrets   : 地形・砲台連動。砲台を召喚、健在中は被ダメ減、全滅でスタン（被ダメ増）。
_GIMMICKS: dict[str | int, str] = {
    1:     "shield",     # 悪寒大王インフルX
    2:     "weakpoint",  # 情報汚染超人野獣ブロリー
    3:     "turrets",    # 婚活要塞マッチング・ゼロ
    4:     "shield",     # 藤井竜王 Form1
    "4f2": "weakpoint",  # 赤眼の真・藤井四段 Form2
    # Form3（投了王サワグチ）は専用スクリプト演出のためギミックなし
}

# shield ギミック
_SHIELD_VULN = 6.0    # 無防備（攻撃可能）時間（秒）
_SHIELD_DUR  = 3.0    # シールド展開（無敵）時間（秒）

# weakpoint ギミック
_ARMOR_MAX   = 40     # 装甲耐久（この分のダメージで割れる）
_WEAK_DUR    = 5.0    # 弱点露出時間（秒）
_WEAK_MULT   = 2.0    # 露出中の被ダメ倍率

# turrets ギミック
_TURRET_SUMMON_CD  = 9.0   # 砲台再召喚クールダウン（秒）
_TURRET_GUARD_MULT = 0.0   # 砲台健在中の被ダメ倍率（0=シールド中は本体無効）
_TURRET_STUN_DUR   = 4.0   # 全砲台撃破後のスタン時間（秒）
_TURRET_STUN_MULT  = 1.8   # スタン中の被ダメ倍率


class Boss(pygame.sprite.Sprite):
    def __init__(self, game: "Game", stage_id: int = 1) -> None:
        super().__init__()
        self.game      = game
        self._stage_id = stage_id
        self._form2    = False
        self._form3:   bool = False
        self._form3_act: int = 1     # 1=反芻再生あり / 2=最終ゲージ
        self._regen_enabled:   bool = False
        self._fakeout_used:    bool = False
        self._final_kill_armed: bool = False

        img_path, scale, max_hp = _BOSS_CONFIG.get(stage_id, _BOSS_CONFIG[1])
        self.image = self._load_image(img_path, scale)

        self.hp     = max_hp
        self.max_hp = max_hp

        self.sx: float = float(SCREEN_WIDTH + self.image.get_width())
        self.sy: float = SCREEN_HEIGHT / 2.0
        self.rect = self.image.get_rect(center=(int(self.sx), int(self.sy)))

        self._state:        str   = "enter"
        self._vy:           float = _MOVE_SPEED_Y
        self._shoot_timer:  float = 2.0
        self._spiral_angle: float = 0.0
        self._shot_variant: int   = 0
        self._time:         float = 0.0
        self.hit_flash_timer: float = 0.0   # 被弾時の白フラッシュ（game_scene が描画）

        # ── ギミック状態 ──────────────────────────────────────────
        # shield
        self._shield_active: bool  = False
        self._shield_timer:  float = _SHIELD_VULN
        # weakpoint
        self._armor:      int   = _ARMOR_MAX
        self._weak_timer: float = 0.0
        # turrets（game_scene が summon_turret_fn を注入。呼ぶと砲台リストを返す）
        self.summon_turret_fn = None           # Callable[[int], list] | None
        self._summoned: list   = []
        self._summon_cd:  float = 3.0
        self._stun_timer: float = 0.0
        self._shot_se_t:  float = -1.0   # 攻撃SEの再生間隔制御
        self._shoot_delay_override: float | None = None

    def _load_image(self, path: str, scale: float) -> pygame.Surface:
        raw = self.game.resources.image(path)
        if scale != 1.0:
            w = int(raw.get_width()  * scale)
            h = int(raw.get_height() * scale)
            return pygame.transform.smoothscale(raw, (w, h))
        return raw

    # ─────────────────────────────────────────
    def _form_key(self) -> str | int:
        if self._form3:
            return f"{self._stage_id}f3"
        if self._form2:
            return f"{self._stage_id}f2"
        return self._stage_id

    @property
    def _phase(self) -> tuple:
        key = self._form_key()
        phases = _PHASE_CONFIGS.get(key, _PHASE_CONFIGS[1])
        ratio  = self.hp / self.max_hp
        active = phases[0]
        for phase in phases:
            if ratio <= phase[0]:
                active = phase
        return active

    def _current_gimmick(self) -> str | None:
        """現在の形態に対応するギミック種別を返す（Form3 は None）。"""
        if self._form3:
            return None
        return _GIMMICKS.get(self._form_key())

    def _summoned_alive(self) -> int:
        self._summoned = [t for t in self._summoned if t.alive()]
        return len(self._summoned)

    def suppresses_hit_feedback(self) -> bool:
        """Return True when the current gimmick should absorb normal hit feedback."""
        gimmick = self._current_gimmick()
        if gimmick == "shield" and self._shield_active:
            return True
        if gimmick == "weakpoint" and self._weak_timer <= 0:
            return True
        if gimmick == "turrets" and self._summoned_alive() > 0:
            return True
        return False

    # ─────────────────────────────────────────
    def update(self, dt: float, enemy_bullets: pygame.sprite.Group, player: "Player") -> None:
        self._time += dt
        if self.hit_flash_timer > 0:
            self.hit_flash_timer -= dt
        if self._state == "enter":
            self.sx -= _ENTER_SPEED * dt
            if self.sx <= _TARGET_SX:
                self.sx    = _TARGET_SX
                self._state = "fight"
        else:
            gimmick   = self._current_gimmick()
            suppress  = self._update_gimmick(dt, gimmick, enemy_bullets, player)

            pattern = self._phase[1]
            self._update_movement(dt, player, pattern)

            self._shoot_timer -= dt
            if self._shoot_timer <= 0 and not suppress:
                self._shoot_delay_override = None
                self._shoot(enemy_bullets, player)
                self._shoot_timer = self._shoot_delay_override or self._phase[2]

        self.rect.center = (int(self.sx), int(self.sy))

    def _approach(self, current: float, target: float, speed: float, dt: float) -> float:
        step = speed * dt
        if current < target:
            return min(target, current + step)
        return max(target, current - step)

    def _approach_goal(self, sx: float, sy: float, speed: float, dt: float) -> None:
        sx = max(_BOUNDS_LEFT, min(_BOUNDS_RIGHT, sx))
        sy = max(_BOUNDS_TOP, min(_BOUNDS_BOT, sy))
        self.sx = self._approach(self.sx, sx, speed, dt)
        self.sy = self._approach(self.sy, sy, speed, dt)

    def _move_vertical(self, dt: float, pattern: str) -> None:
        speed_y = _MOVE_SPEED_Y * (2.0 if pattern in ("vortex2", "vortex3", "chaos", "scatter") else 1.0)
        self._vy = math.copysign(speed_y, self._vy)
        self.sy += self._vy * dt
        if self.sy >= _BOUNDS_BOT:
            self._vy = -abs(self._vy)
        elif self.sy <= _BOUNDS_TOP:
            self._vy = abs(self._vy)
        self.sx = self._approach(self.sx, _TARGET_SX, 120.0, dt)

    def _update_movement(self, dt: float, player: "Player", pattern: str) -> None:
        style = _MOVE_STYLES.get(self._form_key())
        mid_y = SCREEN_HEIGHT / 2.0

        if style == "fever_lunge":
            phase = self._time % 4.4
            lunging = 2.9 <= phase <= 3.35
            tx = 485.0 if lunging else _TARGET_SX
            wave_y = mid_y + math.sin(self._time * 1.05) * 125.0
            ty = wave_y * 0.85 + player.sy * 0.15
            self._approach_goal(tx, ty, 235.0 if lunging else 95.0, dt)

        elif style == "heavy_laser":
            tx = 612.0 + math.sin(self._time * 0.28) * 16.0
            ty = mid_y + math.sin(self._time * 0.42) * 70.0
            ty = ty * 0.82 + player.sy * 0.18
            self._approach_goal(tx, ty, 52.0, dt)

        elif style == "fortress":
            tx = 622.0 + math.sin(self._time * 0.24) * 10.0
            ty = mid_y + math.sin(self._time * 0.35) * 18.0
            self._approach_goal(tx, ty, 45.0, dt)

        elif style == "shogi_board":
            cols = (520.0, 600.0, 680.0)
            rows = (95.0, 195.0, 300.0, 405.0, 505.0)
            idx = int(self._time / 2.55)
            tx = cols[idx % len(cols)]
            ty = rows[(idx * 2 + self._shot_variant) % len(rows)]
            self._approach_goal(tx, ty, 112.0, dt)

        elif style == "dash":
            phase = self._time % 2.8
            if phase < 0.55:
                tx = 430.0
                ty = player.sy
                speed = 620.0
            else:
                tx = 650.0 + math.sin(self._time * 1.4) * 32.0
                ty = mid_y + math.sin(self._time * 2.0) * 210.0
                speed = 270.0
            self._approach_goal(tx, ty, speed, dt)

        elif style == "nightmare":
            tx = 590.0 + math.sin(self._time * 0.48) * 32.0
            ty = mid_y + math.sin(self._time * 0.72) * 82.0
            self._approach_goal(tx, ty, 90.0, dt)

        else:
            self._move_vertical(dt, pattern)

        self.sx = max(_BOUNDS_LEFT, min(_BOUNDS_RIGHT, self.sx))
        self.sy = max(_BOUNDS_TOP, min(_BOUNDS_BOT, self.sy))

    def _update_gimmick(self, dt: float, gimmick: str | None,
                        enemy_bullets: pygame.sprite.Group, player: "Player") -> bool:
        """ギミックの時間進行。射撃を止めるべきとき True を返す（スタン中など）。"""
        if gimmick == "shield":
            self._shield_timer -= dt
            if self._shield_timer <= 0:
                if self._shield_active:
                    self._shield_active = False
                    self._shield_timer  = _SHIELD_VULN
                else:
                    self._shield_active = True
                    self._shield_timer  = _SHIELD_DUR
                    # シールド展開と同時に強反撃（16方向リング）
                    for i in range(16):
                        a = math.radians(i * 22.5)
                        enemy_bullets.add(EnemyBullet(self.sx, self.sy,
                                                      math.cos(a) * 250, math.sin(a) * 250))
            return False

        if gimmick == "weakpoint":
            if self._weak_timer > 0:
                self._weak_timer -= dt
                if self._weak_timer <= 0:
                    self._armor = _ARMOR_MAX   # 露出終了で再装甲
            return False

        if gimmick == "turrets":
            if self._stun_timer > 0:
                self._stun_timer -= dt
                return True   # スタン中は射撃停止
            alive = self._summoned_alive()
            if alive == 0:
                if self._summoned:
                    # 直前まで居た砲台が全滅 → スタン突入
                    self._summoned = []
                    self._stun_timer = _TURRET_STUN_DUR
                    return True
                self._summon_cd -= dt
                if self._summon_cd <= 0 and self.summon_turret_fn is not None:
                    count = 3 if self._stage_id == 3 else 2
                    self._summoned = list(self.summon_turret_fn(count) or [])
                    self._summon_cd = _TURRET_SUMMON_CD
            return False

        return False

    def _aimed_dir(self, player: "Player") -> tuple[float, float]:
        dx = player.sx - self.sx
        dy = player.sy - self.sy
        d  = math.hypot(dx, dy) or 1
        return dx / d, dy / d

    def _rotated(self, nx: float, ny: float, deg: float, speed: float) -> tuple[float, float]:
        rad = math.radians(deg)
        ca, sa = math.cos(rad), math.sin(rad)
        return (nx * ca - ny * sa) * speed, (nx * sa + ny * ca) * speed

    def _font(self, size: int) -> pygame.font.Font:
        resources = getattr(self.game, "resources", None)
        if resources is not None and hasattr(resources, "pixelfont"):
            return resources.pixelfont(size)
        return pygame.font.Font(None, size)

    def _laser_bullet(self, by: float, *, warning: bool = False, height: int = 46,
                      warn_height: int = 12, damage: int = 18) -> EnemyBullet:
        width = max(80, int(self.sx - 18))
        h = warn_height if warning else height
        bullet = EnemyBullet(
            width / 2,
            by,
            0.0,
            0.0,
            0 if warning else damage,
            size=(width, h),
            color=(255, 230, 80) if warning else (255, 40, 55),
            lifetime=0.28 if warning else 0.58,
            terrain_passthrough=True,
            warning_only=warning,
        )
        bullet.image.fill((0, 0, 0, 0))
        if warning:
            if h > 24:   # 極太ビームの予告は本体の太さを薄く示す（回避用）
                pygame.draw.rect(bullet.image, (255, 110, 60, 46), (0, 0, width, h), border_radius=h // 2)
            pygame.draw.rect(bullet.image, (255, 235, 90, 150), (0, h // 2 - 2, width, 4))
            pygame.draw.rect(bullet.image, (255, 245, 160, 210), (0, h // 2 - 1, width, 2))
        else:
            pygame.draw.rect(bullet.image, (255, 35, 45, 120), (0, 0, width, h), border_radius=h // 2)
            pygame.draw.rect(bullet.image, (255, 235, 210, 240), (0, h // 2 - 5, width, 10), border_radius=5)
            pygame.draw.rect(bullet.image, (255, 100, 80, 190), (0, h // 2 - 15, width, 30), 2, border_radius=15)
        return bullet

    def _forward_aim(self, sx: float, sy: float, player: "Player", tilt: float) -> tuple[float, float]:
        """右端から左へ進む駒に、プレイヤー方向へ控えめな上下の傾きを与える。"""
        fy = max(-tilt, min(tilt, (player.sy - sy) / 300.0))
        d = math.hypot(-1.0, fy) or 1.0
        return -1.0 / d, fy / d

    def _rock_bullet(self, sx: float, vy: float, vx: float = 0.0) -> EnemyBullet:
        radius = random.randint(10, 17)
        bullet = EnemyBullet(
            sx,
            -radius,
            vx,
            vy,
            12,
            radius=radius,
            color=(126, 102, 76),
            lifetime=3.8,
            terrain_passthrough=True,
            hp=3,   # 撃墜可能（落石も撃ち落とせる）
        )
        bullet.image.fill((0, 0, 0, 0))
        pts = []
        for i in range(9):
            a = math.radians(i * 40 + random.uniform(-10, 10))
            r = radius * random.uniform(0.72, 1.08)
            pts.append((radius + math.cos(a) * r, radius + math.sin(a) * r))
        pygame.draw.polygon(bullet.image, (126, 102, 76), pts)
        pygame.draw.polygon(bullet.image, (190, 170, 132), pts, 2)
        return bullet

    # ── 将棋駒（Form1/2）─────────────────────────────────────────
    # 駒種 → (表示文字, 五角形塗り, 縁取り色, 文字色, 大きめか)
    _PIECE_DEFS: dict[str, tuple] = {
        "pawn":   ("歩", (222, 188, 120), (78, 50, 26),  (48, 24, 18), False),
        "lance":  ("香", (224, 196, 132), (120, 70, 24), (60, 32, 18), False),
        "knight": ("桂", (224, 196, 132), (120, 70, 24), (60, 32, 18), False),
        "silver": ("銀", (228, 204, 150), (96, 96, 110), (52, 52, 70), False),
        "gold":   ("金", (236, 212, 140), (150, 120, 40), (90, 66, 18), True),
        "bishop": ("角", (226, 200, 150), (54, 86, 150),  (34, 48, 96), False),
        "rook":   ("飛", (232, 200, 140), (150, 92, 30),  (74, 40, 18), True),
        "dragon": ("龍", (244, 206, 120), (188, 44, 44),  (150, 20, 20), True),
    }
    _PIECE_CACHE: dict[str, pygame.Surface] = {}

    def _piece_surface(self, kind: str) -> pygame.Surface:
        """上向きに描いた将棋駒のサーフェス（駒種ごとにキャッシュ）。"""
        cached = self._PIECE_CACHE.get(kind)
        if cached is not None:
            return cached
        label, fill, border, text_col, big = self._PIECE_DEFS.get(kind, self._PIECE_DEFS["pawn"])
        w, h = (36, 46) if big else (28, 35)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pts = ((w // 2, 1), (w - 2, int(h * 0.26)), (w - 4, h - 2), (4, h - 2), (2, int(h * 0.26)))
        pygame.draw.polygon(surf, fill, pts)
        pygame.draw.polygon(surf, border, pts, 2)
        txt = self._font(22 if big else 18).render(label, True, text_col)
        surf.blit(txt, ((w - txt.get_width()) // 2, (h - txt.get_height()) // 2 + 1))
        self._PIECE_CACHE[kind] = surf
        return surf

    def _spawn_piece(self, enemy_bullets: pygame.sprite.Group, sx: float, sy: float,
                     kind: str, *, speed: float, forward: tuple[float, float] = (-1.0, 0.0),
                     target=None, drop_target: tuple[float, float] | None = None,
                     incoming_speed: float = 0.0, incoming_time: float = 0.55) -> None:
        damage = 18 if kind in ("rook", "dragon", "gold") else 14
        enemy_bullets.add(ShogiBullet(
            sx, sy, self._piece_surface(kind),
            kind=kind, speed=speed, forward=forward, damage=damage, target=target,
            drop_target=drop_target, incoming_speed=incoming_speed, incoming_time=incoming_time,
        ))

    # 持ち駒打ちの飛来開始位置（指定マスへ「上/左/右/斜め」から差してくる）。
    def _drop_spawn(self, edge: str, tx: float, ty: float) -> tuple[float, float]:
        if edge == "top":
            return tx, -30.0
        if edge == "left":
            return -30.0, ty
        if edge == "right":
            return SCREEN_WIDTH + 30.0, ty
        if edge == "topleft":
            return tx - 220.0, -30.0
        if edge == "topright":
            return tx + 220.0, -30.0
        return SCREEN_WIDTH + 30.0, ty

    def _drop_telegraph(self, tx: float, ty: float, lifetime: float) -> EnemyBullet:
        """着駒予告のマス枠（warning_only＝無害・衝突対象外）。"""
        size = 44
        tele = EnemyBullet(tx, ty, 0.0, 0.0, 0, size=(size, size),
                           lifetime=lifetime, terrain_passthrough=True, warning_only=True)
        tele.image.fill((0, 0, 0, 0))
        pygame.draw.rect(tele.image, (255, 210, 120, 70), (0, 0, size, size), border_radius=4)
        pygame.draw.rect(tele.image, (255, 235, 160, 200), (0, 0, size, size), 2, border_radius=4)
        return tele

    def _draw_mini_piece(self, surf: pygame.Surface, cx: int, cy: int, label: str) -> None:
        """盤上に置かれた小さな駒（盤だと一目で分かるように）。"""
        w, h = 13, 16
        top = cy - h // 2
        pts = ((cx, top), (cx + w // 2, top + 4),
               (cx + w // 2 - 1, cy + h // 2), (cx - w // 2 + 1, cy + h // 2),
               (cx - w // 2, top + 4))
        pygame.draw.polygon(surf, (236, 200, 132), pts)
        pygame.draw.polygon(surf, (92, 58, 28), pts, 1)
        txt = self._font(12).render(label, True, (66, 36, 18))
        surf.blit(txt, (cx - txt.get_width() // 2, cy - txt.get_height() // 2))

    def _board_surface(self) -> pygame.Surface:
        """投げつける将棋盤。厚みのある木の盤＋9x9＋星＋盤上の駒で「盤」と分かるように。"""
        cached = self._PIECE_CACHE.get("__board__")
        if cached is not None:
            return cached
        size = 104
        pad = 9   # 盤の厚み（側面）分の余白
        surf = pygame.Surface((size + pad, size + pad), pygame.SRCALPHA)
        # 厚み（側面の木口）を右下にずらして 3D の盤に見せる。
        pygame.draw.rect(surf, (86, 52, 24, 255), (pad, pad, size, size), border_radius=6)
        pygame.draw.rect(surf, (60, 34, 16, 255), (pad, pad, size, size), 2, border_radius=6)
        # 盤面（榧色の明るい木目）。
        board = pygame.Rect(0, 0, size, size)
        pygame.draw.rect(surf, (214, 176, 112, 255), board, border_radius=6)
        pygame.draw.rect(surf, (120, 78, 36), board, 3, border_radius=6)
        inner = 9
        step = (size - inner * 2) / 9.0
        for i in range(10):
            p = int(inner + i * step)
            pygame.draw.line(surf, (96, 60, 28), (inner, p), (size - inner, p), 1)
            pygame.draw.line(surf, (96, 60, 28), (p, inner), (p, size - inner), 1)
        # 星（3・6 の交点）。
        for gi in (3, 6):
            for gj in (3, 6):
                pygame.draw.circle(surf, (70, 44, 20),
                                   (int(inner + gi * step), int(inner + gj * step)), 2)
        # 盤上に駒を数枚並べる。
        for label, gi, gj in (("歩", 2, 6), ("歩", 4, 6), ("飛", 1, 7), ("角", 7, 7), ("王", 4, 8)):
            self._draw_mini_piece(surf, int(inner + (gi + 0.5) * step),
                                  int(inner + (gj + 0.5) * step), label)
        self._PIECE_CACHE["__board__"] = surf
        return surf

    def _shoot(self, enemy_bullets: pygame.sprite.Group, player: "Player") -> None:
        nx, ny  = self._aimed_dir(player)
        pattern = self._phase[1]
        bx, by  = self.sx, self.sy
        spd     = _BULLET_SPEED
        variant = self._shot_variant
        self._shot_variant += 1
        spin_dir = -1 if variant % 2 else 1

        # 攻撃SE（dummy・連射で鳴り過ぎないよう間隔制御）
        if self._time - self._shot_se_t >= 0.25:
            self.game.sound.play_se_alias("SE_BOSS_SHOT", volume=0.4)
            self._shot_se_t = self._time

        # ── 5-way 扇形 ±40°（薄め）
        if pattern == "fan5":
            offset = -8 if variant % 2 else 8
            for deg in (-40, -20, 0, 20, 40):
                deg += offset
                vx, vy = self._rotated(nx, ny, deg, spd)
                enemy_bullets.add(EnemyBullet(bx, by, vx, vy))

        # ── 7-way 扇形 ±54°（広め）
        elif pattern == "fan7":
            offset = -6 if variant % 2 else 6
            for deg in (-54, -36, -18, 0, 18, 36, 54):
                deg += offset
                vx, vy = self._rotated(nx, ny, deg, spd * 1.05)
                enemy_bullets.add(EnemyBullet(bx, by, vx, vy))

        # ── 単発 超高速 狙い打ち
        elif pattern == "aimed":
            enemy_bullets.add(EnemyBullet(bx, by, nx * 420, ny * 420))

        # ── 2発 高速狙い打ち（±12°）
        elif pattern == "dbl_aimed":
            for deg in (-12, 12):
                vx, vy = self._rotated(nx, ny, deg, spd * 1.5)
                enemy_bullets.add(EnemyBullet(bx, by, vx, vy))

        # ── 8方向 全方位 等間隔
        elif pattern == "ring8":
            for i in range(8):
                a = math.radians(i * 45 + self._spiral_angle * 0.5)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * 200, math.sin(a) * 200))
            self._spiral_angle = (self._spiral_angle + spin_dir * 22.5) % 360

        # ── 12方向 全方位 等間隔
        elif pattern == "ring12":
            for i in range(12):
                a = math.radians(i * 30 + self._spiral_angle * 0.4)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * 210, math.sin(a) * 210))
            self._spiral_angle = (self._spiral_angle + spin_dir * 15) % 360

        # ── 16方向 全方位 高密度（激難）
        elif pattern == "ring16":
            for i in range(16):
                a = math.radians(i * 22.5 + self._spiral_angle * 0.6)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * 240, math.sin(a) * 240))
            self._spiral_angle = (self._spiral_angle + spin_dir * 11.25) % 360

        # ── 6方向 プレイヤー方向に位相合わせ + リング
        elif pattern == "aimring6":
            base = math.atan2(ny, nx)
            for i in range(6):
                a = base + math.radians(i * 60)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * (spd * 1.1), math.sin(a) * (spd * 1.1)))

        # ── 8方向 プレイヤー方向に位相合わせ
        elif pattern == "aimring8":
            base = math.atan2(ny, nx)
            for i in range(8):
                a = base + math.radians(i * 45)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * (spd * 1.15), math.sin(a) * (spd * 1.15)))

        # ── 12発 ランダム広角 散弾
        elif pattern == "scatter":
            base = math.atan2(ny, nx)
            count = 10 + (variant % 4)
            spread = 58 + (variant % 3) * 12
            for _ in range(count):
                a = base + math.radians(random.uniform(-spread, spread))
                s = spd * random.uniform(1.2, 1.9)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * s, math.sin(a) * s))

        # ── 十字気味 5-way
        elif pattern == "cross":
            for deg in (-90, -30, 0, 30, 90):
                vx, vy = self._rotated(nx, ny, deg, spd * 1.1)
                enemy_bullets.add(EnemyBullet(bx, by, vx, vy))

        # ── 6アームスパイラル
        elif pattern == "spiral":
            base = math.atan2(ny, nx)
            for i in range(6):
                a = base + math.radians(self._spiral_angle + i * 60)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * 255, math.sin(a) * 255))
            self._spiral_angle = (self._spiral_angle + spin_dir * 35) % 360

        # ── 2アームスパイラル（高速回転）
        elif pattern == "vortex2":
            base = math.atan2(ny, nx)
            for i in range(2):
                a = base + math.radians(self._spiral_angle + i * 180)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * 280, math.sin(a) * 280))
            # 同フレームで狙い打ちも追加（プレイヤーへのプレッシャー）
            enemy_bullets.add(EnemyBullet(bx, by, nx * 350, ny * 350))
            self._spiral_angle = (self._spiral_angle + spin_dir * 50) % 360

        # ── 3アームスパイラル（高速弾・激難）
        elif pattern == "vortex3":
            base = math.atan2(ny, nx)
            for i in range(3):
                a = base + math.radians(self._spiral_angle + i * 120)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * 295, math.sin(a) * 295))
            # 逆向き3アームも追加（交差する弾幕）
            for i in range(3):
                a = base - math.radians(self._spiral_angle + i * 120 + 60)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * 240, math.sin(a) * 240))
            self._spiral_angle = (self._spiral_angle + spin_dir * 45) % 360

        # ── カオス弾幕（aimring8 + ランダムオフセット + 狙い打ち）
        elif pattern == "chaos":
            base = math.atan2(ny, nx)
            # 8方向リング（ランダムオフセット付き）
            for i in range(8):
                a = base + math.radians(i * 45 + random.uniform(-8, 8))
                s = spd * random.uniform(1.1, 1.55)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * s, math.sin(a) * s))
            # 超高速狙い打ち
            enemy_bullets.add(EnemyBullet(bx, by, nx * 440, ny * 440))

        # ── 3連狙撃（速度差で回避タイミングをずらす）
        elif pattern == "burst3":
            for deg, speed in ((-10, 360), (0, 450), (10, 390)):
                vx, vy = self._rotated(nx, ny, deg + (-4 if variant % 2 else 4), speed)
                enemy_bullets.add(EnemyBullet(bx, by, vx, vy))

        # ── 縦の弾壁。毎回違う位置に抜け道を作る。
        elif pattern == "wall_gap":
            gap = 2 + (variant % 5) * 2
            for i in range(13):
                if gap <= i <= gap + 1:
                    continue
                vy = (i - 6) * 42.0
                enemy_bullets.add(EnemyBullet(bx, by, -270.0, vy))
            enemy_bullets.add(EnemyBullet(bx, by, nx * 340, ny * 340))

        # ── Stage1: 前進突き上げ。突進で距離を詰め、薄い扇と高速弾を重ねる。
        elif pattern == "fever_lunge":
            for deg in (-30, -15, 0, 15, 30):
                vx, vy = self._rotated(nx, ny, deg, spd * 1.22)
                enemy_bullets.add(EnemyBullet(bx, by, vx, vy, color=(255, 95, 75)))
            if variant % 2 == 0:
                enemy_bullets.add(EnemyBullet(bx - 28, by, nx * 430, ny * 430, color=(255, 210, 120)))

        # ── Stage2: 巨大レーザー。発射中/直後は弱点が開く。
        elif pattern == "mega_laser":
            if variant % 2 == 0:
                enemy_bullets.add(self._laser_bullet(by, warning=True))
                for off in (-56, 56):
                    enemy_bullets.add(EnemyBullet(bx, by + off, -165.0, off * 0.04, 8, radius=5, color=(255, 180, 80)))
                self._shoot_delay_override = 0.62
            else:
                enemy_bullets.add(self._laser_bullet(by))
                for off in (-88, 88):
                    enemy_bullets.add(EnemyBullet(bx, by + off, -330.0, off * 0.15, 12, radius=7, color=(255, 120, 70)))
                if self._current_gimmick() == "weakpoint":
                    self._weak_timer = max(self._weak_timer, 1.65)
                    self._armor = min(self._armor, _ARMOR_MAX // 2)
                self._shoot_delay_override = 2.55

        # ── Stage3: 砲台/子機の射線と交差する狙撃。
        elif pattern == "drone_cross":
            for origin_y in (by - 70.0, by + 70.0):
                dx = player.sx - bx
                dy = player.sy - origin_y
                d = math.hypot(dx, dy) or 1.0
                ox, oy = dx / d, dy / d
                for deg in (-24, 0, 24):
                    vx, vy = self._rotated(ox, oy, deg, spd * 1.25)
                    enemy_bullets.add(EnemyBullet(bx, origin_y, vx, vy, radius=6, color=(130, 210, 255)))
            for i in range(6):
                a = math.radians(i * 60 + self._spiral_angle)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * 185, math.sin(a) * 185, radius=5, color=(160, 180, 255)))
            self._spiral_angle = (self._spiral_angle + spin_dir * 30) % 360

        # ── Stage3/Form3: 落石。上から降る弾で横移動を要求する。
        elif pattern == "rock_fall":
            count = 6 + (variant % 3)
            for i in range(count):
                sx = 60.0 + i * (SCREEN_WIDTH - 120.0) / max(1, count - 1)
                sx += random.uniform(-28.0, 28.0)
                vx = random.uniform(-35.0, 35.0)
                vy = random.uniform(225.0, 315.0)
                enemy_bullets.add(self._rock_bullet(sx, vy, vx))
            if variant % 2 == 0:
                enemy_bullets.add(EnemyBullet(bx, by, nx * 360, ny * 360, radius=7, color=(205, 150, 95)))

        # ── Stage4 Form1: 将棋駒の隊列。歩が並んで直進し、たまに special が混じる。
        elif pattern == "shogi_file":
            rows = (90.0, 190.0, 290.0, 390.0, 490.0)
            gap = variant % len(rows)
            spd = 250.0
            # 特殊駒は最大1行だけ（無しの確率も高め＝歩の隊列が主役）。
            special_kind = None
            special_row = -1
            if random.random() < 0.55:
                special_kind = random.choices(
                    ("lance", "knight", "silver", "gold"), weights=(4, 4, 2, 2))[0]
                special_row = random.choice([i for i in range(len(rows)) if i != gap])
            for i, sy in enumerate(rows):
                if i == gap:
                    continue
                kind = special_kind if i == special_row and special_kind else "pawn"
                fwd = self._forward_aim(SCREEN_WIDTH + 18.0, sy, player, 0.5) if kind == "silver" else (-1.0, 0.0)
                self._spawn_piece(enemy_bullets, SCREEN_WIDTH + 18.0, sy, kind,
                                  speed=spd, forward=fwd, target=player)

        # ── Stage4 Form2: 角/飛/龍 解禁。歩の隊列に大駒の猛攻が重なる。
        elif pattern == "shogi_storm":
            rows = (80.0, 170.0, 260.0, 350.0, 440.0, 530.0)
            gap = variant % len(rows)
            spd = 285.0
            for i, sy in enumerate(rows):
                if i == gap:
                    continue
                kind = random.choices(("pawn", "lance", "knight"), weights=(6, 2, 2))[0]
                self._spawn_piece(enemy_bullets, SCREEN_WIDTH + 18.0, sy, kind,
                                  speed=spd, forward=(-1.0, 0.0), target=player)
            # 解禁された大駒（角=斜めジグザグ / 飛=高速直進 / 龍=追尾）を1〜2枚。
            for kind in random.choices(("bishop", "rook", "dragon"), weights=(4, 3, 2),
                                       k=1 + (variant % 2)):
                sy = random.uniform(100.0, SCREEN_HEIGHT - 100.0)
                fwd = self._forward_aim(SCREEN_WIDTH + 18.0, sy, player, 0.5) if kind == "rook" else (-1.0, 0.0)
                self._spawn_piece(enemy_bullets, SCREEN_WIDTH + 18.0, sy, kind,
                                  speed=spd, forward=fwd, target=player)

        # ── 持ち駒打ち: 任意のマスへ上/左/右/斜めから差し、ピシッと置いて攻める。
        elif pattern == "shogi_drop":
            grid_x = (150.0, 250.0, 350.0, 450.0, 540.0)
            grid_y = (130.0, 230.0, 330.0, 430.0, 500.0)
            edges = ("top", "left", "right", "topleft", "topright")
            pool = ("pawn", "pawn", "pawn", "lance", "knight",
                    "silver", "gold", "bishop", "rook", "dragon")
            incoming = 0.55
            for _ in range(2 + (variant % 2)):
                tx = random.choice(grid_x)
                ty = random.choice(grid_y)
                kind = random.choice(pool)
                sx, sy = self._drop_spawn(random.choice(edges), tx, ty)
                dist = math.hypot(tx - sx, ty - sy)
                enemy_bullets.add(self._drop_telegraph(tx, ty, incoming))
                self._spawn_piece(enemy_bullets, sx, sy, kind, speed=275.0, target=player,
                                  drop_target=(tx, ty), incoming_speed=dist / incoming,
                                  incoming_time=incoming)

        # ── Form3: 盤面ごと投げつける（投了王の「ちゃぶ台返し」）。
        elif pattern == "board_throw":
            board = self._board_surface()
            for _ in range(2 + (variant % 2)):
                ty = random.uniform(90.0, SCREEN_HEIGHT - 90.0)
                vx = -random.uniform(190.0, 250.0)
                vy = (ty - by) * 0.55 + random.uniform(-40.0, 40.0)
                enemy_bullets.add(ThrownBoardBullet(
                    bx - 30.0, by, board, vx=vx, vy=vy,
                    spin=random.choice((-220.0, 220.0)), damage=22))
            # 崩れた盤から散る駒。
            for _ in range(3):
                sy = random.uniform(60.0, SCREEN_HEIGHT - 60.0)
                self._spawn_piece(enemy_bullets, bx, sy, "pawn", speed=300.0,
                                  forward=(-1.0, 0.0), target=player)

        # ── Form3: 巨大破壊光線。チャージ警告 → 極太レーザー。
        elif pattern == "mega_beam":
            if variant % 2 == 0:
                enemy_bullets.add(self._laser_bullet(by, warning=True, warn_height=132))
                self._shoot_delay_override = 0.85
            else:
                enemy_bullets.add(self._laser_bullet(by, height=128, damage=24))
                for off in (-120, -60, 60, 120):
                    enemy_bullets.add(EnemyBullet(bx, by + off, -360.0, off * 0.1, 14,
                                                  radius=6, color=(255, 90, 70)))
                self._shoot_delay_override = 2.4

        # ── Form3: 時空破壊。外周から収縮する弾＋中心から拡散する弾。
        elif pattern == "void_break":
            cx, cy = SCREEN_WIDTH * 0.5, SCREEN_HEIGHT * 0.5
            for i in range(16):
                a = math.radians(i * 22.5 + self._spiral_angle)
                rx = cx + math.cos(a) * 360.0
                ry = cy + math.sin(a) * 280.0
                dx, dy = cx - rx, cy - ry
                d = math.hypot(dx, dy) or 1.0
                enemy_bullets.add(EnemyBullet(rx, ry, dx / d * 185.0, dy / d * 185.0,
                                              radius=5, color=(150, 40, 95)))
            for i in range(12):
                a = math.radians(i * 30 - self._spiral_angle)
                enemy_bullets.add(EnemyBullet(cx, cy, math.cos(a) * 210.0, math.sin(a) * 210.0,
                                              radius=5, color=(225, 60, 115)))
            self._spiral_angle = (self._spiral_angle + spin_dir * 18) % 360

        # ── Stage4 Form2: ダッシュと同時に刺し込む細い高速弾。
        elif pattern == "dash_knives":
            for deg in (-16, -6, 6, 16):
                vx, vy = self._rotated(nx, ny, deg, 455.0)
                enemy_bullets.add(EnemyBullet(bx, by, vx, vy, radius=4, color=(255, 70, 130)))
            for off in (-62, 62):
                dx = player.sx - bx
                dy = player.sy - (by + off)
                d = math.hypot(dx, dy) or 1.0
                enemy_bullets.add(EnemyBullet(bx, by + off, dx / d * 390.0, dy / d * 390.0, radius=5, color=(245, 110, 190)))

        # ── Form3: 画面を広く埋めるが、2レーン分の隙間を残す。
        elif pattern == "curtain":
            gap = 2 + (variant % 9)
            for i in range(15):
                if gap <= i <= gap + 1:
                    continue
                sy = 34.0 + i * 38.0
                vy = math.sin((i + variant) * 0.85) * 58.0
                enemy_bullets.add(EnemyBullet(SCREEN_WIDTH + 18.0, sy, -248.0, vy, radius=5, color=(180, 30, 72)))
            enemy_bullets.add(EnemyBullet(bx, by, nx * 420, ny * 420, radius=7, color=(255, 40, 80)))

    # ─────────────────────────────────────────
    def take_damage(self, amount: int) -> bool:
        # ── ギミックによる被ダメージ補正 ──────────────────────────
        gimmick = self._current_gimmick()
        dealt = amount
        if gimmick == "shield" and self._shield_active:
            return False   # シールド中は無敵（ダメージ無効）
        elif gimmick == "weakpoint":
            if self._weak_timer > 0:
                dealt = int(amount * _WEAK_MULT)   # 弱点露出中は大ダメージ
            else:
                self._armor -= amount              # 装甲を削る（HP は守られる）
                if self._armor <= 0:
                    self._armor = 0
                    self._weak_timer = _WEAK_DUR    # 装甲破壊 → 弱点露出
                dealt = 0
        elif gimmick == "turrets":
            if self._stun_timer > 0:
                dealt = int(amount * _TURRET_STUN_MULT)   # スタン中は被ダメ増
            elif self._summoned_alive() > 0:
                dealt = int(amount * _TURRET_GUARD_MULT)  # 砲台健在中は本体シールド
        if dealt > 0:
            self.hit_flash_timer = 0.08   # 被弾フラッシュ
        self.hp -= dealt
        if self._form3:
            # Form3 は game_scene のスクリプト演出が死を制御する。
            # Act2 で最終撃破がアームされている時のみ HP0 を許可。
            if self.hp <= 0:
                if self._form3_act == 2 and self._final_kill_armed:
                    return True
                self.hp = 1   # それ以外は 1 にクランプ（フェイクアウト/勧告で駆動）
            return False
        if self.hp <= 0:
            if self._stage_id == 4 and not self._form2:
                self._transform_form2()
                return False  # まだ死なない
            if self._stage_id == 4 and self._form2 and not self._form3:
                self._transform_form3()
                return False  # 投了王サワグチへ
            return True
        return False

    def _transform_form2(self) -> None:
        self._form2 = True
        img_path, scale, hp2 = _FORM2_CONFIG[4]
        self.image  = self._load_image(img_path, scale)
        self.rect   = self.image.get_rect(center=(int(self.sx), int(self.sy)))
        self.hp     = hp2
        self.max_hp = hp2
        self._shoot_timer  = 1.0
        self._spiral_angle = 0.0
        self._shot_variant = 0
        # Form2 は weakpoint ギミック。装甲を満タンで開始。
        self._shield_active = False
        self._armor         = _ARMOR_MAX
        self._weak_timer    = 0.0
        # SE なし（演出は game_scene 側の form2 検知で行う）

    def _make_form3_sprite(self) -> pygame.Surface:
        """投了王サワグチのダミースプライト（差し替え前提）。

        台本「澤口の影が巨大化」に沿い、プレイヤー画像を暗紫シルエット化＋拡大。
        """
        raw = self.game.resources.image("graphic/sawaguchi_49_64.png")
        w = int(raw.get_width()  * _FORM3_SCALE)
        h = int(raw.get_height() * _FORM3_SCALE)
        big = pygame.transform.smoothscale(raw, (w, h))
        shadow = pygame.Surface((w, h), pygame.SRCALPHA)
        # 赤い縁取り（自己否定の発光）をマスクから生成し、上下左右にずらして描く
        outline = pygame.mask.from_surface(big).to_surface(
            setcolor=(150, 20, 40, 255), unsetcolor=(0, 0, 0, 0))
        for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
            shadow.blit(outline, (ox, oy))
        # 暗紫トーンのシルエット化（元画像を暗紫で乗算）
        silhouette = big.copy()
        dark = pygame.Surface((w, h), pygame.SRCALPHA)
        dark.fill((40, 10, 55, 255))
        silhouette.blit(dark, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        shadow.blit(silhouette, (0, 0))
        # ダミー明示ラベル
        font = self.game.resources.pixelfont(14)
        tag = font.render("(DUMMY)", True, (255, 0, 255))
        shadow.blit(tag, (w // 2 - tag.get_width() // 2, 2))
        return shadow

    def _transform_form3(self) -> None:
        self._form3      = True
        self._form3_act  = 1
        self._regen_enabled = True
        self.image  = self._make_form3_sprite()
        self.rect   = self.image.get_rect(center=(int(self.sx), int(self.sy)))
        self.hp     = _FORM3_MAX_HP
        self.max_hp = _FORM3_MAX_HP
        self._shoot_timer  = 1.2
        self._spiral_angle = 0.0
        self._shot_variant = 0
        # 演出（バナー・セリフ）は game_scene の form3 検知で行う

    def regen(self, amount: int) -> None:
        """反芻再生: _regen_enabled のとき HP を回復（max クランプ）。"""
        if self._regen_enabled and self.hp < self.max_hp:
            self.hp = min(self.max_hp, self.hp + amount)

    def begin_act2(self, hp: int) -> None:
        """カロナール復帰後の最終ゲージ開始。反芻再生を停止する。"""
        self._form3_act     = 2
        self._regen_enabled = False
        self.hp     = hp
        self.max_hp = hp
        self._shoot_timer = 1.0
        self._spiral_angle = 0.0
        self._shot_variant = 0

    def arm_final_kill(self) -> None:
        """最終勧告後: 次の被弾で撃破できるようにする。"""
        self._final_kill_armed = True
        self.hp = 1
