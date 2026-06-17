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
from src.scenes.dialogue_panel import COMBAT_PURPLE_STYLE, draw_combat_panel

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
# "" -> alert -> entering -> boss_name -> boss_dialogue -> fight_banner -> fighting
_BOSS_INTRO_FREEZE = {"boss_name", "boss_dialogue", "fight_banner"}
_BOSS_GATE_ENEMIES = {"EnemyBilly", "EnemyCoughSprayer", "EnemySporeSplitter"}


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
        self._stage_scroll_speed = self.camera.scroll_speed
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
            world_events=self.stage.world_events,
        )
        self.spawner.spawn_terrain_events(self.stage.terrain_layout, self.camera)
        self._boss_terrain_spawned = False
        self._pending_boss_stage_id: int | None = None
        self._active_boss_stage_id: int | None = None
        self._boss     = None
        self._boss_wait_notice_timer = 0.0
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
        self._weapon_tip_shown = False
        self._stage_banner_timer: float = STAGE_BANNER_DURATION
        self._stage_banner_font  = None
        self._stage_banner_sub_font = None

        self._bg_text_pool:  list = STAGE_BG_TEXT.get(self._stage_id, [])
        self._bg_text_items: list = []
        self._bg_text_timer: float = 0.0
        self._bg_text_font   = None

        # 戦闘中自動タイムアウトセリフ
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

        self._defeat_dialogue_active: bool      = False
        self._defeat_dialogue_pages:  list[str] = []
        self._defeat_dialogue_index:  int       = 0
        self._defeat_dialogue_delay:  float     = 0.0
        self._defeat_dialogue_font    = None

        self._hitstop_timer: float = 0.0

        # 第二形態移行フラッシュ
        self._form2_flash_timer: float = 0.0
        self._boss_kill_flash_timer: float = 0.0
        self._laser_flash_timer: float = 0.0

        # ポップアップテキスト
        self._popups: list = []

        # 相棒（カロナール先輩）
        self._companion = None
        if self.game.story.karonaru_available:
            from src.entities.companion import Karonaru
            self._companion = Karonaru(self.game, popup_fn=self._spawn_popup,
                                       spawn_heal_fn=self._companion_spawn_heal)

        # 最終決戦（Form3 投了王サワグチ）
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
        self._karonaru_return_timer: float = 0.0
        self._karonaru_return_from: tuple[float, float] = (0.0, 0.0)
        self._karonaru_return_to: tuple[float, float] = (0.0, 0.0)
        self._karonaru_arrival_timer: float = 0.0
        self._karonaru_arrival_pos: tuple[float, float] = (0.0, 0.0)
        self._karonaru_arrival_duration: float = 0.0
        self._karonaru_arrival_from: tuple[float, float] = (0.0, 0.0)
        self._karonaru_arrival_to: tuple[float, float] = (0.0, 0.0)
        self._karonaru_arrival_trail: list[tuple[float, float, float]] = []

        self._player_prev_rect = self.player.rect.copy()

        # コンボカウンター
        self._combo_count:       int   = 0
        self._combo_timer:       float = 0.0
        self._combo_pulse:       float = 0.0   # 更新時にズームパルス 0->1 で減衰
        self._combo_break_timer: float = 0.0

        if __debug__:
            self._debug_invincible: bool = False

        # デバッグステージ専用パネル
        if self._is_debug_stage:
            from src.scenes.game.debug_stage_panel import DebugStagePanel
            self._debug_panel = DebugStagePanel(self.game, self)

        if self._stage_id == 1:
            self.game.shared.score      = 0
            self.game.shared.kill_count = 0
            self.game.shared.lives      = 3
            self.game.shared.carry_hp     = None
            self.game.shared.carry_weapon = None
            self.game.playlog.begin_run()

        if not self._is_debug_stage:
            self.game.playlog.log_stage_start(self._stage_id)
        self._stage_elapsed: float = 0.0

        carry = self.game.shared.take_carry()
        if carry:
            self.player.restore_state(carry[0], carry[1])

        self.game.shared.stage_start_weapon = self.player.weapon.snapshot()

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

    def _boss_stage_id(self) -> int:
        return self._active_boss_stage_id or self._pending_boss_stage_id or self._stage_id

    def _queue_boss_spawn(self, stage_id: int | None = None) -> None:
        self._pending_boss_stage_id = self._stage_id if stage_id is None else stage_id
        self.spawner.skip_all_events()
        self.spawner.boss_pending = True

    def _boss_stage_data(self, stage_id: int) -> Stage:
        if stage_id == self._stage_id:
            return self.stage
        return Stage(self.game, stage_id=stage_id)

    def _replace_boss_terrain(self, stage_id: int) -> None:
        boss_stage = self._boss_stage_data(stage_id)
        self.terrain.empty()
        self.spawner.spawn_terrain_events(boss_stage.boss_terrain, self.camera)

    def _prepare_boss_terrain(self, stage_id: int) -> None:
        boss_stage = self._boss_stage_data(stage_id)
        preplaced_here = (
            stage_id == self._stage_id
            and boss_stage.boss_terrain_mode == "preplaced"
        )
        if not preplaced_here:
            self._replace_boss_terrain(stage_id)
        self._boss_terrain_spawned = True

    # ── update ────────────────────────────────────────────────────
    def update(self, dt: float) -> None:
        # Hitstop slows movement updates for a short impact moment.
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
        if self._karonaru_arrival_timer > 0:
            self._update_karonaru_arrival_motion(dt)
        elif self._karonaru_arrival_trail:
            self._decay_karonaru_arrival_trail(dt)
        self._tick_boss_dialogue(dt)
        if self._combo_pulse           > 0: self._combo_pulse           -= dt * 4.0
        if self._combo_break_timer     > 0: self._combo_break_timer     -= dt
        self._update_popups(dt)

        # Combo timeout.
        if self._combo_count > 0 and self._combo_timer > 0:
            self._combo_timer -= dt
            if self._combo_timer <= 0:
                if self._combo_count >= COMBO_MIN:
                    self._combo_break_timer = 0.9
                self._combo_count = 0
                self._combo_timer = 0.0

        inp = self.game.input

        # Pause toggle (open only). Closing is handled in _update_pause(), so we
        # return here to keep the same keypress from being consumed twice in one
        # frame (open then immediately close), which left pause unusable.
        if (not self._upgrading and not self._paused
                and inp.is_action_just_pressed("pause")):
            self._paused = True
            self._pause_cursor = 0
            return

        # Open weapon upgrade when stock is available (自機 or 先輩).
        comp_stock = self._companion.stock if self._companion is not None else 0
        if (not self._upgrading and not self._paused
                and inp.is_action_just_pressed("weapon_select")
                and (self.player.weapon.weapon_stock > 0 or comp_stock > 0)):
            self._open_upgrade_ui()

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

        # ── 常時更新 ───────────────────────────────────────
        self.camera.update(dt)
        self._update_bg_text(dt)

        # Freeze gameplay during boss intro overlays.
        if self._boss_intro_state in _BOSS_INTRO_FREEZE:
            self.particles.update(dt)
            return

        # Freeze gameplay during final scripted dialogue.
        if self._final_dialogue_active:
            self._update_final_dialogue()
            self.particles.update(dt)
            return
        if self._final_seq == "return_join":
            self._update_karonaru_return_join(dt)
            self.particles.update(dt)
            return

        # ── 通常 / alert / entering 共通更新 ─────────────────
        self._stage_elapsed += dt
        self.stage.update(dt)
        _panel_open = self._is_debug_stage and self._debug_panel is not None and self._debug_panel._open
        self._player_prev_rect = self.player.rect.copy()
        if not _panel_open:
            self.player.update(dt)
        if self._companion:
            self._companion.update(dt, self.player, self.player_bullets, self.camera,
                                   self.enemies, self.enemy_bullets, self.terrain)

        if self._stage_banner_timer <= 0 and self._boss_intro_state == "":
            self.spawner.update(dt, self.camera)
        # alert/entering 中はスポーナー不動だがボス保留検知は行う

        if self.spawner.boss_gate_pending and self._boss_intro_state == "":
            if self._boss_gate_blocked():
                self._hold_before_boss_room()
                self._show_boss_gate_notice(dt)
            else:
                self.spawner.clear_boss_gate()
                self.camera.scroll_speed = getattr(self, "_stage_scroll_speed", 80.0)

        # ボス保留検知 -> ALERT 開始
        if self.spawner.boss_pending and self._boss_intro_state == "":
            if self._boss_gate_blocked():
                self._hold_before_boss_room()
                self._show_boss_gate_notice(dt)
            else:
                self._start_boss_alert()

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
                laser_killed, laser_hit, laser_boss_killed = self.laser.hit_check(
                    self.enemies, self._boss, msx, msy, terrain=self.terrain,
                )
                for enemy in laser_killed:
                    self._on_enemy_killed(enemy)
                if self._boss is not None:
                    if getattr(self.laser, "boss_form2_transition", False):
                        self._on_form2_transition()
                    if self._boss is not None and getattr(self.laser, "boss_form3_transition", False):
                        self._on_form3_transition()
                    if laser_boss_killed:
                        self._on_boss_killed()
                        if not self._is_debug_stage:
                            return
                terrain_hit = getattr(self.laser, "terrain_hit", None)
                if terrain_hit is not None and getattr(self.laser, "_terrain_hit_timer", 0.0) <= 0.0:
                    ter, hx, hy = terrain_hit
                    self._strike_terrain(ter, 1, int(hx), int(hy), allow_damage=True)
                    self.laser._terrain_hit_timer = 0.12
                if laser_hit:
                    self.game.sound.play_se("music/se/ウェポン：laser_hit.mp3", volume=0.12)
                    self.camera.shake(1.2)
                    hx = int(msx + (SCREEN_WIDTH - msx) * random.uniform(0.3, 0.8))
                    self.particles.spawn_hit(hx, int(msy))
            else:
                self.laser.state = "ready"

        for ter in list(self.terrain):
            ter.update(dt, self.camera)
            if ter.is_off_left(self.camera):
                ter.kill()

        if self._resolve_player_terrain_collision():
            self._damage_player(PLAYER_DMG_TERRAIN)
            if self.player.hp <= 0 and not self._is_debug_stage:
                return

        # 雑魚敵更新
        for enemy in list(self.enemies):
            enemy.update(dt, self.camera)
            if enemy.is_off_left(self.camera):
                enemy.kill()

        # アイテム引き寄せはカロナール先輩のマグネット系統が担う
        # （自機ツリーからは撤去。旧セーブ互換で自機magnetも残し、強い方を使う）
        mag_range, mag_speed = 0.0, 0.0
        if self._companion is not None and self._companion.is_active:
            mag_range, mag_speed = self._companion.magnet_params()
        if mag_range <= 0:
            mag_range, mag_speed = MAGNET_CONFIG.get(self.player.weapon.magnet_level, (0, 0))
        for item in list(self.items):
            item.update(dt, self.camera)
            if mag_range > 0:
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
            bounce_timer = getattr(bullet, "_terrain_bounce_timer", 0.0)
            if bounce_timer > 0.0:
                bullet._terrain_bounce_timer = bounce_timer - dt
                if bullet._terrain_bounce_timer <= 0.0:
                    bullet.kill()
                    continue
            if bullet.is_off_screen(self.camera):
                bullet.kill()

        for bullet in list(self.enemy_bullets):
            bullet.update(dt)
            bounce_timer = getattr(bullet, "_terrain_bounce_timer", 0.0)
            if bounce_timer > 0.0:
                bullet._terrain_bounce_timer = bounce_timer - dt
                if bullet._terrain_bounce_timer <= 0.0:
                    bullet.kill()
                    continue
            if bullet.is_off_screen():
                bullet.kill()

        self._process_terrain_bullet_collisions()

        # Queue boss mid-fight dialogue once after HP drops below half.
        if (self._boss is not None and self._boss_intro_state == "fighting"
                and self._final_phase == 0
                and not self._boss_mid_dialogue_shown
                and self._boss.hp / self._boss.max_hp <= 0.5):
            boss_stage_id = self._boss_stage_id()
            mid_key = "4f2mid" if getattr(self._boss, "_form2", False) else f"{boss_stage_id}mid"
            if mid_key in BOSS_MID:
                self._enqueue_boss_dialogue(BOSS_MID[mid_key], BOSS_MID_LINE_DURATION)
                self._boss_mid_dialogue_shown = True

        # Update final-battle special effects and companion sequence.
        if (self._boss is not None and self._boss_intro_state == "fighting"
                and self._final_phase > 0 and self._final_seq == ""):
            self._update_final_combat(dt)

        if self._process_collisions():
            return

        if __debug__:
            self._debug_handle_input()

        if self._is_debug_stage and self._debug_panel is not None:
            self._debug_panel.update(dt)

    def _boss_gate_blocked(self) -> bool:
        return any(type(enemy).__name__ in _BOSS_GATE_ENEMIES for enemy in self.enemies)

    def _hold_before_boss_room(self) -> None:
        gate = self.spawner.boss_gate_event or {}
        lock_camera_x = gate.get("lock_camera_x")
        if lock_camera_x is not None:
            self.camera.x = min(self.camera.x, float(lock_camera_x))
        self.camera.scroll_speed = 0.0

        player_limit_x = gate.get("player_limit_x")
        if player_limit_x is None:
            return
        max_sx = float(player_limit_x) - self.camera.x - self.player.rect.width
        max_sx = max(0.0, min(float(SCREEN_WIDTH - self.player.rect.width), max_sx))
        if self.player.sx > max_sx:
            self.player.sx = max_sx
            self.player.rect.topleft = (int(self.player.sx), int(self.player.sy))

    def _show_boss_gate_notice(self, dt: float) -> None:
        self._boss_wait_notice_timer -= dt
        if self._boss_wait_notice_timer <= 0.0:
            self._boss_wait_notice_timer = 1.4
            self._spawn_popup(
                "DEFEAT MID-BOSS FIRST",
                SCREEN_WIDTH // 2,
                78,
                color=(255, 190, 90),
                life=1.2,
            )

    def _start_boss_alert(self) -> None:
        self._active_boss_stage_id = self._pending_boss_stage_id or self._stage_id
        if not self._boss_terrain_spawned:
            self._prepare_boss_terrain(self._active_boss_stage_id)
        self._boss_intro_state = "alert"
        self._boss_intro_timer = ALERT_DURATION
        self.camera.scroll_speed = 0.0
        self.game.sound.play_bgm(BOSS_BGM.get(self._active_boss_stage_id, "music/bgm/決戦.mp3"))
        self.laser.state = "ready"

    def _update_boss_intro(self, dt: float) -> None:
        state = self._boss_intro_state
        inp   = self.game.input

        if state == "alert":
            self._boss_intro_timer -= dt
            if self._boss_intro_timer <= 0:
                self.spawner.confirm_spawn_boss(stage_id=self._boss_stage_id())
                self._boss = self.spawner.boss
                self._pending_boss_stage_id = None
                # 砲台連動ギミック用の召喚コールバックを注入
                self._boss.summon_turret_fn = self._summon_boss_turrets
                self._boss_intro_state = "entering"

        elif state == "boss_name":
            self._boss_intro_timer -= dt
            if self._boss_intro_timer <= 0:
                # ボスセリフへ
                pages = BOSS_INTRO.get(self._boss_stage_id(), [])
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
        boss_stage_id = self._boss_stage_id()
        self._boss_name_text   = BOSS_NAMES.get(boss_stage_id, "")
        self._boss_intro_state = "boss_name"
        self._boss_intro_timer = BOSS_NAME_DURATION
        self.game.sound.play_bgm_if_new(BOSS_BGM.get(boss_stage_id, "music/bgm/決戦.mp3"))

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
            # Draw boss hit flash.
            if getattr(self._boss, "hit_flash_timer", 0.0) > 0:
                tint = self._boss.image.copy()
                tint.fill((170, 170, 170), special_flags=pygame.BLEND_RGB_ADD)
                buf.blit(tint, self._boss.rect)
        self._draw_boss_gimmick(buf)
        self.particles.draw(buf)
        if self._karonaru_arrival_trail:
            self._draw_karonaru_arrival_trail(buf)
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

        # Draw laser fire flash.
        if self._laser_flash_timer > 0:
            alpha = int(160 * (self._laser_flash_timer / 0.08))
            flash = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            lv = self.player.weapon.laser_level
            fc = (180, 240, 255) if lv <= 4 else (255, 180, 180)
            flash.fill((*fc, alpha))
            screen.blit(flash, (0, 0))

        if self._form2_flash_timer > 0:
            alpha = int(220 * (self._form2_flash_timer / 0.5))
            flash = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            flash.fill((255, 255, 255, alpha))
            screen.blit(flash, (0, 0))

        # Draw boss-kill flash.
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

        s = self._boss_intro_state
        if s == "alert":         self._draw_alert(screen)
        elif s == "boss_name":   self._draw_boss_name(screen)
        elif s == "boss_dialogue": self._draw_boss_intro_dialogue(screen)
        elif s == "fight_banner": self._draw_fight_banner(screen)

        if self._boss_dialogue_timer > 0:
            self._draw_boss_dialogue(screen)

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

    def _resolve_player_terrain_collision(self) -> bool:
        """Push the player out of terrain and report whether contact happened."""
        if not self.terrain:
            return False

        collided = False
        prev_hit = self._hit_rect_from_rect(getattr(self, "_player_prev_rect", self.player.rect))

        for _ in range(4):
            hit = self.player.hit_rect
            blockers = [ter for ter in self.terrain if hit.colliderect(ter.rect)]
            if not blockers:
                break

            collided = True
            ter = max(blockers, key=lambda t: hit.clip(t.rect).width * hit.clip(t.rect).height)
            dx, dy = self._terrain_separation_delta(hit, prev_hit, ter.rect)
            if dx == 0 and dy == 0:
                break

            self.player.sx += dx
            self.player.sy += dy
            self.player.sx = max(0.0, min(SCREEN_WIDTH - self.player.rect.width, self.player.sx))
            self.player.sy = max(0.0, min(SCREEN_HEIGHT - self.player.rect.height, self.player.sy))
            self.player.rect.topleft = (int(self.player.sx), int(self.player.sy))

        return collided

    def _hit_rect_from_rect(self, rect: pygame.Rect) -> pygame.Rect:
        return rect.inflate(-int(rect.width * 0.1), -int(rect.height * 0.1))

    def _terrain_separation_delta(
        self,
        hit: pygame.Rect,
        prev_hit: pygame.Rect,
        block: pygame.Rect,
    ) -> tuple[float, float]:
        if prev_hit.right <= block.left:
            return float(block.left - hit.right), 0.0
        if prev_hit.left >= block.right:
            return float(block.right - hit.left), 0.0
        if prev_hit.bottom <= block.top:
            return 0.0, float(block.top - hit.bottom)
        if prev_hit.top >= block.bottom:
            return 0.0, float(block.bottom - hit.top)

        candidates = (
            (float(block.left - hit.right), 0.0),
            (float(block.right - hit.left), 0.0),
            (0.0, float(block.top - hit.bottom)),
            (0.0, float(block.bottom - hit.top)),
        )
        return min(candidates, key=lambda d: abs(d[0]) + abs(d[1]))

    def _process_terrain_bullet_collisions(self) -> None:
        if not self.terrain:
            return

        for bullet in list(self.player_bullets):
            if getattr(bullet, "_terrain_bounced", False):
                continue
            ter = pygame.sprite.spritecollideany(bullet, self.terrain)
            if ter is None:
                continue
            sx, sy = bullet.rect.center
            self._strike_terrain(ter, getattr(bullet, "damage", 1), sx, sy, allow_damage=True)
            from src.entities.bullets.player_bullet import HomingBullet
            if isinstance(bullet, HomingBullet):
                bullet.kill()   # ホーミングは壁で跳ね返さず消滅させる
            else:
                self._ricochet_bullet(bullet, ter, screen_space=False)

        for bullet in list(self.enemy_bullets):
            if (getattr(bullet, "_terrain_bounced", False)
                    or getattr(bullet, "terrain_passthrough", False)
                    or getattr(bullet, "warning_only", False)):
                continue
            ter = pygame.sprite.spritecollideany(bullet, self.terrain)
            if ter is None:
                continue
            sx, sy = bullet.rect.center
            self._strike_terrain(ter, 1, sx, sy, allow_damage=False)
            self._ricochet_bullet(bullet, ter, screen_space=True)

    def _strike_terrain(self, ter, damage: int, sx: int, sy: int, *, allow_damage: bool) -> None:
        self.particles.spawn_spark(sx, sy, count=10, speed=300.0)
        self.particles.spawn_hit(sx, sy, color=(255, 210, 130), count=4)
        self.camera.shake(0.8)
        self.game.sound.play_se("music/se/hit.wav", volume=0.18)

        if not allow_damage or not hasattr(ter, "take_damage"):
            return

        if not ter.take_damage(max(1, int(damage))):
            return

        world_x = self.camera.to_world_x(sx)
        world_y = max(24.0, min(float(sy), SCREEN_HEIGHT - 24.0))
        drop_chance = float(getattr(ter, "drop_chance", 0.0))
        ter.kill()
        self.particles.spawn_explosion(sx, sy, color=(255, 130, 70), count=18)
        self.particles.spawn_spark(sx, sy, color=(255, 180, 90), count=18, speed=420.0)
        self.particles.spawn_glow(sx, sy, color=(255, 210, 120), count=10, speed=120.0)
        self.camera.shake(4.0)
        terrain_score = 25 * combo_multiplier(max(1, self._combo_count))
        self.game.shared.score += terrain_score
        self._combo_count += 1
        self._combo_timer = COMBO_WINDOW
        self._combo_pulse = 0.8
        self._spawn_popup(f"BREAK +{terrain_score}", sx, sy - 18, color=(255, 200, 110), life=1.1)
        if self._add_fixed_item_drop(getattr(ter, "fixed_drop", None), world_x, world_y, spread=16.0):
            return
        if drop_chance > 0.0 and random.random() < drop_chance:
            self._add_random_item_drop(world_x, world_y, spread=16.0)

    def _ricochet_bullet(self, bullet, ter, *, screen_space: bool) -> None:
        b = bullet.rect
        t = ter.rect
        overlap_x = min(b.right - t.left, t.right - b.left)
        overlap_y = min(b.bottom - t.top, t.bottom - b.top)

        if overlap_y < overlap_x:
            if b.centery < t.centery:
                b.bottom = t.top - 1
                fallback_vy = -220.0
            else:
                b.top = t.bottom + 1
                fallback_vy = 220.0
            bullet.vy = -getattr(bullet, "vy", fallback_vy)
            if abs(bullet.vy) < 80.0:
                bullet.vy = fallback_vy
            bullet.vx = getattr(bullet, "vx", 0.0) * 0.45
        else:
            if b.centerx < t.centerx:
                b.right = t.left - 1
                fallback_vx = -260.0
            else:
                b.left = t.right + 1
                fallback_vx = 260.0
            bullet.vx = -getattr(bullet, "vx", fallback_vx)
            if abs(bullet.vx) < 100.0:
                bullet.vx = fallback_vx
            bullet.vy = getattr(bullet, "vy", 0.0) + random.uniform(-90.0, 90.0)

        if hasattr(bullet, "_homing_left"):
            bullet._homing_left = 0.0
        bullet._terrain_bounced = True
        bullet._terrain_bounce_timer = 0.18
        if screen_space:
            bullet.sx, bullet.sy = bullet.rect.center
        else:
            bullet.world_x = self.camera.to_world_x(bullet.rect.centerx)
            bullet.world_y = float(bullet.rect.centery)

    def _process_collisions(self) -> bool:
        from src.entities.bullets.player_bullet import HomingBullet
        active_player_bullets = pygame.sprite.Group(*[
            b for b in self.player_bullets if not getattr(b, "_terrain_bounced", False)
        ])
        hits = pygame.sprite.groupcollide(active_player_bullets, self.enemies, False, False)
        for bullet, hit_enemies in hits.items():
            hit_se = "music/se/ウェポン：missile_hit.mp3" if isinstance(bullet, HomingBullet) \
                     else "music/se/ウェポン：normalshot_hit.mp3"
            blocked_by_shield = False
            for enemy in hit_enemies:
                bx, by = bullet.rect.centerx, bullet.rect.centery
                if getattr(enemy, "blocks_projectile_damage", lambda b: False)(bullet):
                    self.particles.spawn_spark(bx, by, color=(180, 110, 255), count=8, speed=320.0)
                    self.particles.spawn_hit(bx, by, color=(120, 230, 255), count=4)
                    self.camera.shake(1.0)
                    self.game.sound.play_se("music/se/hit.wav", volume=0.18)
                    blocked_by_shield = True
                    break
                if isinstance(bullet, HomingBullet):
                    self.particles.spawn_explosion(bx, by, color=(255, 160, 40), count=22)
                    self.camera.shake(3.0)
                else:
                    self.particles.spawn_hit(bx, by)
                    self.camera.shake(1.0)
                self.game.sound.play_se(hit_se, volume=0.4)
                if self._combo_count > 0:
                    self._combo_timer = COMBO_WINDOW
                if enemy.take_damage(bullet.damage):
                    self._on_enemy_killed(enemy)
            if blocked_by_shield or not getattr(bullet, "piercing", False):
                bullet.kill()

        if self._boss is not None and self._boss_intro_state == "fighting":
            for bullet in list(self.player_bullets):
                if getattr(bullet, "_terrain_bounced", False):
                    continue
                if bullet.rect.colliderect(self._boss.rect):
                    hit_se = "music/se/ウェポン：missile_hit.mp3" if isinstance(bullet, HomingBullet) \
                             else "music/se/ウェポン：normalshot_hit.mp3"
                    bx, by = bullet.rect.centerx, bullet.rect.centery
                    feedback = not getattr(self._boss, "suppresses_hit_feedback", lambda: False)()
                    if feedback:
                        if isinstance(bullet, HomingBullet):
                            self.particles.spawn_explosion(bx, by, color=(255, 160, 40), count=22)
                            self.particles.spawn_spark(bx, by, count=6)
                            self.camera.shake(4.0)
                        else:
                            self.particles.spawn_hit(bx, by)
                            self.particles.spawn_spark(bx, by, count=3)
                            self.camera.shake(1.5)
                        self.game.sound.play_se(hit_se, volume=0.3)
                    if self._combo_count > 0:
                        self._combo_timer = COMBO_WINDOW
                    bullet.kill()
                    was_form2 = self._boss._form2
                    was_form3 = self._boss._form3
                    if self._boss.take_damage(bullet.damage):
                        self._on_boss_killed()
                        if not self._is_debug_stage:
                            return True
                        break
                    if self._boss is not None and not was_form2 and self._boss._form2:
                        self._on_form2_transition()
                    if self._boss is not None and not was_form3 and self._boss._form3:
                        self._on_form3_transition()

        if pygame.sprite.spritecollideany(self.player, self.enemies, _hit_rect_collide):
            self._damage_player(PLAYER_DMG_ENEMY)
            if self.player.hp <= 0 and not self._is_debug_stage:
                return True

        hit_bullet = None
        for bullet in list(self.enemy_bullets):
            if getattr(bullet, "_terrain_bounced", False) or getattr(bullet, "warning_only", False):
                continue
            if self.player.hit_rect.colliderect(bullet.rect):
                hit_bullet = bullet
                break
        if hit_bullet is not None:
            self._damage_player(getattr(hit_bullet, "damage", PLAYER_DMG_BULLET))
            if self.player.hp <= 0 and not self._is_debug_stage:
                return True

        # Damage player on direct boss contact during combat.
        if (self._boss is not None and self._boss_intro_state == "fighting"
                and self.player.hit_rect.colliderect(self._boss.rect)):
            self._damage_player(PLAYER_DMG_BOSS)
            if self.player.hp <= 0 and not self._is_debug_stage:
                return True

        # Damage player on terrain contact.
        if pygame.sprite.spritecollideany(self.player, self.terrain, _hit_rect_collide):
            self._damage_player(PLAYER_DMG_TERRAIN)
            if self.player.hp <= 0 and not self._is_debug_stage:
                return True

        if self._companion and self._companion.is_active:
            for enemy in list(self.enemies):
                if self._companion.hit_rect.colliderect(enemy.rect):
                    self._companion.take_damage()
                    # Also damage the enemy that touched the companion.
                    if enemy.take_damage(KARONARU_CONTACT_DMG):
                        self._on_enemy_killed(enemy)
                    break
            if self._companion.is_active:
                for bullet in list(self.enemy_bullets):
                    if getattr(bullet, "_terrain_bounced", False) or getattr(bullet, "warning_only", False):
                        continue
                    if self._companion.hit_rect.colliderect(bullet.rect):
                        self._companion.take_damage()
                        bullet.kill()   # 被弾した弾は相殺
                        break

        picked_items = pygame.sprite.spritecollide(self.player, self.items, True)
        for item in picked_items:
            self._play_item_pickup_sound(item)
            if type(item).__name__ == "WeaponItem":
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
        if hasattr(enemy, "split"):
            shards = enemy.split(self.game)
            self.enemies.add(*shards)
            for shard in shards:
                sx2 = self.camera.to_screen_x(shard.world_x)
                self.particles.spawn_spark(int(sx2), int(shard.world_y), count=6, speed=280.0)
        enemy.kill()
        self._combo_count += 1
        self._combo_timer  = COMBO_WINDOW
        self._combo_pulse  = 1.0
        mult = combo_multiplier(self._combo_count)
        self.game.shared.score      += 100 * mult
        self.game.shared.kill_count += 1
        self.game.sound.play_se("music/se/game_explosion9.mp3", volume=0.3)

        if etype == "EnemyBilly":
            from src.entities.items.heal import HealItem
            self._add_weapon_drop(
                enemy.world_x + random.uniform(-40, 40),
                enemy.world_y + random.uniform(-30, 30),
            )
            for _ in range(4):
                self.items.add(HealItem(
                    enemy.world_x + random.uniform(-60, 60),
                    enemy.world_y + random.uniform(-40, 40),
                ))
        else:
            if self._add_fixed_item_drop(getattr(enemy, "fixed_drop", None), enemy.world_x, enemy.world_y):
                return
            if getattr(enemy, "drops_enabled", True):
                chance = getattr(enemy, "drop_chance", DROP_CHANCE.get(etype, 0.20))
                if random.random() < chance:
                    self._add_random_item_drop(enemy.world_x, enemy.world_y)

    def _add_weapon_drop(self, world_x: float, world_y: float) -> None:
        from src.entities.items.weapon_item import WeaponItem
        self.items.add(WeaponItem(world_x, world_y))

    def _add_fixed_item_drop(
        self,
        item_name: str | None,
        world_x: float,
        world_y: float,
        *,
        spread: float = 0.0,
    ) -> bool:
        if not item_name:
            return False
        from src.core.factories import make_item
        ox = world_x + random.uniform(-spread, spread)
        oy = world_y + random.uniform(-spread, spread)
        item = make_item(str(item_name), ox, oy)
        if item is None:
            return False
        self.items.add(item)
        return True

    def _add_random_item_drop(self, world_x: float, world_y: float, *, spread: float = 0.0) -> None:
        self.items.add(random_item(world_x, world_y, spread=spread))

    def _play_item_pickup_sound(self, item) -> None:
        item_type = type(item).__name__
        if item_type == "WeaponItem":
            self.game.sound.play_se_alias("SE_ITEM_WEAPON", volume=0.75)
        elif item_type == "HealItem":
            self.game.sound.play_se_alias("SE_ITEM_HEAL", volume=0.75)
        else:
            self.game.sound.play_se_alias("SE_ITEM", volume=0.7)

    def _on_form2_transition(self) -> None:
        self.camera.shake(22.0)
        self._hitstop_timer = 0.14
        self.particles.spawn_big_explosion(self._boss.sx, self._boss.sy)
        self.enemy_bullets.empty()
        self.player._invincible_timer = max(self.player._invincible_timer, 2.5)
        self._form2_flash_timer = 0.5
        f2_key = f"{self._boss_stage_id()}f2"
        self._enqueue_boss_dialogue(BOSS_MID.get(f2_key, []), BOSS_MID_LINE_DURATION)
        self._boss_mid_dialogue_shown = False

    def _show_final_banner(self, key: str, duration: float = 2.6) -> None:
        self._final_banner_text  = FINAL_BANNERS.get(key, ())
        self._final_banner_timer = duration

    def _play_final_dialogue(self, pages: list, on_done) -> None:
        """Play final dialogue pages and invoke a completion callback."""
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
        """Transition from form 2 to the true final form."""
        self.camera.shake(26.0)
        self._hitstop_timer = 0.18
        self.particles.spawn_big_explosion(self._boss.sx, self._boss.sy)
        self.enemy_bullets.empty()
        self.player._invincible_timer = max(self.player._invincible_timer, 2.5)
        self._boss_kill_flash_timer = 1.2
        self.game.sound.stop_bgm(fadeout_ms=600)
        boss_stage_id = self._boss_stage_id()
        self.game.sound.play_bgm(BOSS_BGM.get(boss_stage_id, "music/bgm/決戦.mp3"))
        self._final_phase = 1
        self._final_seq   = ""
        self._show_final_banner("true_final", 3.0)
        self._play_final_dialogue(BOSS_FORM3_INTRO, on_done=lambda: None)

    def _update_final_combat(self, dt: float) -> None:
        """Update special story beats during the final form."""
        boss = self._boss
        if boss is None:
            return
        ratio = boss.hp / boss.max_hp

        if self._final_phase == 1:
            if getattr(boss, "_regen_enabled", False):
                self._regen_timer -= dt
                if self._regen_timer <= 0.0:
                    self._regen_timer = 1.0
                    boss.regen(2)
            if not self._f3_act1_mid_shown and ratio <= 0.6:
                self._enqueue_boss_dialogue(BOSS_MID.get("4f3mid", []), BOSS_MID_LINE_DURATION)
                self._f3_act1_mid_shown = True
            if not self._fakeout_triggered and ratio <= 0.3:
                self._fakeout_triggered = True
                self._start_fakeout()
        elif self._final_phase == 2:
            if not self._f3_act2_mid_shown and ratio <= 0.5:
                self._enqueue_boss_dialogue(BOSS_MID.get("4f3act2mid", []), BOSS_MID_LINE_DURATION)
                self._f3_act2_mid_shown = True
            if not self._final_sengen_triggered and boss.hp <= 1:
                self._final_sengen_triggered = True
                self._start_final_sengen()

    def _start_fakeout(self) -> None:
        self._final_seq = "fakeout"
        self.enemy_bullets.empty()
        self.camera.shake(16.0)
        self._play_final_dialogue(FINAL_SEQ["fakeout"], on_done=self._start_sengen)

    def _start_sengen(self) -> None:
        if self._boss is not None:
            self._boss.hp = self._boss.max_hp // 2
        self._final_seq = "sengen"
        self._sengen_overlay_timer = 2.5
        self._show_final_banner("sengen", 2.6)
        self.player.hp = 1   # 蝗樣∩荳崎・ 竊・轢墓ｭｻ
        self.player._invincible_timer = max(self.player._invincible_timer, 3.0)
        self._play_final_dialogue(FINAL_SEQ["sengen"], on_done=self._start_karonaru_return)

    def _start_karonaru_return(self) -> None:
        self._final_seq = "return"
        self._show_final_banner("kouhatsu", 3.0)
        self._boss_kill_flash_timer = 1.2   # 逋ｽ髢・・
        self.game.sound.play_bgm("music/bgm/Rebirth_the_edge.mp3", volume=0.7)
        self.game.sound.play_se_alias("SE_LIGHT")
        self._spawn_returning_karonaru()
        self._play_final_dialogue(FINAL_SEQ["return"], on_done=self._start_karonaru_return_join)

    def _spawn_returning_karonaru(self) -> None:
        if self._companion is None:
            from src.entities.companion import Karonaru
            self._companion = Karonaru(self.game, popup_fn=self._spawn_popup,
                                       spawn_heal_fn=self._companion_spawn_heal)
        arrival_y = float(self.player.rect.centery) + 18.0
        end_x = max(62.0, float(self.player.rect.centerx) - 76.0)
        start = (-48.0, arrival_y)
        end = (end_x, arrival_y)
        self._companion.sx, self._companion.sy = start
        self._companion.rect.center = (int(self._companion.sx), int(self._companion.sy))
        self._karonaru_arrival_duration = 1.65
        self._karonaru_arrival_timer = self._karonaru_arrival_duration
        self._karonaru_arrival_from = start
        self._karonaru_arrival_to = end
        self._karonaru_arrival_pos = start
        self._karonaru_arrival_trail = [(start[0], start[1], 0.45)]
        self.game.sound.play_se_alias("SE_KARONARU_ARRIVE", volume=0.7)

    def _update_karonaru_arrival_motion(self, dt: float) -> None:
        if self._companion is None:
            self._karonaru_arrival_timer = 0.0
            return
        dur = max(0.001, self._karonaru_arrival_duration)
        self._karonaru_arrival_timer = max(0.0, self._karonaru_arrival_timer - dt)
        t = 1.0 - self._karonaru_arrival_timer / dur
        ease = 1.0 - (1.0 - t) ** 3
        sx0, sy0 = self._karonaru_arrival_from
        sx1, sy1 = self._karonaru_arrival_to
        self._companion.sx = sx0 + (sx1 - sx0) * ease
        self._companion.sy = sy0 + (sy1 - sy0) * ease
        self._companion.rect.center = (int(self._companion.sx), int(self._companion.sy))
        self._karonaru_arrival_pos = (self._companion.sx, self._companion.sy)
        self._karonaru_arrival_trail.append((self._companion.sx, self._companion.sy, 0.55))
        self._karonaru_arrival_trail = [
            (x, y, life - dt) for x, y, life in self._karonaru_arrival_trail
            if life - dt > 0.0
        ]

    def _decay_karonaru_arrival_trail(self, dt: float) -> None:
        self._karonaru_arrival_trail = [
            (x, y, life - dt) for x, y, life in self._karonaru_arrival_trail
            if life - dt > 0.0
        ]

    def _draw_karonaru_arrival_trail(self, surf: pygame.Surface) -> None:
        trail = self._karonaru_arrival_trail
        if len(trail) < 2:
            return
        layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for i, (x, y, life) in enumerate(trail):
            alpha = max(0, min(180, int(180 * life / 0.55)))
            radius = 2 + min(4, i // 3)
            pygame.draw.circle(layer, (170, 255, 205, alpha), (int(x), int(y)), radius)
        pts = [(int(x), int(y)) for x, y, _ in trail]
        if len(pts) >= 2:
            pygame.draw.lines(layer, (125, 245, 180, 80), False, pts, 2)
        surf.blit(layer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def _start_karonaru_return_join(self) -> None:
        if self._companion is None:
            self._spawn_returning_karonaru()
        if self._karonaru_arrival_timer > 0:
            self._karonaru_arrival_timer = 0.0
            self._companion.sx, self._companion.sy = self._karonaru_arrival_to
            self._companion.rect.center = (int(self._companion.sx), int(self._companion.sy))
        self._final_seq = "return_join"
        self._karonaru_return_timer = 0.0
        self._karonaru_return_from = (float(self._companion.sx), float(self._companion.sy))
        self._karonaru_return_to = (
            float(self.player.rect.centerx) - 52.0,
            float(self.player.rect.centery) + 18.0,
        )
        self.game.sound.play_se_alias("SE_LIGHT")

    def _update_karonaru_return_join(self, dt: float) -> None:
        if self._companion is None:
            self._do_karonaru_max()
            return
        self._karonaru_return_timer += dt
        dur = 1.35
        t = min(1.0, self._karonaru_return_timer / dur)
        ease = 1.0 - (1.0 - t) ** 3
        sx0, sy0 = self._karonaru_return_from
        sx1, sy1 = self._karonaru_return_to
        arc = math.sin(t * math.pi) * 36.0
        self._companion.sx = sx0 + (sx1 - sx0) * ease
        self._companion.sy = sy0 + (sy1 - sy0) * ease - arc
        self._companion.rect.center = (int(self._companion.sx), int(self._companion.sy))
        self.particles.spawn_glow(
            self._companion.sx,
            self._companion.sy,
            color=(190, 255, 210),
            count=2,
            speed=45.0,
        )
        if t >= 1.0:
            self._spawn_popup("LET'S GO", int(self._companion.sx), int(self._companion.sy) - 34,
                              color=(180, 255, 200), life=1.8)
            self._do_karonaru_max()

    def _do_karonaru_max(self) -> None:
        if self._companion is None:
            from src.entities.companion import Karonaru
            self._companion = Karonaru(self.game, popup_fn=self._spawn_popup,
                                       spawn_heal_fn=self._companion_spawn_heal)
            self._companion.sx = float(self.player.rect.centerx) - 50.0
            self._companion.sy = float(self.player.rect.centery) + 16.0
        self._companion.set_max()
        self._companion.reseed_trail(self.player)
        self._karonaru_heal_player()
        self.game.story.karonaru_lost        = False
        # Story flags for Karonaru return.
        self.game.story.karonaru_available   = True
        self.game.story.karonaru_max         = True
        self.game.story.final_self_distanced = True
        self._show_final_banner("anti_rumin", 3.0)
        # Start the anti-rumination field and final gauge.
        from src.entities.enemies.boss import _FORM3_ACT2_HP
        if self._boss is not None:
            self._boss.begin_act2(_FORM3_ACT2_HP)
        self._final_phase = 2
        self._boss_mid_dialogue_shown = False
        self._play_final_dialogue(FINAL_SEQ["act2_start"], on_done=self._resume_final_combat)

    def _karonaru_heal_player(self) -> None:
        before = self.player.hp
        self.player.hp = self.player.max_hp
        self.player._invincible_timer = max(self.player._invincible_timer, 2.8)
        healed = max(0, self.player.hp - before)
        px, py = self.player.rect.center
        self._spawn_popup(
            "HP FULL RECOVER" if healed > 0 else "HP SECURED",
            px,
            self.player.rect.top - 26,
            color=(160, 255, 190),
            life=2.4,
        )
        self.particles.spawn_glow(px, py, color=(160, 255, 190), count=28, speed=85.0)
        self.particles.spawn_spark(px, py, color=(225, 255, 210), count=16, speed=260.0)
        if self._companion is not None:
            self.particles.spawn_glow(
                self._companion.sx,
                self._companion.sy,
                color=(220, 255, 230),
                count=18,
                speed=70.0,
            )
        self.game.sound.play_se_alias("SE_HEAL", volume=0.8)

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
        self._show_final_banner("final_chance", 2.4)
        self._spawn_popup("NOW STRIKE", SCREEN_WIDTH // 2, 120, color=(255, 230, 150), life=2.0)
        self._final_seq = "final_chance"

    # ── 最終決戦 描画 ──────────────────────────────────────────────
    def _draw_sengen_overlay(self, screen: pygame.Surface) -> None:
        """Draw the final declaration overlay."""
        pulse = 0.5 + 0.5 * math.sin(self._sengen_overlay_timer * 6.0)
        alpha = int(120 + 80 * pulse)
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        ov.fill((90, 0, 10, alpha))
        screen.blit(ov, (0, 0))

    def _draw_final_banner(self, screen: pygame.Surface) -> None:
        """Draw the final system banner."""
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
        """Draw final battle dialogue pages."""
        if self._final_dialogue_font is None:
            self._final_dialogue_font = self.game.resources.pixelfont(26)
        pages = self._final_dialogue_pages
        idx   = self._final_dialogue_idx
        if not pages or idx >= len(pages):
            return
        line  = pages[idx]
        total = len(pages)

        if idx < total - 1:
            hint = f"{idx + 1}/{total}  ENTER: 次へ"
        else:
            hint = "ENTER: OK"
        draw_combat_panel(
            screen,
            self.game.resources,
            line.speaker,
            (line.text,),
            page_index=idx,
            total_pages=total,
            hint_text=hint,
            style=COMBAT_PURPLE_STYLE,
        )

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

    def _enqueue_boss_dialogue(self, lines: list, line_duration: float | None = None) -> None:
        """Start timed boss dialogue and queue remaining lines."""
        if not lines:
            return
        self._boss_dialogue_line_dur = line_duration or BOSS_DIALOGUE_DURATION
        self._boss_dialogue_queue    = list(lines[1:])
        first = lines[0]
        self._boss_dialogue_speaker  = first.speaker
        self._boss_dialogue_text     = first.text
        self._boss_dialogue_timer    = self._boss_dialogue_line_dur

    def _tick_boss_dialogue(self, dt: float) -> None:
        """Advance timed boss dialogue."""
        if self._boss_dialogue_timer <= 0:
            return
        self._boss_dialogue_timer -= dt
        if self._boss_dialogue_timer <= 0 and self._boss_dialogue_queue:
            nxt = self._boss_dialogue_queue.pop(0)
            self._boss_dialogue_speaker = nxt.speaker
            self._boss_dialogue_text    = nxt.text
            self._boss_dialogue_timer   = getattr(self, "_boss_dialogue_line_dur", BOSS_DIALOGUE_DURATION)

    def _draw_boss_gimmick(self, buf: pygame.Surface) -> None:
        """Draw the current boss gimmick state."""
        b = self._boss
        if b is None:
            return
        cx, cy = b.rect.center
        r = max(b.rect.width, b.rect.height) // 2 + 10
        gimmick = b._current_gimmick() if hasattr(b, "_current_gimmick") else None
        if getattr(b, "_state", "fight") != "fight":
            return
        self._draw_boss_concept_fx(buf, b, cx, cy, r)
        if gimmick is None:
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
                pygame.draw.circle(buf, (255, 55, 80), (cx, cy), 18)
                pygame.draw.circle(buf, (255, 240, 220), (cx, cy), 8)
                label, lcol = "CORE EXPOSED!", (255, 90, 90)
            else:
                label, lcol = "ARMOR", (180, 190, 210)
                self._draw_armor_gauge(buf, b, cx, b.rect.top - 30)

        elif gimmick == "turrets":
            if getattr(b, "_stun_timer", 0.0) > 0:
                label, lcol = "STUN  DAMAGE UP", (255, 220, 60)
            else:
                n = b._summoned_alive() if hasattr(b, "_summoned_alive") else 0
                if n > 0:
                    label, lcol = f"DRONE SHIELD x{n}", (160, 230, 255)

        if label:
            surf = self.game.resources.pixelfont(20).render(label, True, lcol)
            buf.blit(surf, (cx - surf.get_width() // 2, b.rect.top - 26))

    def _draw_armor_gauge(self, buf: pygame.Surface, b, cx: int, y: int) -> None:
        """Draw a compact armor gauge for weakpoint gimmicks."""
        from src.entities.enemies.boss import _ARMOR_MAX
        w, h = 80, 6
        ratio = max(0.0, min(1.0, getattr(b, "_armor", 0) / _ARMOR_MAX))
        x = cx - w // 2
        pygame.draw.rect(buf, (40, 44, 54), (x, y, w, h), border_radius=2)
        pygame.draw.rect(buf, (150, 170, 200), (x, y, int(w * ratio), h), border_radius=2)
        pygame.draw.rect(buf, (90, 100, 120), (x, y, w, h), 1, border_radius=2)

    def _draw_boss_concept_fx(self, buf: pygame.Surface, b, cx: int, cy: int, r: int) -> None:
        """Draw form-specific readable boss silhouettes and danger cues."""
        stage_id = getattr(b, "_stage_id", 0)
        form2 = bool(getattr(b, "_form2", False))
        form3 = bool(getattr(b, "_form3", False))

        if form3:
            pulse = 0.5 + 0.5 * math.sin(getattr(b, "_time", 0.0) * 3.0)
            aura = pygame.Surface((r * 2 + 36, r * 2 + 36), pygame.SRCALPHA)
            pygame.draw.circle(aura, (120, 10, 70, int(50 + 55 * pulse)),
                               (r + 18, r + 18), r + 12)
            pygame.draw.circle(aura, (220, 30, 80, int(90 + 45 * pulse)),
                               (r + 18, r + 18), r + 12, 3)
            buf.blit(aura, (cx - r - 18, cy - r - 18), special_flags=pygame.BLEND_RGBA_ADD)
            return

        if stage_id == 2 and not form2:
            if getattr(b, "_weak_timer", 0.0) <= 0:
                plate = pygame.Surface((b.rect.width + 34, b.rect.height + 34), pygame.SRCALPHA)
                w, h = plate.get_size()
                col = (150, 165, 185, 135)
                pygame.draw.rect(plate, col, (4, 14, w - 8, 14), border_radius=3)
                pygame.draw.rect(plate, col, (4, h - 28, w - 8, 14), border_radius=3)
                pygame.draw.rect(plate, col, (6, 30, 16, h - 60), border_radius=3)
                pygame.draw.rect(plate, col, (w - 22, 30, 16, h - 60), border_radius=3)
                pygame.draw.rect(plate, (230, 240, 255, 110), (0, 10, w, h - 20), 2, border_radius=8)
                buf.blit(plate, (b.rect.left - 17, b.rect.top - 17))

        if stage_id == 3 and not form2:
            alive = b._summoned_alive() if hasattr(b, "_summoned_alive") else 0
            if alive > 0:
                shield = pygame.Surface((r * 2 + 16, r * 2 + 16), pygame.SRCALPHA)
                pygame.draw.circle(shield, (50, 210, 240, 62), (r + 8, r + 8), r + 4)
                pygame.draw.circle(shield, (130, 245, 255, 170), (r + 8, r + 8), r + 4, 3)
                buf.blit(shield, (cx - r - 8, cy - r - 8))
                for turret in list(getattr(b, "_summoned", [])):
                    if not turret.alive():
                        continue
                    tx, ty = turret.rect.center
                    pygame.draw.aaline(buf, (110, 235, 255), (cx, cy), (tx, ty))
                    pygame.draw.circle(buf, (170, 255, 255), (tx, ty), 8, 2)
            elif getattr(b, "_stun_timer", 0.0) > 0:
                pygame.draw.circle(buf, (255, 225, 80), (cx, cy), r + 8, 4)

        if stage_id == 4 and not form2:
            grid = pygame.Surface((178, 250), pygame.SRCALPHA)
            for x in range(0, 179, 44):
                pygame.draw.line(grid, (210, 170, 70, 55), (x, 0), (x, 249))
            for y in range(0, 251, 50):
                pygame.draw.line(grid, (210, 170, 70, 55), (0, y), (177, y))
            buf.blit(grid, (cx - grid.get_width() // 2, cy - grid.get_height() // 2))

        if form2:
            slash = pygame.Surface((r * 2 + 28, r * 2 + 28), pygame.SRCALPHA)
            pygame.draw.line(slash, (255, 45, 120, 150), (slash.get_width() - 8, 14), (18, slash.get_height() - 12), 5)
            pygame.draw.line(slash, (255, 190, 225, 110), (slash.get_width() - 40, 8), (46, slash.get_height() - 22), 2)
            buf.blit(slash, (cx - r - 14, cy - r - 14), special_flags=pygame.BLEND_RGBA_ADD)

    def _summon_boss_turrets(self, n: int) -> list:
        """Summon turrets used by boss gimmicks."""
        if self._boss_stage_id() == 3 and self._boss is not None:
            from src.entities.enemies.boss_drone import MatchingZeroDrone
            spawned = []
            for i in range(n):
                d = MatchingZeroDrone(self.game, self._boss, i, self.enemy_bullets, self.player)
                self.enemies.add(d)
                spawned.append(d)
            return spawned

        from src.entities.enemies.turret import EnemyTurret
        spawned = []
        for i in range(n):
            wx = self.camera.spawn_x(margin=-120)
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
        # Regenerate the final boss when the player is hit during act 1.
        if (self._boss is not None and self._final_phase == 1
                and getattr(self._boss, "_regen_enabled", False)):
            self._boss.regen(15)
        if self.player.hp <= 0:
            self._go_gameover()
        else:
            self.game.sound.play_se("music/se/shout.wav", volume=0.6)

    def _pickup_weapon_item(self) -> None:
        """Apply a weapon stock pickup."""
        self.player.weapon.weapon_stock += 1
        # 取得ごとに先輩（カロナール）の強化ストックも +1（別ツリー＝支援系）
        if self._companion is not None:
            self._companion.stock += 1
            self._spawn_popup(
                "先輩 強化ストック +1",
                self._companion.rect.centerx, self._companion.rect.top - 6,
                color=(150, 235, 170), life=1.6,
            )
        wsel = self.game.settings.key_display("weapon_select")
        px, py = self.player.rect.centerx, self.player.rect.top - 10
        if not self._weapon_tip_shown:
            self._weapon_tip_shown = True
            self._spawn_popup(f"WEAPON STOCK +1   {wsel}キーで強化を選択",
                              px, py, color=(120, 230, 255), life=3.0)
        else:
            self._spawn_popup(f"WEAPON +1  [{wsel}]", px, py)

    def _companion_spawn_heal(self) -> None:
        """補給: 先輩が前方へ回復アイテムを射出する（Lvで頻度上昇）。"""
        if self._companion is None:
            return
        from src.entities.items.heal import HealItem
        # 先輩の少し前方（右）に射出 → 自然に左ドリフトして自機の進路に乗る
        world_x = self.camera.x + float(self._companion.rect.centerx) + 26.0
        world_y = float(self._companion.rect.centery)
        self.items.add(HealItem(world_x, world_y))
        # 射出演出（先輩位置からのきらめき）
        self.particles.spawn_spark(
            self._companion.rect.centerx, self._companion.rect.centery,
            color=(120, 240, 150), count=10, speed=210.0,
        )
        self.game.sound.play_se_alias("SE_ITEM_HEAL", volume=0.5)

    def _spawn_popup(self, text: str, sx: int, sy: int,
                     color: tuple = (255, 230, 60), life: float = 1.4) -> None:
        self._popups.append([text, float(sx), float(sy), life, color])

    def _update_popups(self, dt: float) -> None:
        for p in self._popups:
            p[3] -= dt
            p[2] -= 35.0 * dt   # 上に流れめE        self._popups = [p for p in self._popups if p[3] > 0]

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
            label += f"  x{mult}"
        surf = font.render(label, True, color)
        cx   = SCREEN_WIDTH // 2
        cy   = 58
        screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))

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
