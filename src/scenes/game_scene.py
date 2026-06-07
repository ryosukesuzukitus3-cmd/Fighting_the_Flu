from __future__ import annotations
import math
import random
from pathlib import Path as _Path
import pygame

from src.core.scene import Scene
from src.core.camera import Camera
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.entities.background import ScrollingBackground
from src.entities.player import Player
from src.entities.hud import HUD
from src.entities.laser_beam import LaserBeam
from src.stages.stage import Stage
from src.stages.spawner import EnemySpawner
from src.entities.particle import ParticleSystem

# ミックスイン（各責務を分割管理）
from src.scenes.game.pause_mixin    import GameScenePauseMixin
from src.scenes.game.upgrade_mixin  import GameSceneUpgradeMixin
from src.scenes.game.overlay_mixin  import GameSceneOverlayMixin
from src.scenes.game.post_boss_mixin import GameScenePostBossMixin
from src.scenes.game.debug_mixin    import GameSceneDebugMixin

# ゲームシーン専用定数
from src.scenes.game.config import (
    DROP_CHANCE, MAGNET_CONFIG,
    STAGE_BANNER_DURATION,
    BOSS_NAMES, BOSS_NAME_DURATION, BOSS_BGM,
    BOSS_DIALOGUE_DURATION, BOSS_MID_LINE_DURATION,
    ALERT_DURATION, FIGHT_BANNER_DURATION,
    UPGRADE_SLOTS, random_item, ROUNDS_DIR,
    COMBO_WINDOW, COMBO_MIN, combo_multiplier,
)
# セリフ内容の SSOT
from src.story.script import (
    BOSS_INTRO, BOSS_MID, STAGE_BG_TEXT,
    BOSS_FORM3_INTRO, FINAL_SEQ, FINAL_BANNERS,
)
# 被ダメージ／反撃ダメージ定数
from src.core.balance import (
    PLAYER_DMG_ENEMY, PLAYER_DMG_BULLET, PLAYER_DMG_BOSS, PLAYER_DMG_TERRAIN,
    KARONARU_CONTACT_DMG,
)

# ボス演出シーケンス状態
# "" → alert → entering → boss_name → boss_dialogue → fight_banner → fighting
_BOSS_INTRO_FREEZE = {"boss_name", "boss_dialogue", "fight_banner"}


def _hit_rect_collide(player, other) -> bool:
    return player.hit_rect.colliderect(other.rect)


