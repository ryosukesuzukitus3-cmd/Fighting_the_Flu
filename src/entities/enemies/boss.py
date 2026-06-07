from __future__ import annotations
import math
import random
from typing import TYPE_CHECKING
import pygame
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.entities.bullets.enemy_bullet import EnemyBullet

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
_PHASE_CONFIGS: dict[str | int, list[tuple]] = {
    1: [   # 悪寒大王インフルX（ステージ1 入門ボス）
        (1.00, "fan5",      2.0),
        (0.70, "aimed",     1.3),
        (0.45, "ring8",     1.1),
        (0.20, "dbl_aimed", 0.55),
    ],
    2: [   # 情報汚染超人野獣ブロリー（ステージ2 中級ボス）
        (1.00, "fan7",      1.6),
        (0.65, "aimring6",  1.0),
        (0.35, "ring12",    0.75),
        (0.12, "scatter",   0.32),
    ],
    3: [   # 婚活要塞マッチング・ゼロ（ステージ3 中上級ボス）
        (1.00, "ring12",   1.5),
        (0.60, "aimring6", 0.9),
        (0.30, "scatter",  0.35),
        (0.12, "spiral",   0.60),
    ],
    4: [   # 藤井竜王 Form1（ステージ4 ラスボス）
        (1.00, "ring12",   1.5),
        (0.65, "spiral",   0.55),
        (0.35, "aimring8", 0.65),
        (0.15, "vortex2",  0.28),
    ],
    "4f2": [  # 藤井竜王 Form2（激難）
        (1.00, "vortex3", 0.38),
        (0.60, "ring16",  0.48),
        (0.25, "chaos",   0.20),
    ],
    "4f3": [  # 投了王サワグチ Form3（最終形態・赤黒弾幕）
        (1.00, "ring16",  0.55),
        (0.65, "chaos",   0.30),
        (0.30, "vortex3", 0.24),
    ],
}

# ステージ別ボス設定: (image_path, scale, max_hp)
_BOSS_CONFIG = {
    1: ("graphic/enemy_バイキンマン68x80.png", 1.0,  80),
    2: ("graphic/enemy_ブロリー.png",          1.2, 150),
    3: ("graphic/enemy_ブロリー.png",          1.2, 200),
    4: ("graphic/enemy_fujii4dan.png",         1.2, 250),
}

# 第二形態設定（ステージ4のみ）: (image_path, scale, max_hp)
_FORM2_CONFIG = {
    4: ("graphic/藤井四段第二形態_もう一度.png", 0.2266, 300),
}

# 第三形態（投了王サワグチ）: max_hp（スプライトはダミー生成）
#   ※専用画像なし。台本「澤口の影が巨大化」に沿いプレイヤー画像を暗紫・拡大したダミー。
_FORM3_MAX_HP   = 200   # Act1（反芻再生あり）
_FORM3_ACT2_HP  = 180   # Act2（最終ゲージ・反芻再生なし）
_FORM3_SCALE    = 2.4   # プレイヤー画像に対する拡大率（影が巨大化）

