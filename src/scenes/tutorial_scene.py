"""対話型チュートリアル（準備運動）。

カロナール先輩が澤口をコーチする体裁の、物語組込み・プレイアブルな導入。
GameScene（神ファイル）には触れず、Player / 弾 / パーティクル / Camera を
流用した専用の軽量シーン。台本 SSOT は src/story/script.py の TUTORIAL。

ステップ: offer(Yes/No) → move → shoot → dummy登場 → fight(勝敗どちらでも・
無死) → 感想 → on_complete。キャンペーン導入では初回のみ提示し、タイトルの
「チュートリアル」からは offer 無しで即プレイ（再生）する。
"""
from __future__ import annotations

import math
from typing import Callable

import pygame

from src.core.scene import Scene
from src.core.camera import Camera
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.entities.player import Player
from src.entities.bullet import Bullet
from src.entities.particle import ParticleSystem
from src.scenes.dialogue_panel import draw_combat_panel, COMBAT_RED_STYLE, COMBAT_BLUE_STYLE
from src.scenes.meta_ui import draw_meta_panel, draw_meta_footer, wrap_text
from src.story import script
from src.story.speakers import KARONARU

_TARGET_SHOTS = 6      # 「撃つ」ステップ完了に必要な発射数
_LOSE_HITS    = 3      # 被弾がこの回数に達したら（無死で）終了
_DUMMY_HP     = 18


class _DummyBullet(Bullet):
    """練習用インフル人形が撃つ、遅くて避けやすい弾。"""

    def __init__(self, wx: float, wy: float, vx: float, vy: float) -> None:
        super().__init__(wx, wy, vx=vx, vy=vy, damage=1)
        self.image = pygame.Surface((14, 14), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (255, 110, 110), (7, 7), 7)
        pygame.draw.circle(self.image, (255, 220, 220), (7, 7), 3)
        self.rect = self.image.get_rect(center=(int(wx), int(wy)))


class _DummyTarget(pygame.sprite.Sprite):
    """練習用インフル人形。HP を持ち、遅い弾をたまに撃つ。倒れても喋る。"""

    def __init__(self, game, sx: float, sy: float) -> None:
        super().__init__()
        raw = game.resources.image("graphic/enemy_バイキンマン68x80.png")
        self.image0 = pygame.transform.smoothscale(raw, (66, 78)).convert_alpha()
        self.image = self.image0
        self.sx, self.sy = float(sx), float(sy)
        self.rect = self.image.get_rect(center=(int(sx), int(sy)))
        self.hp = self.max_hp = _DUMMY_HP
        self._t = 0.0
        self._flash = 0.0
        self._fire_cd = 1.6

    @property
    def hit_rect(self) -> pygame.Rect:
        return self.rect.inflate(-10, -12)

    def hit(self, dmg: int, particles: ParticleSystem) -> None:
        self.hp = max(0, self.hp - dmg)
        self._flash = 0.10
        particles.spawn_hit(self.rect.centerx, self.rect.centery, count=6)

    def update(self, dt: float, player: Player, enemy_bullets: pygame.sprite.Group) -> None:
        self._t += dt
        self.rect.centerx = int(self.sx)
        self.rect.centery = int(self.sy + math.sin(self._t * 2.0) * 16)
        if self._flash > 0:
            self._flash -= dt
        if self.hp <= 0:
            return
        self._fire_cd -= dt
        if self._fire_cd <= 0.0:
            self._fire_cd = 1.5
            px, py = player.rect.center
            dx, dy = px - self.rect.centerx, py - self.rect.centery
            d = math.hypot(dx, dy) or 1.0
            spd = 155.0
            enemy_bullets.add(_DummyBullet(
                self.rect.centerx, self.rect.centery, dx / d * spd, dy / d * spd))

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self.image0, self.rect)
        if self._flash > 0:
            flash = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            flash.fill((255, 255, 255, 150))
            surf.blit(flash, self.rect, special_flags=pygame.BLEND_RGBA_ADD)
        if 0 < self.hp < self.max_hp:
            w, h = 60, 5
            x, y = self.rect.centerx - w // 2, self.rect.top - 12
            pygame.draw.rect(surf, (40, 20, 20), (x, y, w, h))
            pygame.draw.rect(surf, (120, 220, 140), (x, y, int(w * self.hp / self.max_hp), h))