class GameScene(
    GameSceneDebugMixin,
    GameScenePostBossMixin,
    GameSceneOverlayMixin,
    GameSceneUpgradeMixin,
    GameScenePauseMixin,
    Scene,
):
    def __init__(self, game, stage_id: int = 1) -> None:
        super().__init__(game)
        self._stage_id       = stage_id
        self._is_debug_stage = (stage_id == 99)
        self._debug_panel    = None

    def on_enter(self) -> None:
        self.game.sound.stop_bgm()
        from src.entities.bullets.player_bullet import HomingBullet, PierceBullet
        HomingBullet._base_image = None
        PierceBullet._base_image = None

        self.camera  = Camera()
        self.bg      = ScrollingBackground(self._stage_id)
        self.player  = Player(self.game)
        self.hud     = HUD(self.game)
        self.stage   = Stage(self.game, stage_id=self._stage_id)
        self.laser   = LaserBeam()
        self.game.shared.stage = self._stage_id

        self.player_bullets: pygame.sprite.Group = pygame.sprite.Group()
        self.enemy_bullets:  pygame.sprite.Group = pygame.sprite.Group()
        self.enemies:        pygame.sprite.Group = pygame.sprite.Group()
        self.items:          pygame.sprite.Group = pygame.sprite.Group()
        self.terrain:        pygame.sprite.Group = pygame.sprite.Group()
        self.spawner = EnemySpawner(
            self.game, self.enemies, self.enemy_bullets,
            self.stage.events, self.player, stage_id=self._stage_id,
            terrain=self.terrain,
        )
        self._boss     = None
        self.particles = ParticleSystem()
        self._buf      = pygame.Surface(self.game.screen.get_size())

        # ポーズ
        self._paused       = False
        self._pause_font   = None
        self._pause_cursor = 0

        # ウェポン選択UI
        self._upgrading      = False
        self._upgrade_cursor = 0
        self._upgrade_font   = None
        self._weapon_tip_shown = False   # 初回 WeaponItem 取得時だけ強めの導線を出す

        # ステージ名バナー（スポーナーも BANNER_DURATION 間ロック）
        self._stage_banner_timer: float = STAGE_BANNER_DURATION
        self._stage_banner_font  = None
        self._stage_banner_sub_font = None

        # 背景の流れテキスト（§041/§051 ミーム・婚活UI）
        self._bg_text_pool:  list = STAGE_BG_TEXT.get(self._stage_id, [])
        self._bg_text_items: list = []
        self._bg_text_timer: float = 0.0
        self._bg_text_font   = None

        # 戦闘中自動タイムアウトセリフ（mid / form2）— 話者付き・キュー順送り
        self._boss_dialogue_timer:   float = 0.0
        self._boss_dialogue_text:    str   = ""
        self._boss_dialogue_speaker: str   = ""
        self._boss_dialogue_queue:   list  = []
        self._boss_dialogue_font   = None
        self._boss_mid_dialogue_shown: bool = False

        # ボス演出ステートマシン
        self._boss_intro_state: str   = ""
        self._boss_intro_timer: float = 0.0
        self._boss_name_text:   str   = ""
        self._boss_name_font    = None
        self._boss_name_label_font = None
        self._boss_intro_pages:    list      = []   # list[Line]
        self._boss_intro_page_idx: int       = 0
        self._intro_dialogue_font = None
        self._alert_font  = None
        self._fight_font  = None
        self._fight_sound_played: bool = False

        # ボス撃破後フェーズ
        self._post_boss          = False
        self._post_boss_timer    = 0.0
        self._post_boss_next_id: int | None = None
        self._post_boss_slow     = 1.0
        self._boss_boom_timers: list[float] = []
        self._boss_boom_x        = 0.0
        self._boss_boom_y        = 0.0
        self._hint_blink         = 0.0

        # 撃破後セリフ（post_boss_mixin が管理）
        self._defeat_dialogue_active: bool      = False
        self._defeat_dialogue_pages:  list[str] = []
        self._defeat_dialogue_index:  int       = 0
        self._defeat_dialogue_delay:  float     = 0.0
        self._defeat_dialogue_font    = None

        # ヒットストップ（撃破・フォーム遷移時に一瞬スロー）
        self._hitstop_timer: float = 0.0

        # 第二形態移行フラッシュ
        self._form2_flash_timer: float = 0.0
        # ラスボス撃破フラッシュ（閃光）
        self._boss_kill_flash_timer: float = 0.0
        # レーザー発射閃光
        self._laser_flash_timer: float = 0.0

        # ポップアップテキスト [(text, sx, sy, timer, color), ...]
        self._popups: list = []

        # 相棒（カロナール先輩）— karonaru_available のときのみ生成
        self._companion = None
        if self.game.story.karonaru_available:
            from src.entities.companion import Karonaru
            self._companion = Karonaru(self.game, popup_fn=self._spawn_popup)

        # 最終決戦（Form3 投了王サワグチ）スクリプト演出
        self._final_phase: int = 0     # 0=非Form3 / 1=Act1 / 2=Act2
        self._final_seq:   str = ""    # ""/fakeout/sengen/return/final_sengen/final_chance
        self._final_dialogue_pages:  list = []
        self._final_dialogue_idx:    int  = 0
        self._final_dialogue_active: bool = False
        self._final_dialogue_on_done = None
        self._final_dialogue_font    = None
        self._final_banner_text: tuple = ()
        self._final_banner_timer: float = 0.0
        self._sengen_overlay_timer: float = 0.0
        self._regen_timer: float = 0.0
        self._f3_act1_mid_shown:    bool = False
        self._f3_act2_mid_shown:    bool = False
        self._fakeout_triggered:    bool = False
        self._final_sengen_triggered: bool = False

        # コンボカウンター
        self._combo_count:       int   = 0
        self._combo_timer:       float = 0.0
        self._combo_pulse:       float = 0.0   # 更新時にズームパルス 0→1 で減衰
        self._combo_break_timer: float = 0.0   # "COMBO BREAK" 表示タイマー

        if __debug__:
            self._debug_invincible: bool = False

        # デバッグステージ専用パネル
        if self._is_debug_stage:
            from src.scenes.game.debug_stage_panel import DebugStagePanel
            self._debug_panel = DebugStagePanel(self.game, self)

        # スコア・残機初期化（ステージ1のみ）
        if self._stage_id == 1:
            self.game.shared.score      = 0
            self.game.shared.kill_count = 0
            self.game.shared.lives      = 3
            self.game.shared.carry_hp     = None
            self.game.shared.carry_weapon = None
            self.game.playlog.begin_run()

        self.game.playlog.log_stage_start(self._stage_id)
        self._stage_elapsed: float = 0.0

        # ステージ引き継ぎ復元
        carry = self.game.shared.take_carry()
        if carry:
            self.player.restore_state(carry[0], carry[1])

        # ステージ開始時のウェポン状態を保存（コンティニュー用）
        self.game.shared.stage_start_weapon = self.player.weapon.snapshot()

        # ラウンドSE → BGM 遅延スタート
        _next_stage_path = _Path("data") / "stages" / f"stage{self._stage_id + 1}.json"
        _is_final_stage  = not _next_stage_path.exists()
        if _is_final_stage:
            se_name = "music/rounds/final.wav"
        else:
            round_wav = ROUNDS_DIR / f"round{self._stage_id}.wav"
            se_name   = (f"music/rounds/round{self._stage_id}.wav"
                         if round_wav.exists() else "music/rounds/final.wav")
        round_se        = self.game.resources.sound(se_name)
        self.game.sound.play_se(se_name, volume=0.5)
        self._bgm_delay = round_se.get_length() + 0.3
        self._bgm_path  = f"music/bgm/{self.stage.bgm}" if self.stage.bgm else ""

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    # ── update ────────────────────────────────────────────────────
    def update(self, dt: float) -> None:
        # ヒットストップ: タイマー中は移動系 dt をほぼ 0 にして打撃感を出す
        if self._hitstop_timer > 0:
            self._hitstop_timer -= dt
            dt = dt * 0.06

        # BGM 遅延タイマー
        if self._bgm_delay > 0:
            self._bgm_delay -= dt
            if self._bgm_delay <= 0 and self._bgm_path:
                self.game.sound.play_bgm(self._bgm_path)

        # 演出タイマー
        if self._form2_flash_timer     > 0: self._form2_flash_timer     -= dt
        if self._boss_kill_flash_timer > 0: self._boss_kill_flash_timer -= dt
        if self._laser_flash_timer     > 0: self._laser_flash_timer     -= dt
        if self._stage_banner_timer    > 0: self._stage_banner_timer    -= dt
        if self._final_banner_timer    > 0: self._final_banner_timer    -= dt
        if self._sengen_overlay_timer  > 0: self._sengen_overlay_timer  -= dt
        self._tick_boss_dialogue(dt)
        if self._combo_pulse           > 0: self._combo_pulse           -= dt * 4.0
        if self._combo_break_timer     > 0: self._combo_break_timer     -= dt
        self._update_popups(dt)

        # コンボタイムアウト
        if self._combo_count > 0 and self._combo_timer > 0:
            self._combo_timer -= dt
            if self._combo_timer <= 0:
                if self._combo_count >= COMBO_MIN:
                    self._combo_break_timer = 0.9
                self._combo_count = 0
                self._combo_timer = 0.0

        inp = self.game.input

        # ポーズ切り替え
        if not self._upgrading and inp.is_action_just_pressed("pause"):
            self._paused = not self._paused
            self._pause_cursor = 0

        # ウェポン選択画面を開く（V キー・在庫がある時のみ）
        if (not self._upgrading and not self._paused
                and inp.is_action_just_pressed("weapon_select")
                and self.player.weapon.weapon_stock > 0):
            available = [i for i, (k, _) in enumerate(UPGRADE_SLOTS)
                         if self._is_upgrade_available(k)]
            if available:
                self._upgrading      = True
                self._upgrade_cursor = available[0]
                self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.5)

        if self._paused:
            self._update_pause()
            return

        if self._upgrading:
            self._update_upgrade_ui()
            return

        # ボス撃破後フェーズ
        if self._post_boss:
            self._update_post_boss_phase(dt)
            return

        # ── ボス演出ステートマシン ────────────────────────────
        if self._boss_intro_state != "" and self._boss_intro_state != "fighting":
            self._update_boss_intro(dt)

        # ── 常時更新（演出中も動かすもの）───────────────────
        self.camera.update(dt)
        self._update_bg_text(dt)

        # フリーズ中は最低限のみ更新（ボスは fighting に遷移してから動き始める）
        if self._boss_intro_state in _BOSS_INTRO_FREEZE:
            self.particles.update(dt)
            return

        # 最終決戦のスクリプトセリフ中は戦闘をフリーズ（ENTER 送り）
        if self._final_dialogue_active:
            self._update_final_dialogue()
            self.particles.update(dt)
            return

        # ── 通常 / alert / entering 共通更新 ─────────────────
        self._stage_elapsed += dt
        self.stage.update(dt)
        _panel_open = self._is_debug_stage and self._debug_panel is not None and self._debug_panel._open
        if not _panel_open:
            self.player.update(dt)
        if self._companion:
            self._companion.update(dt, self.player, self.player_bullets, self.camera, self.enemies)

        # スポーナー（バナー終了後 & ボス演出中はロック）
        if self._stage_banner_timer <= 0 and self._boss_intro_state == "":
            self.spawner.update(dt, self.camera)
        # alert/entering 中はスポーナー不動だがボス保留検知は行う

        # ボス保留検知 → ALERT 開始
        if self.spawner.boss_pending and self._boss_intro_state == "":
            self._boss_intro_state = "alert"
            self._boss_intro_timer = ALERT_DURATION
            self.camera.scroll_speed = 0.0
            self.game.sound.stop_bgm(fadeout_ms=800)
            self.laser.state = "ready"

        # ボス存在時の更新
        if self._boss is not None:
            if self._boss_intro_state == "entering":
                # 入場中: 移動はするが弾は空グループへ
                self._boss.update(dt, pygame.sprite.Group(), self.player)
                if self._boss._state == "fight":
                    self._start_boss_name()
            elif self._boss_intro_state == "fighting":
                self._boss.update(dt, self.enemy_bullets, self.player)

        # 通常射撃
        if self._boss_intro_state in ("", "fighting"):
            if self.player.shoot_requested:
                from src.entities.bullets.player_bullet import HomingBullet
                wx, wy = self.player.muzzle_world(self.camera)
                new_bullets = list(self.player.weapon.get_bullets(
                        wx, wy, self.enemies, game=self.game, boss=self._boss))
                for bullet in new_bullets:
                    self.player_bullets.add(bullet)
                if any(isinstance(b, HomingBullet) for b in new_bullets):
                    self.game.sound.play_se("music/se/ウェポン：missile_shot.mp3", volume=0.5)
                if any(not isinstance(b, HomingBullet) for b in new_bullets):
                    self.game.sound.play_se("music/se/ウェポン：normalshot_shot.mp3", volume=0.4)

            # レーザー
            if self.player.weapon.has_laser:
                msx, msy = self.player.muzzle_screen()
                self.laser.laser_level = self.player.weapon.laser_level
                _laser_was_ready = self.laser.state == "ready"
                just_fired, just_ended = self.laser.update(dt, self.player.laser_fire_held)
                if _laser_was_ready and self.laser.state == "charging":
                    self.game.sound.play_se("music/se/ウェポン：laser_charge.mp3", volume=0.75)
                if just_fired:
                    lv = self.player.weapon.laser_level
                    se = "music/se/ウェポン：laser1_shot.mp3" if lv <= 4 else "music/se/ウェポン：laser2_shot.mp3"
                    self.game.sound.play_se(se, volume=0.225)
                    self.camera.shake(6.0)
                    self._laser_flash_timer = 0.08
                if just_ended:
                    self.particles.spawn_hit(int(msx), int(msy))
                laser_killed, laser_hit = self.laser.hit_check(self.enemies, self._boss, msx, msy)
                for enemy in laser_killed:
                    self._on_enemy_killed(enemy)
                if laser_hit:
                    self.game.sound.play_se("music/se/ウェポン：laser_hit.mp3", volume=0.12)
                    self.camera.shake(1.2)
                    hx = int(msx + (SCREEN_WIDTH - msx) * random.uniform(0.3, 0.8))
                    self.particles.spawn_hit(hx, int(msy))
            else:
                self.laser.state = "ready"

        # 地形更新（スクロール・画面外除去）
        for ter in list(self.terrain):
            ter.update(dt, self.camera)
            if ter.is_off_left(self.camera):
                ter.kill()

        # 雑魚敵更新
        for enemy in list(self.enemies):
            enemy.update(dt, self.camera)
            if enemy.is_off_left(self.camera):
                enemy.kill()

        # アイテム更新 + マグネット
        mag_lv = self.player.weapon.magnet_level
        mag_range, mag_speed = MAGNET_CONFIG.get(mag_lv, (0, 0))
        for item in list(self.items):
            item.update(dt, self.camera)
            if mag_lv > 0:
                sx = self.camera.to_screen_x(item.world_x)
                dx = self.player.rect.centerx - sx
                dy = self.player.rect.centery - item.world_y
                dist = math.hypot(dx, dy)
                if dist < mag_range and dist > 0:
                    item.world_x += (dx / dist) * mag_speed * dt
                    item.world_y += (dy / dist) * mag_speed * dt

        self.particles.update(dt)

        for bullet in list(self.player_bullets):
            bullet.update(dt, self.camera)
            if bullet.is_off_screen(self.camera):
                bullet.kill()

        for bullet in list(self.enemy_bullets):
            bullet.update(dt)
            if bullet.is_off_screen():
                bullet.kill()

        # ボス中盤セリフ（HP 50%以下、fighting 中のみ）。Form3 は専用処理。
        if (self._boss is not None and self._boss_intro_state == "fighting"
                and self._final_phase == 0
                and not self._boss_mid_dialogue_shown
                and self._boss.hp / self._boss.max_hp <= 0.5):
            # Form2 中は専用キー、それ以外はステージ番号
            mid_key = "4f2mid" if getattr(self._boss, "_form2", False) else f"{self._stage_id}mid"
            if mid_key in BOSS_MID:
                self._enqueue_boss_dialogue(BOSS_MID[mid_key], BOSS_MID_LINE_DURATION)
                self._boss_mid_dialogue_shown = True

        # 最終決戦（Form3）: 反芻再生・しきい値演出
        if (self._boss is not None and self._boss_intro_state == "fighting"
                and self._final_phase > 0 and self._final_seq == ""):
            self._update_final_combat(dt)

        if self._process_collisions():
            return

        if __debug__:
            self._debug_handle_input()

        # デバッグステージ: パネル更新（開閉は Tab キー）
        if self._is_debug_stage and self._debug_panel is not None:
            self._debug_panel.update(dt)

    # ── ボス演出ステートマシン ────────────────────────────────
    def _update_boss_intro(self, dt: float) -> None:
        state = self._boss_intro_state
        inp   = self.game.input

        if state == "alert":
            self._boss_intro_timer -= dt
            if self._boss_intro_timer <= 0:
                self.spawner.confirm_spawn_boss()
                self._boss = self.spawner.boss
                # 砲台連動ギミック用の召喚コールバックを注入
                self._boss.summon_turret_fn = self._summon_boss_turrets
                self._boss_intro_state = "entering"

        elif state == "boss_name":
            self._boss_intro_timer -= dt
            if self._boss_intro_timer <= 0:
                # ボスセリフへ
                pages = BOSS_INTRO.get(self._stage_id, [])
                if pages:
                    self._boss_intro_pages    = pages
                    self._boss_intro_page_idx = 0
                    self._boss_intro_state    = "boss_dialogue"
                else:
                    self._start_fight_banner()

        elif state == "boss_dialogue":
            if (inp.is_held_with_repeat(pygame.K_RETURN, 0.25, 0.12)
                    or inp.is_held_with_repeat(pygame.K_SPACE, 0.25, 0.12)):
                self._boss_intro_page_idx += 1
                if self._boss_intro_page_idx >= len(self._boss_intro_pages):
                    self._start_fight_banner()

        elif state == "fight_banner":
            self._boss_intro_timer -= dt
            if self._boss_intro_timer <= 0:
                self._boss_intro_state = "fighting"

    def _start_boss_name(self) -> None:
        self._boss_name_text   = BOSS_NAMES.get(self._stage_id, "")
        self._boss_intro_state = "boss_name"
        self._boss_intro_timer = BOSS_NAME_DURATION
        self.game.sound.play_bgm(BOSS_BGM.get(self._stage_id, "music/bgm/決戦.mp3"))

    def _start_fight_banner(self) -> None:
        self._boss_intro_state = "fight_banner"
        self._boss_intro_timer = FIGHT_BANNER_DURATION
        if not self._fight_sound_played:
            self.game.sound.play_se("music/se/fight.wav", volume=0.5)
            self._fight_sound_played = True

    # ── draw ──────────────────────────────────────────────────────
    def draw(self, screen: pygame.Surface) -> None:
        buf = self._buf
        buf.fill((0, 0, 0))
        self.bg.draw(buf, self.camera.x)
        self._draw_bg_text(buf)
        self.terrain.draw(buf)
        self.items.draw(buf)
        self.player_bullets.draw(buf)
        self.enemy_bullets.draw(buf)
        self.enemies.draw(buf)
        if self._boss is not None:
            buf.blit(self._boss.image, self._boss.rect)
            # 被弾フラッシュ（白ティント加算）
            if getattr(self._boss, "hit_flash_timer", 0.0) > 0:
                tint = self._boss.image.copy()
                tint.fill((170, 170, 170), special_flags=pygame.BLEND_RGB_ADD)
                buf.blit(tint, self._boss.rect)
            self._draw_boss_gimmick(buf)
        self.particles.draw(buf)
        if self._companion:
            self._companion.draw(buf)
        self.player.draw(buf)

        if self.player.weapon.has_laser:
            msx, msy = self.player.muzzle_screen()
            self.laser.laser_level = self.player.weapon.laser_level
            self.laser.draw(buf, msx, msy)

        ox, oy = self.camera.shake_offset
        screen.blit(buf, (ox, oy))

        self.hud.draw(
            screen,
            self.player,
            self.game.shared.score,
            self.game.shared.kill_count,
            clear_goal=0,
            boss=self._boss,
            laser=self.laser if self.player.weapon.has_laser else None,
            lives=self.game.shared.lives,
        )

        self._draw_popups(screen)
        self._draw_combo(screen)

        # レーザー発射閃光
        if self._laser_flash_timer > 0:
            alpha = int(160 * (self._laser_flash_timer / 0.08))
            flash = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            lv = self.player.weapon.laser_level
            fc = (180, 240, 255) if lv <= 4 else (255, 180, 180)
            flash.fill((*fc, alpha))
            screen.blit(flash, (0, 0))

        # 第二形態フラッシュ
        if self._form2_flash_timer > 0:
            alpha = int(220 * (self._form2_flash_timer / 0.5))
            flash = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            flash.fill((255, 255, 255, alpha))
            screen.blit(flash, (0, 0))

        # ラスボス撃破フラッシュ（閃光）
        if self._boss_kill_flash_timer > 0:
            _FLASH_DUR = 1.2
            alpha = int(255 * (self._boss_kill_flash_timer / _FLASH_DUR))
            flash = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            flash.fill((255, 255, 255, alpha))
            screen.blit(flash, (0, 0))

        if self._paused:   self._draw_pause(screen)
        if self._upgrading: self._draw_upgrade_ui(screen)
        if self._post_boss: self._draw_post_boss_hint(screen)
        if self._defeat_dialogue_active: self._draw_defeat_dialogue(screen)

        if self._stage_banner_timer > 0:
            self._draw_stage_banner(screen)

        # ボス演出オーバーレイ
        s = self._boss_intro_state
        if s == "alert":         self._draw_alert(screen)
        elif s == "boss_name":   self._draw_boss_name(screen)
        elif s == "boss_dialogue": self._draw_boss_intro_dialogue(screen)
        elif s == "fight_banner": self._draw_fight_banner(screen)

        if self._boss_dialogue_timer > 0:
            self._draw_boss_dialogue(screen)

        # 最終決戦（Form3）オーバーレイ
        if self._sengen_overlay_timer > 0:
            self._draw_sengen_overlay(screen)
        if self._final_banner_timer > 0:
            self._draw_final_banner(screen)
        if self._final_dialogue_active:
            self._draw_final_dialogue(screen)

        if __debug__:
            self._debug_draw_overlay(screen)

        if self._is_debug_stage and self._debug_panel is not None:
            self._debug_panel.draw(screen)

    # ── 衝突処理 ──────────────────────────────────────────────────
    def _process_collisions(self) -> bool:
        from src.entities.bullets.player_bullet import HomingBullet
        hits = pygame.sprite.groupcollide(self.player_bullets, self.enemies, False, False)
        for bullet, hit_enemies in hits.items():
            hit_se = "music/se/ウェポン：missile_hit.mp3" if isinstance(bullet, HomingBullet) \
                     else "music/se/ウェポン：normalshot_hit.mp3"
            for enemy in hit_enemies:
                bx, by = bullet.rect.centerx, bullet.rect.centery
                if isinstance(bullet, HomingBullet):
                    self.particles.spawn_explosion(bx, by, color=(255, 160, 40), count=22)
                    self.camera.shake(3.0)
                else:
                    self.particles.spawn_hit(bx, by)
                    self.camera.shake(1.0)
                self.game.sound.play_se(hit_se, volume=0.4)
                if self._combo_count > 0:   # 命中している間はコンボ継続
                    self._combo_timer = COMBO_WINDOW
                if enemy.take_damage(bullet.damage):
                    self._on_enemy_killed(enemy)
            if not getattr(bullet, "piercing", False):
                bullet.kill()

        if self._boss is not None and self._boss_intro_state == "fighting":
            for bullet in list(self.player_bullets):
                if bullet.rect.colliderect(self._boss.rect):
                    hit_se = "music/se/ウェポン：missile_hit.mp3" if isinstance(bullet, HomingBullet) \
                             else "music/se/ウェポン：normalshot_hit.mp3"
                    bx, by = bullet.rect.centerx, bullet.rect.centery
                    if isinstance(bullet, HomingBullet):
                        self.particles.spawn_explosion(bx, by, color=(255, 160, 40), count=22)
                        self.particles.spawn_spark(bx, by, count=6)
                        self.camera.shake(4.0)
                    else:
                        self.particles.spawn_hit(bx, by)
                        self.particles.spawn_spark(bx, by, count=3)
                        self.camera.shake(1.5)
                    self.game.sound.play_se(hit_se, volume=0.3)
                    if self._combo_count > 0:   # ボスへの命中でもコンボ継続
                        self._combo_timer = COMBO_WINDOW
                    bullet.kill()
                    was_form2 = self._boss._form2
                    was_form3 = self._boss._form3
                    if self._boss.take_damage(bullet.damage):
                        self._on_boss_killed()
                        if not self._is_debug_stage:
                            return True
                        break  # デバッグステージ: ボス消去後は残弾処理を打ち切る
                    if self._boss is not None and not was_form2 and self._boss._form2:
                        self._on_form2_transition()
                    if self._boss is not None and not was_form3 and self._boss._form3:
                        self._on_form3_transition()

        if pygame.sprite.spritecollideany(self.player, self.enemies, _hit_rect_collide):
            self._damage_player(PLAYER_DMG_ENEMY)
            if self.player.hp <= 0 and not self._is_debug_stage:
                return True

        hit_bullet = pygame.sprite.spritecollideany(self.player, self.enemy_bullets, _hit_rect_collide)
        if hit_bullet is not None:
            self._damage_player(getattr(hit_bullet, "damage", PLAYER_DMG_BULLET))
            if self.player.hp <= 0 and not self._is_debug_stage:
                return True

        # ボス本体との接触ダメージ（戦闘中のみ）
        if (self._boss is not None and self._boss_intro_state == "fighting"
                and self.player.hit_rect.colliderect(self._boss.rect)):
            self._damage_player(PLAYER_DMG_BOSS)
            if self.player.hp <= 0 and not self._is_debug_stage:
                return True

        # 地形との接触ダメージ（i-frame で連続接触を間引く）
        if pygame.sprite.spritecollideany(self.player, self.terrain, _hit_rect_collide):
            self._damage_player(PLAYER_DMG_TERRAIN)
            if self.player.hp <= 0 and not self._is_debug_stage:
                return True

        # 相棒への敵/弾接触（ゲームオーバーとは独立）。被弾SEは companion.take_damage 内で再生。
        if self._companion and self._companion.is_active:
            for enemy in list(self.enemies):
                if self._companion.hit_rect.colliderect(enemy.rect):
                    self._companion.take_damage()
                    # 接触した敵にも反撃ダメージ。倒したら撃破処理。
                    if enemy.take_damage(KARONARU_CONTACT_DMG):
                        self._on_enemy_killed(enemy)
                    break
            if self._companion.is_active:
                for bullet in list(self.enemy_bullets):
                    if self._companion.hit_rect.colliderect(bullet.rect):
                        self._companion.take_damage()
                        bullet.kill()   # 被弾した弾は相殺
                        break

        from src.entities.items.weapon_item import WeaponItem
        for item in pygame.sprite.spritecollide(self.player, self.items, True):
            if isinstance(item, WeaponItem):
                # 即選択せず在庫に加算。V キーで選択画面を開いて消費する。
                self._pickup_weapon_item()
            else:
                item.apply(self.player)
                if getattr(item, "popup_text", None):
                    self._spawn_popup(item.popup_text,
                                      self.player.rect.centerx,
                                      self.player.rect.top - 10)

        return False

    # ── イベントハンドラ ──────────────────────────────────────────
    def _on_enemy_killed(self, enemy) -> None:
        sx = self.camera.to_screen_x(enemy.world_x)
        self.particles.spawn_explosion(sx, enemy.world_y)
        self.camera.shake(5.0)
        etype = type(enemy).__name__
        from src.core.registries import ENEMY_BY_NAME
        if etype in ENEMY_BY_NAME and ENEMY_BY_NAME[etype].se:
            d = ENEMY_BY_NAME[etype]
            self.game.sound.play_se(d.se, volume=d.se_volume)
        enemy.kill()
        # コンボ更新（ボス以外の雑魚のみカウント）
        self._combo_count += 1
        self._combo_timer  = COMBO_WINDOW
        self._combo_pulse  = 1.0
        mult = combo_multiplier(self._combo_count)
        self.game.shared.score      += 100 * mult
        self.game.shared.kill_count += 1
        self.game.sound.play_se("music/se/game_explosion9.mp3", volume=0.3)

        if etype == "EnemyBilly":
            from src.entities.items.weapon_item import WeaponItem
            from src.entities.items.heal import HealItem
            self.items.add(WeaponItem(
                enemy.world_x + random.uniform(-40, 40),
                enemy.world_y + random.uniform(-30, 30),
            ))
            for _ in range(8):
                self.items.add(HealItem(
                    enemy.world_x + random.uniform(-60, 60),
                    enemy.world_y + random.uniform(-40, 40),
                ))
        else:
            chance = DROP_CHANCE.get(etype, 0.20)
            if random.random() < chance:
                self.items.add(random_item(enemy.world_x, enemy.world_y))
            # レアドロップ: 残機アイテム (2%)
            if random.random() < 0.02:
                from src.entities.items.extra_life import ExtraLifeItem
                self.items.add(ExtraLifeItem(enemy.world_x, enemy.world_y))

    def _on_form2_transition(self) -> None:
        self.camera.shake(22.0)
        self._hitstop_timer = 0.14
        self.particles.spawn_big_explosion(self._boss.sx, self._boss.sy)
        self.enemy_bullets.empty()
        self.player._invincible_timer = max(self.player._invincible_timer, 2.5)
        self._form2_flash_timer = 0.5
        f2_key = f"{self._stage_id}f2"
        self._enqueue_boss_dialogue(BOSS_MID.get(f2_key, []), BOSS_MID_LINE_DURATION)
        # Form2 の HP50% mid を再び発火できるようにする
        self._boss_mid_dialogue_shown = False

    # ── 最終決戦（Form3 投了王サワグチ）────────────────────────────
    def _show_final_banner(self, key: str, duration: float = 2.6) -> None:
        self._final_banner_text  = FINAL_BANNERS.get(key, ())
        self._final_banner_timer = duration

    def _play_final_dialogue(self, pages: list, on_done) -> None:
        """list[Line] を ENTER 送りで再生し、終了後 on_done を呼ぶ（戦闘フリーズ）。"""
        self._final_dialogue_pages   = list(pages)
        self._final_dialogue_idx     = 0
        self._final_dialogue_active  = True
        self._final_dialogue_on_done = on_done

    def _update_final_dialogue(self) -> None:
        inp = self.game.input
        if (inp.is_held_with_repeat(pygame.K_RETURN, 0.25, 0.12)
                or inp.is_held_with_repeat(pygame.K_SPACE, 0.25, 0.12)):
            self._final_dialogue_idx += 1
            if self._final_dialogue_idx >= len(self._final_dialogue_pages):
                self._final_dialogue_active = False
                cb = self._final_dialogue_on_done
                self._final_dialogue_on_done = None
                if cb is not None:
                    cb()

    def _on_form3_transition(self) -> None:
        """Form2 撃破 → 投了王サワグチ登場。"""
        self.camera.shake(26.0)
        self._hitstop_timer = 0.18
        self.particles.spawn_big_explosion(self._boss.sx, self._boss.sy)
        self.enemy_bullets.empty()
        self.player._invincible_timer = max(self.player._invincible_timer, 2.5)
        self._boss_kill_flash_timer = 1.2   # 白閃光（暗転演出の代替）
        self.game.sound.stop_bgm(fadeout_ms=600)
        self.game.sound.play_bgm("music/bgm/決戦.mp3")
        self._final_phase = 1
        self._final_seq   = ""
        self._show_final_banner("true_final", 3.0)
        self._play_final_dialogue(BOSS_FORM3_INTRO, on_done=lambda: None)

    def _update_final_combat(self, dt: float) -> None:
        """Form3 戦闘中: 反芻再生・しきい値演出（_final_seq=='' のときのみ）。"""
        boss = self._boss
        if boss is None:
            return
        ratio = boss.hp / boss.max_hp

        if self._final_phase == 1:
            # 反芻再生（周期回復）
            if getattr(boss, "_regen_enabled", False):
                self._regen_timer -= dt
                if self._regen_timer <= 0.0:
                    self._regen_timer = 1.0
                    boss.regen(2)
            # HP60% 初回: 反芻再生の気づきセリフ（非ブロッキング）
            if not self._f3_act1_mid_shown and ratio <= 0.6:
                self._enqueue_boss_dialogue(BOSS_MID.get("4f3mid", []), BOSS_MID_LINE_DURATION)
                self._f3_act1_mid_shown = True
            # HP30% 初回: フェイクアウト → 投了勧告 → カロナール復帰
            if not self._fakeout_triggered and ratio <= 0.3:
                self._fakeout_triggered = True
                self._start_fakeout()
        elif self._final_phase == 2:
            # Act2 中盤セリフ（HP50%）
            if not self._f3_act2_mid_shown and ratio <= 0.5:
                self._enqueue_boss_dialogue(BOSS_MID.get("4f3act2mid", []), BOSS_MID_LINE_DURATION)
                self._f3_act2_mid_shown = True
            # HP を削りきった（1 にクランプ）→ 最終勧告・終局
            if not self._final_sengen_triggered and boss.hp <= 1:
                self._final_sengen_triggered = True
                self._start_final_sengen()

    def _start_fakeout(self) -> None:
        self._final_seq = "fakeout"
        self.enemy_bullets.empty()
        self.camera.shake(16.0)
        self._play_final_dialogue(FINAL_SEQ["fakeout"], on_done=self._start_sengen)

    def _start_sengen(self) -> None:
        # 投了王 HP を半分まで戻す復活演出
        if self._boss is not None:
            self._boss.hp = self._boss.max_hp // 2
        self._final_seq = "sengen"
        self._sengen_overlay_timer = 2.5
        self._show_final_banner("sengen", 2.6)
        self.player.hp = 1   # 回避不能 → 瀕死
        self.player._invincible_timer = max(self.player._invincible_timer, 3.0)
        self._play_final_dialogue(FINAL_SEQ["sengen"], on_done=self._start_karonaru_return)

    def _start_karonaru_return(self) -> None:
        self._final_seq = "return"
        self._boss_kill_flash_timer = 1.2   # 白閃光
        self.game.sound.play_bgm("music/bgm/Rebirth_the_edge.mp3", volume=0.7)   # 先輩復帰で盛り上がりBGMへ（音量0.7倍）
        self._show_final_banner("kouhatsu", 3.0)
        self.game.sound.play_se_alias("SE_LIGHT")
        self._play_final_dialogue(FINAL_SEQ["return"], on_done=self._do_karonaru_max)

    def _do_karonaru_max(self) -> None:
        # カロナール先輩・薬効最大で復帰
        if self._companion is None:
            from src.entities.companion import Karonaru
            self._companion = Karonaru(self.game, popup_fn=self._spawn_popup)
            self._companion.sx = float(self.player.rect.centerx) - 50.0
            self._companion.sy = float(self.player.rect.centery) + 16.0
        self._companion.set_max()
        # ストーリーフラグ更新（SCENE090）
        self.game.story.karonaru_lost        = False
        self.game.story.karonaru_available   = True
        self.game.story.karonaru_max         = True
        self.game.story.final_self_distanced = True
        # 抗反芻フィールド・最終ゲージ開始
        self._show_final_banner("anti_rumin", 3.0)
        from src.entities.enemies.boss import _FORM3_ACT2_HP
        if self._boss is not None:
            self._boss.begin_act2(_FORM3_ACT2_HP)
        self._final_phase = 2
        self._boss_mid_dialogue_shown = False
        self._play_final_dialogue(FINAL_SEQ["act2_start"], on_done=self._resume_final_combat)

    def _resume_final_combat(self) -> None:
        self._final_seq = ""

    def _start_final_sengen(self) -> None:
        self._final_seq = "final_sengen"
        self.enemy_bullets.empty()
        self._sengen_overlay_timer = 2.0
        self._show_final_banner("final_sengen", 2.6)
        self._play_final_dialogue(FINAL_SEQ["final_sengen"], on_done=self._arm_final_kill)

    def _arm_final_kill(self) -> None:
        if self._boss is not None:
            self._boss.arm_final_kill()
        self._final_seq = "final_chance"

    # ── 最終決戦 描画 ──────────────────────────────────────────────
    def _draw_sengen_overlay(self, screen: pygame.Surface) -> None:
        """投了勧告の赤黒全画面オーバーレイ（脈動）。"""
        pulse = 0.5 + 0.5 * math.sin(self._sengen_overlay_timer * 6.0)
        alpha = int(120 + 80 * pulse)
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        ov.fill((90, 0, 10, alpha))
        screen.blit(ov, (0, 0))

    def _draw_final_banner(self, screen: pygame.Surface) -> None:
        """技名・SYSTEM バナー（中央・複数行）。"""
        if not self._final_banner_text:
            return
        big   = self.game.resources.pixelfont(40)
        small = self.game.resources.pixelfont(22)
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2 - 120
        alpha = 255 if self._final_banner_timer > 0.4 else int(255 * (self._final_banner_timer / 0.4))
        for i, txt in enumerate(self._final_banner_text):
            font = big if i == 0 else small
            col  = (255, 80, 80) if i == 0 else (255, 210, 120)
            surf = font.render(txt, True, col)
            surf.set_alpha(alpha)
            screen.blit(surf, (cx - surf.get_width() // 2, cy + i * 46))

    def _draw_final_dialogue(self, screen: pygame.Surface) -> None:
        """最終決戦スクリプトセリフ（ENTER 送り）。"""
        if self._final_dialogue_font is None:
            self._final_dialogue_font = self.game.resources.pixelfont(26)
        pages = self._final_dialogue_pages
        idx   = self._final_dialogue_idx
        if not pages or idx >= len(pages):
            return
        line  = pages[idx]
        total = len(pages)

        box_h = 88
        box_y = SCREEN_HEIGHT - box_h - 20
        overlay = pygame.Surface((SCREEN_WIDTH - 40, box_h), pygame.SRCALPHA)
        overlay.fill((14, 0, 24, 220))
        pygame.draw.rect(overlay, (170, 60, 160, 210),
                         (0, 0, SCREEN_WIDTH - 40, box_h), 2, border_radius=6)
        screen.blit(overlay, (20, box_y))

        self._draw_speaker_nameplate(screen, line.speaker, 20, box_y)
        text_x = self._draw_speaker_portrait(screen, line.speaker, 20, box_y, box_h)

        surf = self._final_dialogue_font.render(line.text, True, (255, 235, 245))
        screen.blit(surf, (text_x, box_y + (box_h - surf.get_height()) // 2))

        hint_font = self.game.resources.pixelfont(16)
        if idx < total - 1:
            hint = hint_font.render(f"{idx + 1}/{total}  ENTER: 次へ", True, (180, 130, 190))
        else:
            hint = hint_font.render("ENTER: 続ける", True, (160, 200, 150))
        screen.blit(hint, (SCREEN_WIDTH - hint.get_width() - 28, box_y + box_h - hint.get_height() - 4))

    # ── 背景の流れテキスト（§041/§051）────────────────────────────
    def _update_bg_text(self, dt: float) -> None:
        if not self._bg_text_pool:
            return
        self._bg_text_timer -= dt
        if self._bg_text_timer <= 0:
            self._bg_text_timer = random.uniform(0.9, 1.8)
            self._bg_text_items.append({
                "text":  random.choice(self._bg_text_pool),
                "x":     float(SCREEN_WIDTH + 40),
                "y":     random.uniform(60, SCREEN_HEIGHT - 80),
                "vx":    random.uniform(-70, -40),
                "size":  random.choice((18, 22, 28, 36)),
            })
        for it in self._bg_text_items:
            it["x"] += it["vx"] * dt
        self._bg_text_items = [it for it in self._bg_text_items if it["x"] > -400]

    def _draw_bg_text(self, surf: pygame.Surface) -> None:
        if not self._bg_text_items:
            return
        for it in self._bg_text_items:
            font = self.game.resources.pixelfont(it["size"])
            txt  = font.render(it["text"], True, (70, 70, 95))
            txt.set_alpha(70)
            surf.blit(txt, (int(it["x"]), int(it["y"])))

    # ── 戦闘中セリフ（話者付き・自動順送り）────────────────────────
    def _enqueue_boss_dialogue(self, lines: list, line_duration: float | None = None) -> None:
        """Line のリストを順送り表示する。1 行目を即表示し残りをキューへ。"""
        if not lines:
            return
        self._boss_dialogue_line_dur = line_duration or BOSS_DIALOGUE_DURATION
        self._boss_dialogue_queue    = list(lines[1:])
        first = lines[0]
        self._boss_dialogue_speaker  = first.speaker
        self._boss_dialogue_text     = first.text
        self._boss_dialogue_timer    = self._boss_dialogue_line_dur

    def _tick_boss_dialogue(self, dt: float) -> None:
        """戦闘中セリフのタイマー更新。期限切れでキューの次行へ。"""
        if self._boss_dialogue_timer <= 0:
            return
        self._boss_dialogue_timer -= dt
        if self._boss_dialogue_timer <= 0 and self._boss_dialogue_queue:
            nxt = self._boss_dialogue_queue.pop(0)
            self._boss_dialogue_speaker = nxt.speaker
            self._boss_dialogue_text    = nxt.text
            self._boss_dialogue_timer   = getattr(self, "_boss_dialogue_line_dur", BOSS_DIALOGUE_DURATION)

    def _draw_boss_gimmick(self, buf: pygame.Surface) -> None:
        """ボスのギミック状態（シールド/装甲/弱点露出/砲台/スタン）を可視化する。
        図形に加え、状態が一目で分かる短いラベルをボス頭上に表示する。"""
        b = self._boss
        cx, cy = b.rect.center
        r = max(b.rect.width, b.rect.height) // 2 + 10
        gimmick = b._current_gimmick() if hasattr(b, "_current_gimmick") else None
        if gimmick is None or getattr(b, "_state", "fight") != "fight":
            return

        label = ""        # 頭上ラベル
        lcol  = (255, 220, 60)

        if gimmick == "shield":
            if getattr(b, "_shield_active", False):
                ring = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
                pygame.draw.circle(ring, (80, 200, 255, 90), (r + 3, r + 3), r)
                pygame.draw.circle(ring, (160, 230, 255, 220), (r + 3, r + 3), r, 3)
                buf.blit(ring, (cx - r - 3, cy - r - 3))
                label, lcol = "SHIELD", (160, 230, 255)
            else:
                label, lcol = "BREAK CHANCE!", (120, 255, 140)

        elif gimmick == "weakpoint":
            if getattr(b, "_weak_timer", 0.0) > 0:
                glow = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 60, 60, 120), (r + 3, r + 3), r, 5)
                buf.blit(glow, (cx - r - 3, cy - r - 3))
                label, lcol = "WEAK POINT!", (255, 90, 90)
            else:
                label, lcol = "ARMOR", (180, 190, 210)
                self._draw_armor_gauge(buf, b, cx, b.rect.top - 30)

        elif gimmick == "turrets":
            if getattr(b, "_stun_timer", 0.0) > 0:
                label, lcol = "STUN  DAMAGE UP", (255, 220, 60)
            else:
                n = b._summoned_alive() if hasattr(b, "_summoned_alive") else 0
                if n > 0:
                    label, lcol = f"TURRET GUARD x{n}", (160, 200, 255)

        if label:
            surf = self.game.resources.pixelfont(20).render(label, True, lcol)
            buf.blit(surf, (cx - surf.get_width() // 2, b.rect.top - 26))

    def _draw_armor_gauge(self, buf: pygame.Surface, b, cx: int, y: int) -> None:
        """weakpoint ギミックの装甲残量を小ゲージで表示。"""
        from src.entities.enemies.boss import _ARMOR_MAX
        w, h = 80, 6
        ratio = max(0.0, min(1.0, getattr(b, "_armor", 0) / _ARMOR_MAX))
        x = cx - w // 2
        pygame.draw.rect(buf, (40, 44, 54), (x, y, w, h), border_radius=2)
        pygame.draw.rect(buf, (150, 170, 200), (x, y, int(w * ratio), h), border_radius=2)
        pygame.draw.rect(buf, (90, 100, 120), (x, y, w, h), 1, border_radius=2)

    def _summon_boss_turrets(self, n: int) -> list:
        """ボス（砲台連動ギミック）用に砲台を召喚し、enemies グループへ追加して返す。"""
        from src.entities.enemies.turret import EnemyTurret
        spawned = []
        for i in range(n):
            wx = self.camera.spawn_x(margin=-120)   # 画面内右寄りに出現
            wy = 110.0 + i * (SCREEN_HEIGHT - 220.0) / max(1, n - 1) if n > 1 else SCREEN_HEIGHT / 2
            t = EnemyTurret(self.game, wx, wy, self.enemy_bullets, self.player)
            self.enemies.add(t)
            spawned.append(t)
        return spawned

    def _damage_player(self, amount: int = PLAYER_DMG_BULLET) -> None:
        if self.player.is_invincible:
            return
        if self.player.weapon.barrier_block():
            self.game.sound.play_se("music/se/hit.wav", volume=0.9)
            self.particles.spawn_hit(int(self.player.sx), int(self.player.sy))
            self.camera.shake(4.0)
            self.player._invincible_timer = 0.8
            return
        self.player.take_damage(amount)
        self.particles.spawn_player_hit(self.player.sx, self.player.sy)
        self.camera.shake(10.0)
        # 反芻再生: Act1 で澤口が被弾するとボスが回復する（後悔をエネルギーに）
        if (self._boss is not None and self._final_phase == 1
                and getattr(self._boss, "_regen_enabled", False)):
            self._boss.regen(15)
        if self.player.hp <= 0:
            self._go_gameover()
        else:
            self.game.sound.play_se("music/se/shout.wav", volume=0.6)

    def _pickup_weapon_item(self) -> None:
        """WeaponItem 取得＝在庫+1。初回だけ強めの導線ポップアップを出す。"""
        self.player.weapon.weapon_stock += 1
        wsel = self.game.settings.key_display("weapon_select")
        px, py = self.player.rect.centerx, self.player.rect.top - 10
        if not self._weapon_tip_shown:
            self._weapon_tip_shown = True
            self._spawn_popup(f"WEAPON STOCK +1   {wsel}キーで強化を選択!",
                              px, py, color=(120, 230, 255), life=3.0)
        else:
            self._spawn_popup(f"WEAPON +1  [{wsel}]", px, py)

    # ── ポップアップテキスト ──────────────────────────────────────
    def _spawn_popup(self, text: str, sx: int, sy: int,
                     color: tuple = (255, 230, 60), life: float = 1.4) -> None:
        self._popups.append([text, float(sx), float(sy), life, color])

    def _update_popups(self, dt: float) -> None:
        for p in self._popups:
            p[3] -= dt
            p[2] -= 35.0 * dt   # 上に流れる
        self._popups = [p for p in self._popups if p[3] > 0]

    def _draw_popups(self, screen: pygame.Surface) -> None:
        font = self.game.resources.pixelfont(24)
        for text, sx, sy, timer, color in self._popups:
            alpha = min(255, int(timer / 1.4 * 255 + 80))
            surf  = font.render(text, True, color)
            surf.set_alpha(alpha)
            screen.blit(surf, (int(sx) - surf.get_width() // 2, int(sy)))

    def _draw_combo(self, screen: pygame.Surface) -> None:
        # COMBO BREAK 表示
        if self._combo_break_timer > 0:
            alpha = int(255 * min(1.0, self._combo_break_timer / 0.3))
            f = self.game.resources.pixelfont(28)
            s = f.render("COMBO BREAK", True, (180, 180, 180))
            s.set_alpha(alpha)
            screen.blit(s, (SCREEN_WIDTH // 2 - s.get_width() // 2, 55))
            return

        if self._combo_count < COMBO_MIN:
            return

        mult  = combo_multiplier(self._combo_count)
        pulse = max(0.0, self._combo_pulse)
        fsize = int(26 + 10 * pulse)
        font  = self.game.resources.pixelfont(fsize)

        # 倍率に応じた色
        if   mult >= 8: color = (255,  80,  80)
        elif mult >= 4: color = (255, 160,  40)
        elif mult >= 2: color = (255, 220,  60)
        else:           color = (200, 255, 180)

        label = f"{self._combo_count} COMBO!"
        if mult > 1:
            label += f"  ×{mult}"
        surf = font.render(label, True, color)
        cx   = SCREEN_WIDTH // 2
        cy   = 58
        screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))

        # タイマーバー（コンボウィンドウの残り時間）
        bar_w   = 160
        bar_h   = 5
        ratio   = max(0.0, self._combo_timer / COMBO_WINDOW)
        bar_x   = cx - bar_w // 2
        bar_y   = cy + surf.get_height() // 2 + 4
        # 背景
        pygame.draw.rect(screen, (60, 60, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
        # 残り
        fill_w = int(bar_w * ratio)
        if fill_w > 0:
            bar_color = (int(255 * (1 - ratio)), int(220 * ratio), 40)
            pygame.draw.rect(screen, bar_color, (bar_x, bar_y, fill_w, bar_h), border_radius=2)

    def _go_gameover(self) -> None:
        if self._is_debug_stage:
            self.player.hp = self.player.max_hp
            self.player._invincible_timer = 2.0
            return
        self.game.playlog.log_player_death(
            self._stage_id,
            self._stage_elapsed,
            self.player.hp,
            self.player.weapon.snapshot(),
        )
        self.game.playlog.end_run(
            cleared=False,
            score=self.game.shared.score,
            kill_count=self.game.shared.kill_count,
        )
        self.game.sound.stop_bgm()
        self.game.sound.play_se("music/se/gameover.mp3")
        from src.scenes.gameover import GameOverScene
        self.game.change_scene(GameOverScene(self.game))