_TARGET_SX    = 580.0
_ENTER_SPEED  = 200.0
_MOVE_SPEED_Y = 100.0
_BOUNDS_TOP   = 60.0
_BOUNDS_BOT   = SCREEN_HEIGHT - 60.0
_BULLET_SPEED = 220.0

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
_TURRET_GUARD_MULT = 0.4   # 砲台健在中の被ダメ倍率
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

    def _load_image(self, path: str, scale: float) -> pygame.Surface:
        raw = self.game.resources.image(path)
        if scale != 1.0:
            w = int(raw.get_width()  * scale)
            h = int(raw.get_height() * scale)
            return pygame.transform.smoothscale(raw, (w, h))
        return raw

    # ─────────────────────────────────────────
    @property
    def _phase(self) -> tuple:
        if self._form3:
            key = f"{self._stage_id}f3"
        elif self._form2:
            key = f"{self._stage_id}f2"
        else:
            key = self._stage_id
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
        if self._form2:
            return _GIMMICKS.get(f"{self._stage_id}f2")
        return _GIMMICKS.get(self._stage_id)

    def _summoned_alive(self) -> int:
        self._summoned = [t for t in self._summoned if t.alive()]
        return len(self._summoned)

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
            speed_y = _MOVE_SPEED_Y * (2.0 if pattern in ("vortex2", "vortex3", "chaos", "scatter") else 1.0)
            self._vy = math.copysign(speed_y, self._vy)
            self.sy += self._vy * dt
            if self.sy >= _BOUNDS_BOT:
                self._vy = -abs(self._vy)
            elif self.sy <= _BOUNDS_TOP:
                self._vy = abs(self._vy)

            self._shoot_timer -= dt
            if self._shoot_timer <= 0 and not suppress:
                self._shoot(enemy_bullets, player)
                self._shoot_timer = self._phase[2]

        self.rect.center = (int(self.sx), int(self.sy))

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
                    self._summoned = list(self.summon_turret_fn(2) or [])
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

    def _shoot(self, enemy_bullets: pygame.sprite.Group, player: "Player") -> None:
        nx, ny  = self._aimed_dir(player)
        pattern = self._phase[1]
        bx, by  = self.sx, self.sy
        spd     = _BULLET_SPEED

        # 攻撃SE（dummy・連射で鳴り過ぎないよう間隔制御）
        if self._time - self._shot_se_t >= 0.25:
            self.game.sound.play_se_alias("SE_BOSS_SHOT", volume=0.4)
            self._shot_se_t = self._time

        # ── 5-way 扇形 ±40°（薄め）
        if pattern == "fan5":
            for deg in (-40, -20, 0, 20, 40):
                vx, vy = self._rotated(nx, ny, deg, spd)
                enemy_bullets.add(EnemyBullet(bx, by, vx, vy))

        # ── 7-way 扇形 ±54°（広め）
        elif pattern == "fan7":
            for deg in (-54, -36, -18, 0, 18, 36, 54):
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
            self._spiral_angle = (self._spiral_angle + 22.5) % 360

        # ── 12方向 全方位 等間隔
        elif pattern == "ring12":
            for i in range(12):
                a = math.radians(i * 30 + self._spiral_angle * 0.4)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * 210, math.sin(a) * 210))
            self._spiral_angle = (self._spiral_angle + 15) % 360

        # ── 16方向 全方位 高密度（激難）
        elif pattern == "ring16":
            for i in range(16):
                a = math.radians(i * 22.5 + self._spiral_angle * 0.6)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * 240, math.sin(a) * 240))
            self._spiral_angle = (self._spiral_angle + 11.25) % 360

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
            for _ in range(12):
                a = base + math.radians(random.uniform(-70, 70))
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
            self._spiral_angle = (self._spiral_angle + 35) % 360

        # ── 2アームスパイラル（高速回転）
        elif pattern == "vortex2":
            base = math.atan2(ny, nx)
            for i in range(2):
                a = base + math.radians(self._spiral_angle + i * 180)
                enemy_bullets.add(EnemyBullet(bx, by, math.cos(a) * 280, math.sin(a) * 280))
            # 同フレームで狙い打ちも追加（プレイヤーへのプレッシャー）
            enemy_bullets.add(EnemyBullet(bx, by, nx * 350, ny * 350))
            self._spiral_angle = (self._spiral_angle + 50) % 360

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
            self._spiral_angle = (self._spiral_angle + 45) % 360

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

    # ─────────────────────────────────────────
    def take_damage(self, amount: int) -> bool:
        self.hit_flash_timer = 0.08   # 被弾フラッシュ
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
                dealt = max(1, int(amount * _TURRET_GUARD_MULT))  # 砲台健在で被ダメ減
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

    def arm_final_kill(self) -> None:
        """最終勧告後: 次の被弾で撃破できるようにする。"""
        self._final_kill_armed = True
        self.hp = 1