class TutorialScene(Scene):
    """対話型チュートリアル本体。

    Parameters
    ----------
    on_complete : 終了時に呼ぶコールバック。省略時はタイトルへ戻る（再生用）。
    with_offer  : True なら冒頭で「準備運動する？」の Yes/No を出す
                  （キャンペーン導入）。False は即プレイ（タイトルからの再生）。
    """

    def __init__(self, game, on_complete: Callable[[], None] | None = None,
                 with_offer: bool = False) -> None:
        super().__init__(game)
        self._with_offer = with_offer
        if on_complete is not None:
            self._on_complete = on_complete
        else:
            def _back_to_title() -> None:
                from src.scenes.title import TitleScene
                self.game.change_scene(TitleScene(self.game))
            self._on_complete = _back_to_title

    # ── ライフサイクル ────────────────────────────────────────────
    def on_enter(self) -> None:
        self.camera = Camera(scroll_speed=0.0)   # スクロールしない練習場
        self.player = Player(self.game)
        self.particles = ParticleSystem()
        self.player_bullets: pygame.sprite.Group = pygame.sprite.Group()
        self.enemy_bullets:  pygame.sprite.Group = pygame.sprite.Group()
        self._targets: pygame.sprite.Group = pygame.sprite.Group()  # ホーミング候補
        self._dummy: _DummyTarget | None = None
        self._buf = pygame.Surface(self.game.screen.get_size())
        self._banner_font = self.game.resources.pixelfont(24)
        self._instruction_font = self.game.resources.pixelfont(20)
        self._tag_font    = self.game.resources.pixelfont(18)
        self._completed = False

        self._phase = "move"
        self._moved_h = self._moved_v = False
        self._shots = 0
        from src.entities.laser_beam import LaserBeam
        from src.core.battle_systems import HeatSystem
        self.laser = LaserBeam()
        self._heat = HeatSystem()
        self._laser_practiced = False
        self._laser_seconds = 0.0
        self._hits  = 0
        self._won   = False

        self._dialogue: list = []
        self._dialogue_idx = 0
        self._dialogue_then: Callable[[], None] | None = None
        self._hint = None
        self._banner = ""
        self._choosing = False
        self._choice = 0   # 0=はい / 1=いいえ

        if self._with_offer:
            self._say(script.TUTORIAL["offer"], then=self._open_choice)
        else:
            self._start_move()

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    # ── 台詞ヘルパ ────────────────────────────────────────────────
    def _say(self, lines: list, then: Callable[[], None] | None) -> None:
        self._dialogue = list(lines)
        self._dialogue_idx = 0
        self._dialogue_then = then

    @property
    def _in_dialogue(self) -> bool:
        return bool(self._dialogue)

    def _advance_dialogue(self) -> None:
        self._dialogue_idx += 1
        if self._dialogue_idx >= len(self._dialogue):
            then = self._dialogue_then
            self._dialogue = []
            self._dialogue_then = None
            if then is not None:
                then()

    # ── ステップ遷移 ──────────────────────────────────────────────
    def _open_choice(self) -> None:
        self._choosing = True
        self._choice = 0

    def _start_move(self) -> None:
        self._phase = "move"
        self._banner = "準備運動：移動"
        self._hint = script.TUTORIAL["move_hint"][0]
        self._moved_h = self._moved_v = False

    def _start_shoot(self) -> None:
        self._phase = "shoot"
        self._banner = "準備運動：射撃"
        self._hint = script.TUTORIAL["shoot_hint"][0]
        self._shots = 0

    def _start_laser(self) -> None:
        self._phase = "laser"
        self._banner = "準備運動：レーザー"
        self._hint = script.TUTORIAL["laser_hint"][0]
        self.player.weapon.laser_level = 1

    def _start_dummy(self) -> None:
        self._phase = "dummy"
        self._banner = ""
        self._hint = None
        self._dummy = _DummyTarget(self.game, SCREEN_WIDTH * 0.72, SCREEN_HEIGHT * 0.5)
        self._targets.add(self._dummy)
        self.game.sound.play_se_alias("SE_ALERT", volume=0.5)
        self._say(script.TUTORIAL["dummy"], then=self._start_fight)

    def _start_fight(self) -> None:
        self._phase = "fight"
        self._banner = "準備運動：実戦"
        self._hint = None
        self._hits = 0

    def _end_fight(self, won: bool) -> None:
        self._won = won
        self._phase = "result"
        self._banner = ""
        self.enemy_bullets.empty()
        self._say(script.TUTORIAL["win" if won else "lose"], then=self._start_outro)

    def _start_outro(self) -> None:
        self._phase = "outro"
        self._say(script.TUTORIAL["outro"], then=self._finish)

    def _finish(self) -> None:
        if not self._completed:
            self._completed = True
            self._on_complete()

    def _exit_key(self) -> int | None:
        # A shared gameplay/back binding must not end practice while shooting.
        settings = self.game.settings
        used = {settings.get_key(action) for action in
                ("fire", "laser", "move_left", "move_right", "move_up", "move_down")}
        back = settings.get_key("ui_back")
        if back not in used:
            return back
        return pygame.K_ESCAPE if pygame.K_ESCAPE not in used else None

    def _exit_hint(self) -> str:
        key = self._exit_key()
        if key is None:
            return ""
        name = self.game.settings.key_display("ui_back") if key == self.game.settings.get_key("ui_back") else "ESC"
        return f"{name}: 準備運動を終了"

    # ── 更新 ──────────────────────────────────────────────────────
    def update(self, dt: float) -> None:
        inp = self.game.input
        if self._completed:
            return
        exit_key = self._exit_key()
        if exit_key is not None and inp.is_just_pressed(exit_key):
            self._finish()
            return
        self.camera.update(dt)
        self.particles.update(dt)

        if self._choosing:
            if inp.is_just_pressed(pygame.K_LEFT) or inp.is_just_pressed(pygame.K_RIGHT):
                self._choice ^= 1
                self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
            if (inp.is_action_just_pressed("ui_accept")
                    or inp.is_action_just_pressed("fire")):
                self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
                self._choosing = False
                if self._choice == 0:
                    self._say(script.TUTORIAL["accept"], then=self._start_move)
                else:
                    self._say(script.TUTORIAL["skip"], then=self._finish)
            return

        if self._in_dialogue:
            if (inp.is_action_just_pressed("ui_accept")
                    or inp.is_action_just_pressed("fire")):
                self._advance_dialogue()
            return

        self.player.update(dt)
        if self._phase in ("move", "shoot", "laser", "fight"):
            self._update_combat(dt, inp)

    def _update_combat(self, dt: float, inp) -> None:
        if self.player.shoot_requested:
            wx, wy = self.player.muzzle_world(self.camera)
            for b in self.player.weapon.get_bullets(wx, wy, self._targets,
                                                    game=self.game, boss=None):
                self.player_bullets.add(b)
            self.game.sound.play_se_alias("SE_NORMALSHOT", volume=0.35)
            self._shots += 1

        self.player_bullets.update(dt, self.camera)
        self.enemy_bullets.update(dt, self.camera)
        for b in list(self.player_bullets):
            if b.is_off_screen(self.camera):
                b.kill()
        for b in list(self.enemy_bullets):
            if b.is_off_screen(self.camera):
                b.kill()

        if self._dummy is not None:
            self._dummy.update(dt, self.player, self.enemy_bullets)
            for b in list(self.player_bullets):
                if self._dummy.hp > 0 and b.rect.colliderect(self._dummy.hit_rect):
                    self._dummy.hit(getattr(b, "damage", 1), self.particles)
                    b.kill()

        if not self.player.is_invincible:
            for b in list(self.enemy_bullets):
                if b.rect.colliderect(self.player.hit_rect):
                    b.kill()
                    self._hits += 1
                    self.player.take_damage(1)
                    self.particles.spawn_player_hit(self.player.sx, self.player.sy)
                    self.camera.shake(8.0)
                    break

        if self._phase == "move" and not self.player._entering:
            if inp.is_action_pressed("move_left") or inp.is_action_pressed("move_right"):
                self._moved_h = True
            if inp.is_action_pressed("move_up") or inp.is_action_pressed("move_down"):
                self._moved_v = True
            if self._moved_h and self._moved_v:
                self._hint = None
                self._say(script.TUTORIAL["move_done"], then=self._start_shoot)
        elif self._phase == "shoot":
            if self._shots >= _TARGET_SHOTS:
                self._hint = None
                self._say(script.TUTORIAL["shoot_done"], then=self._start_laser)
        elif self._phase == "laser":
            from src.core.balance import HEAT_LASER_PER_SEC
            self._heat.update(dt, laser_active=self.laser.is_active)
            self.laser.update(dt, self.player.laser_fire_held and not self._heat.overheated)
            if self.laser.is_active:
                self._heat.add(HEAT_LASER_PER_SEC * dt)
                self._laser_seconds += dt
                self._laser_practiced |= self._laser_seconds >= .5
            if self._laser_practiced and not self.player.laser_fire_held and self._heat.heat <= 5:
                self.player.weapon.laser_level = 0
                self.laser.state = "ready"
                self._start_dummy()
        elif self._phase == "fight" and self._dummy is not None:
            if self._dummy.hp <= 0:
                self.particles.spawn_big_explosion(self._dummy.rect.centerx, self._dummy.rect.centery)
                self.game.sound.play_se("music/se/game_explosion9.mp3", volume=0.3)
                self._end_fight(won=True)
            elif self._hits >= _LOSE_HITS:
                self._end_fight(won=False)

    # ── 描画 ──────────────────────────────────────────────────────
    def draw(self, screen: pygame.Surface) -> None:
        buf = self._buf
        buf.fill((14, 12, 22))
        for gx in range(0, SCREEN_WIDTH, 48):
            pygame.draw.line(buf, (24, 22, 36), (gx, 0), (gx, SCREEN_HEIGHT))
        for gy in range(0, SCREEN_HEIGHT, 48):
            pygame.draw.line(buf, (24, 22, 36), (0, gy), (SCREEN_WIDTH, gy))

        if self._dummy is not None:
            self._dummy.draw(buf)
        self.player.draw(buf)
        if self._phase == "laser" and not self._in_dialogue:
            self.laser.draw(buf, *self.player.muzzle_screen())
        self.player_bullets.draw(buf)
        self.enemy_bullets.draw(buf)
        self.particles.draw(buf)

        ox, oy = self.camera.shake_offset
        screen.blit(buf, (ox, oy))

        # ── UI（シェイクしない）──
        if self._banner:
            self._draw_banner(screen)

        if self._choosing:
            self._draw_choice(screen)
        elif self._in_dialogue:
            self._draw_panel(screen, self._dialogue[self._dialogue_idx], blocking=True)
        elif self._hint is not None:
            self._draw_panel(screen, self._hint, blocking=False)
        if self._exit_hint():
            draw_meta_footer(screen, self._tag_font, self._exit_hint())

    def _draw_banner(self, screen: pygame.Surface) -> None:
        heading, instruction, progress = self._practice_labels()
        lines = wrap_text(self._instruction_font, instruction, SCREEN_WIDTH - 96)
        height = 94 + len(lines) * self._instruction_font.get_linesize()
        rect = pygame.Rect(24, 20, SCREEN_WIDTH - 48, height)
        draw_meta_panel(screen, rect)
        title = self._banner_font.render(heading, True, (240, 219, 158))
        screen.blit(title, (48, 30))
        y = 70
        for line in lines:
            screen.blit(self._instruction_font.render(line, True, (230, 236, 248)), (48, y))
            y += self._instruction_font.get_linesize()
        screen.blit(self._tag_font.render(progress, True, (172, 222, 198)), (48, y + 5))

    def _practice_labels(self) -> tuple[str, str, str]:
        key = self.game.settings.key_display
        if self._phase == "move":
            instruction = f'{key("move_left")} / {key("move_right")}：左右　{key("move_up")} / {key("move_down")}：上下'
            progress = f'左右の移動：{"完了" if self._moved_h else "未完了"}　上下の移動：{"完了" if self._moved_v else "未完了"}'
            return "準備運動  1 / 4  移動", instruction, progress
        if self._phase == "shoot":
            return ("準備運動  2 / 4  射撃", f'{key("fire")} を長押しして連射',
                    f"発射した回数：{min(self._shots, _TARGET_SHOTS)} / {_TARGET_SHOTS}")
        if self._phase == "laser":
            instruction = (f'{key("laser")} を押して発射、離して冷やす'
                           if not self._laser_practiced else f'{key("laser")} を離して冷やそう')
            return "準備運動  3 / 4  レーザー", instruction, f"体温 {self._heat.display_temp:.1f}℃"
        hp = self._dummy.hp if self._dummy is not None else _DUMMY_HP
        return ("準備運動  4 / 4  実戦", f'{key("fire")} で人形を撃つ。弾を避けながら動こう',
                f"人形のHP：{hp} / {_DUMMY_HP}　被弾：{self._hits} / {_LOSE_HITS}（失敗しても進めます）")

    def _draw_choice(self, screen: pygame.Surface) -> None:
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        veil = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        veil.fill((3, 7, 16, 190))
        screen.blit(veil, (0, 0))
        draw_meta_panel(screen, pygame.Rect(64, 172, SCREEN_WIDTH - 128, 224))
        # 直前の offer 台詞（問い）を選択肢の上に残して文脈を保つ
        prompt = script.TUTORIAL["offer"][-1].lines[0]
        for row, text in enumerate(wrap_text(self._banner_font, prompt, SCREEN_WIDTH - 192)):
            q = self._banner_font.render(text, True, (235, 239, 249))
            screen.blit(q, (cx - q.get_width() // 2, 190 + row * self._banner_font.get_linesize()))
        for i, label in enumerate(("準備運動する", "そのまま進む")):
            sel = (i == self._choice)
            surf = self._instruction_font.render(label, True,
                                            (255, 235, 150) if sel else (170, 170, 180))
            bw, bh = 260, 52
            bx = cx + (i * 2 - 1) * 142 - bw // 2
            box = pygame.Surface((bw, bh), pygame.SRCALPHA)
            box.fill((33, 57, 83, 245) if sel else (12, 20, 37, 235))
            pygame.draw.rect(box, (255, 220, 120) if sel else (90, 90, 110), box.get_rect(), 3)
            screen.blit(box, (bx, cy))
            if sel:
                pygame.draw.polygon(screen, (255, 235, 150),
                                    [(bx + 14, cy + 18), (bx + 14, cy + 34), (bx + 23, cy + 26)])
            screen.blit(surf, (bx + 34, cy + 10))

        fire = self.game.settings.key_display("fire")
        accept = self.game.settings.key_display("ui_accept")
        controls = self._tag_font.render(
            f"← →：選択　{fire} / {accept}：決定", True, (220, 220, 235)
        )
        hint_y = cy + self._banner_font.get_height() + 34
        screen.blit(controls, (cx - controls.get_width() // 2, hint_y))

    def _draw_panel(self, screen: pygame.Surface, line, blocking: bool) -> None:
        speaker = line.speaker
        style = COMBAT_BLUE_STYLE if speaker == KARONARU else COMBAT_RED_STYLE
        if blocking:
            accept = self.game.settings.key_display("ui_accept")
            fire = self.game.settings.key_display("fire")
            keys = accept if accept == fire else f"{accept} / {fire}"
            hint = f"{keys}: 次へ"
        else:
            hint = None
        draw_combat_panel(screen, self.game.resources, speaker, line.lines,
                          hint_text=hint, style=style)
