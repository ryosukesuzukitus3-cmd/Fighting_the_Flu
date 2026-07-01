"""最終決戦（Form3 投了王サワグチ）の演出シーケンスを集約するディレクタ。

`GameScene` から最終決戦まわりの状態と振る舞いを切り出したもの。
state（フェーズ・各種タイマー・カロナール帰還モーション等）はこの
ディレクタが所有し、カメラ・自機・ボス・パーティクル等の共有コラボレータ
へは `self.scene` 経由でアクセスする。

呼び出し側（GameScene）が触れる公開 API は以下のみ：
- 読み取り: `phase` / `seq` / `dialogue_active`
- 更新: `update_timers` / `update_dialogue` / `update_return_join` / `update_combat`
- 遷移: `on_form2_transition` / `on_form3_transition`
- 描画: `draw_arrival_trail` / `draw_overlays`
"""
from __future__ import annotations
import math
import pygame

from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.scenes.dialogue_panel import COMBAT_PURPLE_STYLE, draw_combat_panel
from src.scenes.game.config import BOSS_BGM, BOSS_MID_LINE_DURATION
from src.story.aliases import bgm_path
from src.story.script import BOSS_MID, BOSS_FORM3_INTRO, FINAL_SEQ, FINAL_BANNERS


class FinalBattleDirector:
    def __init__(self, scene) -> None:
        self.scene = scene
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

    # ── 公開: 状態読み取り ────────────────────────────────────────
    @property
    def phase(self) -> int:
        return self._final_phase

    @property
    def seq(self) -> str:
        return self._final_seq

    @property
    def dialogue_active(self) -> bool:
        return self._final_dialogue_active

    # ── 公開: 更新エントリ ────────────────────────────────────────
    def update_timers(self, dt: float) -> None:
        """演出タイマー（バナー・宣言オーバーレイ）とカロナール到着モーション。"""
        if self._final_banner_timer    > 0: self._final_banner_timer    -= dt
        if self._sengen_overlay_timer  > 0: self._sengen_overlay_timer  -= dt
        if self._karonaru_arrival_timer > 0:
            self._update_karonaru_arrival_motion(dt)
        elif self._karonaru_arrival_trail:
            self._decay_karonaru_arrival_trail(dt)

    def update_dialogue(self) -> None:
        inp = self.scene.game.input
        if (inp.is_held_with_repeat(pygame.K_RETURN, 0.25, 0.12)
                or inp.is_held_with_repeat(pygame.K_SPACE, 0.25, 0.12)):
            self._final_dialogue_idx += 1
            if self._final_dialogue_idx >= len(self._final_dialogue_pages):
                self._final_dialogue_active = False
                cb = self._final_dialogue_on_done
                self._final_dialogue_on_done = None
                if cb is not None:
                    cb()

    def update_return_join(self, dt: float) -> None:
        companion = self.scene._companion
        if companion is None:
            self._do_karonaru_max()
            return
        self._karonaru_return_timer += dt
        dur = 1.35
        t = min(1.0, self._karonaru_return_timer / dur)
        ease = 1.0 - (1.0 - t) ** 3
        sx0, sy0 = self._karonaru_return_from
        sx1, sy1 = self._karonaru_return_to
        arc = math.sin(t * math.pi) * 36.0
        companion.sx = sx0 + (sx1 - sx0) * ease
        companion.sy = sy0 + (sy1 - sy0) * ease - arc
        companion.rect.center = (int(companion.sx), int(companion.sy))
        self.scene.particles.spawn_glow(
            companion.sx,
            companion.sy,
            color=(190, 255, 210),
            count=2,
            speed=45.0,
        )
        if t >= 1.0:
            self.scene._spawn_popup("LET'S GO", int(companion.sx), int(companion.sy) - 34,
                                    color=(180, 255, 200), life=1.8)
            self._do_karonaru_max()

    def update_combat(self, dt: float) -> None:
        """最終形態中のストーリー要所を進める。"""
        boss = self.scene._boss
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
                self.scene._enqueue_boss_dialogue(BOSS_MID.get("4f3mid", []), BOSS_MID_LINE_DURATION)
                self._f3_act1_mid_shown = True
            if not self._fakeout_triggered and ratio <= 0.3:
                self._fakeout_triggered = True
                self._start_fakeout()
        elif self._final_phase == 2:
            if not self._f3_act2_mid_shown and ratio <= 0.5:
                self.scene._enqueue_boss_dialogue(BOSS_MID.get("4f3act2mid", []), BOSS_MID_LINE_DURATION)
                self._f3_act2_mid_shown = True
            if not self._final_sengen_triggered and boss.hp <= 1:
                self._final_sengen_triggered = True
                self._start_final_sengen()

    # ── 公開: フェーズ遷移 ────────────────────────────────────────
    def on_form2_transition(self) -> None:
        scene = self.scene
        # 第1→2形態の juice を第3形態と同格に：強シェイク・変身スティンガー・
        # 覚醒バナー保持・BGM 切替（専用曲は仮配線）。
        scene.camera.shake(26.0)
        scene._hitstop_timer = 0.16
        scene.particles.spawn_big_explosion(scene._boss.sx, scene._boss.sy)
        scene.enemy_bullets.empty()
        scene.player._invincible_timer = max(scene.player._invincible_timer, 2.5)
        scene._form2_flash_timer = 0.5
        scene.game.sound.play_se_alias("SE_BOSS_TRANSFORM", volume=0.85)
        # 専用トラック未着手のため現状は決戦を継続（if_new＝再スタートしない）。
        # 後で BGM_BOSS_FORM2 を差し替えると自動で切り替わる。
        scene.game.sound.play_bgm_if_new(bgm_path("BGM_BOSS_FORM2"))
        self._show_final_banner("awaken", 2.6)
        f2_key = f"{scene._boss_stage_id()}f2"
        scene._enqueue_boss_dialogue(BOSS_MID.get(f2_key, []), BOSS_MID_LINE_DURATION)
        scene._boss_mid_dialogue_shown = False

    def on_form3_transition(self) -> None:
        """Transition from form 2 to the true final form."""
        scene = self.scene
        scene.camera.shake(26.0)
        scene._hitstop_timer = 0.18
        scene.particles.spawn_big_explosion(scene._boss.sx, scene._boss.sy)
        scene.enemy_bullets.empty()
        scene.player._invincible_timer = max(scene.player._invincible_timer, 2.5)
        scene._boss_kill_flash_timer = 1.2
        scene.game.sound.stop_bgm(fadeout_ms=600)
        boss_stage_id = scene._boss_stage_id()
        scene.game.sound.play_bgm(BOSS_BGM.get(boss_stage_id, "music/bgm/決戦.mp3"))
        self._final_phase = 1
        self._final_seq   = ""
        self._show_final_banner("true_final", 3.0)
        self._play_final_dialogue(BOSS_FORM3_INTRO, on_done=lambda: None)

    # ── 内部: バナー / セリフ ─────────────────────────────────────
    def _show_final_banner(self, key: str, duration: float = 2.6) -> None:
        self._final_banner_text  = FINAL_BANNERS.get(key, ())
        self._final_banner_timer = duration

    def _play_final_dialogue(self, pages: list, on_done) -> None:
        """Play final dialogue pages and invoke a completion callback."""
        self._final_dialogue_pages   = list(pages)
        self._final_dialogue_idx     = 0
        self._final_dialogue_active  = True
        self._final_dialogue_on_done = on_done

    # ── 内部: フェイクアウト → 宣言 → 帰還 シーケンス ────────────────
    def _start_fakeout(self) -> None:
        self._final_seq = "fakeout"
        self.scene.enemy_bullets.empty()
        self.scene.camera.shake(16.0)
        self._play_final_dialogue(FINAL_SEQ["fakeout"], on_done=self._start_sengen)

    def _start_sengen(self) -> None:
        if self.scene._boss is not None:
            self.scene._boss.hp = self.scene._boss.max_hp // 2
        self._final_seq = "sengen"
        self._sengen_overlay_timer = 2.5
        self._show_final_banner("sengen", 2.6)
        self.scene.player.hp = 1   # 回避不可 → 致死
        self.scene.player._invincible_timer = max(self.scene.player._invincible_timer, 3.0)
        self._play_final_dialogue(FINAL_SEQ["sengen"], on_done=self._start_karonaru_return)

    def _start_karonaru_return(self) -> None:
        self._final_seq = "return"
        self._show_final_banner("kouhatsu", 3.0)
        self.scene._boss_kill_flash_timer = 1.2   # 白閃光
        self.scene.game.sound.play_bgm("music/bgm/Rebirth_the_edge.mp3", volume=0.7)
        self.scene.game.sound.play_se_alias("SE_LIGHT")
        self._spawn_returning_karonaru()
        self._play_final_dialogue(FINAL_SEQ["return"], on_done=self._start_karonaru_return_join)

    def _spawn_returning_karonaru(self) -> None:
        scene = self.scene
        if scene._companion is None:
            from src.entities.companion import Karonaru
            scene._companion = Karonaru(scene.game, popup_fn=scene._spawn_popup,
                                        spawn_heal_fn=scene._companion_spawn_heal)
        companion = scene._companion
        arrival_y = float(scene.player.rect.centery) + 18.0
        end_x = max(62.0, float(scene.player.rect.centerx) - 76.0)
        start = (-48.0, arrival_y)
        end = (end_x, arrival_y)
        companion.sx, companion.sy = start
        companion.rect.center = (int(companion.sx), int(companion.sy))
        self._karonaru_arrival_duration = 1.65
        self._karonaru_arrival_timer = self._karonaru_arrival_duration
        self._karonaru_arrival_from = start
        self._karonaru_arrival_to = end
        self._karonaru_arrival_pos = start
        self._karonaru_arrival_trail = [(start[0], start[1], 0.45)]
        scene.game.sound.play_se_alias("SE_KARONARU_ARRIVE", volume=0.7)

    def _update_karonaru_arrival_motion(self, dt: float) -> None:
        companion = self.scene._companion
        if companion is None:
            self._karonaru_arrival_timer = 0.0
            return
        dur = max(0.001, self._karonaru_arrival_duration)
        self._karonaru_arrival_timer = max(0.0, self._karonaru_arrival_timer - dt)
        t = 1.0 - self._karonaru_arrival_timer / dur
        ease = 1.0 - (1.0 - t) ** 3
        sx0, sy0 = self._karonaru_arrival_from
        sx1, sy1 = self._karonaru_arrival_to
        companion.sx = sx0 + (sx1 - sx0) * ease
        companion.sy = sy0 + (sy1 - sy0) * ease
        companion.rect.center = (int(companion.sx), int(companion.sy))
        self._karonaru_arrival_pos = (companion.sx, companion.sy)
        self._karonaru_arrival_trail.append((companion.sx, companion.sy, 0.55))
        self._karonaru_arrival_trail = [
            (x, y, life - dt) for x, y, life in self._karonaru_arrival_trail
            if life - dt > 0.0
        ]

    def _decay_karonaru_arrival_trail(self, dt: float) -> None:
        self._karonaru_arrival_trail = [
            (x, y, life - dt) for x, y, life in self._karonaru_arrival_trail
            if life - dt > 0.0
        ]

    def draw_arrival_trail(self, surf: pygame.Surface) -> None:
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
        scene = self.scene
        if scene._companion is None:
            self._spawn_returning_karonaru()
        companion = scene._companion
        if self._karonaru_arrival_timer > 0:
            self._karonaru_arrival_timer = 0.0
            companion.sx, companion.sy = self._karonaru_arrival_to
            companion.rect.center = (int(companion.sx), int(companion.sy))
        self._final_seq = "return_join"
        self._karonaru_return_timer = 0.0
        self._karonaru_return_from = (float(companion.sx), float(companion.sy))
        self._karonaru_return_to = (
            float(scene.player.rect.centerx) - 52.0,
            float(scene.player.rect.centery) + 18.0,
        )
        scene.game.sound.play_se_alias("SE_LIGHT")

    def _do_karonaru_max(self) -> None:
        scene = self.scene
        if scene._companion is None:
            from src.entities.companion import Karonaru
            scene._companion = Karonaru(scene.game, popup_fn=scene._spawn_popup,
                                        spawn_heal_fn=scene._companion_spawn_heal)
            scene._companion.sx = float(scene.player.rect.centerx) - 50.0
            scene._companion.sy = float(scene.player.rect.centery) + 16.0
        companion = scene._companion
        companion.set_max()
        companion.reseed_trail(scene.player)
        self._karonaru_heal_player()
        scene.game.story.karonaru_lost        = False
        # Story flags for Karonaru return.
        scene.game.story.karonaru_available   = True
        scene.game.story.karonaru_max         = True
        scene.game.story.final_self_distanced = True
        self._show_final_banner("anti_rumin", 3.0)
        # Start the anti-rumination field and final gauge.
        from src.entities.enemies.boss import _FORM3_ACT2_HP
        if scene._boss is not None:
            scene._boss.begin_act2(_FORM3_ACT2_HP)
        self._final_phase = 2
        scene._boss_mid_dialogue_shown = False
        self._play_final_dialogue(FINAL_SEQ["act2_start"], on_done=self._resume_final_combat)

    def _karonaru_heal_player(self) -> None:
        scene = self.scene
        before = scene.player.hp
        scene.player.hp = scene.player.max_hp
        scene.player._invincible_timer = max(scene.player._invincible_timer, 2.8)
        healed = max(0, scene.player.hp - before)
        px, py = scene.player.rect.center
        scene._spawn_popup(
            "HP FULL RECOVER" if healed > 0 else "HP SECURED",
            px,
            scene.player.rect.top - 26,
            color=(160, 255, 190),
            life=2.4,
        )
        scene.particles.spawn_glow(px, py, color=(160, 255, 190), count=28, speed=85.0)
        scene.particles.spawn_spark(px, py, color=(225, 255, 210), count=16, speed=260.0)
        if scene._companion is not None:
            scene.particles.spawn_glow(
                scene._companion.sx,
                scene._companion.sy,
                color=(220, 255, 230),
                count=18,
                speed=70.0,
            )
        scene.game.sound.play_se_alias("SE_HEAL", volume=0.8)

    def _resume_final_combat(self) -> None:
        self._final_seq = ""

    def _start_final_sengen(self) -> None:
        self._final_seq = "final_sengen"
        self.scene.enemy_bullets.empty()
        self._sengen_overlay_timer = 2.0
        self._show_final_banner("final_sengen", 2.6)
        self._play_final_dialogue(FINAL_SEQ["final_sengen"], on_done=self._arm_final_kill)

    def _arm_final_kill(self) -> None:
        if self.scene._boss is not None:
            self.scene._boss.arm_final_kill()
        self._show_final_banner("final_chance", 2.4)
        self.scene._spawn_popup("NOW STRIKE", SCREEN_WIDTH // 2, 120, color=(255, 230, 150), life=2.0)
        self._final_seq = "final_chance"

    # ── 公開/内部: 最終決戦 描画 ──────────────────────────────────
    def draw_overlays(self, screen: pygame.Surface) -> None:
        if self._sengen_overlay_timer > 0:
            self._draw_sengen_overlay(screen)
        if self._final_banner_timer > 0:
            self._draw_final_banner(screen)
        if self._final_dialogue_active:
            self._draw_final_dialogue(screen)

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
        big   = self.scene.game.resources.pixelfont(40)
        small = self.scene.game.resources.pixelfont(22)
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
            self._final_dialogue_font = self.scene.game.resources.pixelfont(26)
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
            self.scene.game.resources,
            line.speaker,
            line.lines,
            page_index=idx,
            total_pages=total,
            hint_text=hint,
            style=COMBAT_PURPLE_STYLE,
        )
