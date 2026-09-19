"""Authored challenge rooms and restart boundaries owned by the active scene."""
from __future__ import annotations
import copy
import math
import random
import pygame
from src.core.balance import PLAYER_MAX_HP
from src.core.constants import SCREEN_WIDTH
from src.entities.terrain_query import iter_collidable_terrain


def terrain_key(terrain):
    return (type(terrain).__name__, getattr(terrain, "world_x", 0),
            getattr(terrain, "world_y", terrain.rect.y), terrain.rect.size)


class LearningEncounter:
    """Kill two emitters to open a wave; their attack schedule is repeatable."""
    def __init__(self, scene, config):
        self.scene, self.config = scene, config
        self.wave = 0
        self.time = 0.0
        self.next_event = 0
        self.emitters = []
        self.pending = {}
        self.warning_sprites = {}
        self.pause = 0.8
        self.complete = False
        self.start_wave()

    def start_wave(self):
        from src.entities.enemies.turret import EnemyTurret
        scene = self.scene
        self.emitters = []
        for index, fraction in enumerate((0.30, 0.70)):
            x = scene.camera.x + 600 + 60 * index
            top, bottom = scene.spawner._safe_y_bounds(x, margin=75)
            y = top + (bottom-top) * fraction
            turret = EnemyTurret(scene.game, x, y, surface="top" if index == 0 else "bottom")
            turret.hp = self.config["emitter_hp"]
            turret.drops_enabled = False
            turret.learning_emitter = True
            turret.update(0, scene.camera)
            scene.enemies.add(turret)
            self.emitters.append(turret)
        self.time = 0.0
        self.next_event = 0
        self.pending = {}
        self.warning_sprites = {}

    def _schedule(self):
        pattern = self.config["pattern"]
        if pattern == 1:
            return ((.7, "aim", 0), (1.15, "aim", 0), (1.6, "aim", 0),
                    (2.35, "fan", 1), (2.9, "fan", 1))
        if pattern == 2:
            return ((.4, "warn", 0), (1.6, "beam", 0),
                    (2.6, "warn", 1), (3.8, "beam", 1))
        if pattern == 3:
            return ((.5, "fan", 0), (1.05, "fan", 1),
                    (2.0, "warn_column", 0), (3.2, "beam", 0), (3.8, "aim", 1))
        return ((.4, "warn_column", 0), (1.6, "beam", 0),
                (2.5, "warn_column", 1), (3.7, "beam", 1), (4.1, "fan", 0))

    def attack(self, action, index):
        from src.entities.bullets.enemy_bullet import EnemyBullet
        from src.entities.bullets.laser_fx import LaserBeamSprite, ZUNDA_PALETTE
        emitter = self.emitters[index]
        if not emitter.alive():
            return
        scene = self.scene
        x, y = emitter.rect.center
        px, py = scene.player.hit_rect.center
        if action in ("aim", "fan"):
            angle = math.atan2(py-y, px-x)
            spread = (-16, 0, 16) if action == "fan" else (0,)
            for offset in spread:
                a = angle + math.radians(offset)
                scene.enemy_bullets.add(EnemyBullet(x, y, math.cos(a)*235,
                                                      math.sin(a)*235, radius=6))
            scene.game.sound.play_se_alias("SE_ENEMY_SHOT", volume=.35)
        elif action.startswith("warn"):
            if action == "warn_column":
                rect = pygame.Rect(max(55, min(475, px-32)), 90, 64, 420)
            else:
                top, bottom = scene.spawner._safe_y_bounds(scene.camera.x + px, margin=65)
                center = max(top+72, min(bottom-72, py))
                rect = pygame.Rect(0, int(center-60), x, 120)
            self.pending[index] = rect
            warning = LaserBeamSprite(*rect.center, *rect.size,
                palette=ZUNDA_PALETTE, lifetime=1.3, warning_only=True)
            self.warning_sprites[index] = warning
            scene.enemy_bullets.add(warning)
        elif action == "beam" and index in self.pending:
            rect = self.pending.pop(index)
            self.warning_sprites.pop(index).kill()
            scene.enemy_bullets.add(LaserBeamSprite(*rect.center, *rect.size,
                palette=ZUNDA_PALETTE, lifetime=.7, damage=32, warning_only=False))
            scene.game.sound.play_se_alias("SE_LASER_FIRE", volume=.35)

    def draw(self, screen):
        for emitter in self.emitters:
            if emitter.alive():
                bar = pygame.Rect(emitter.rect.left, emitter.rect.top-8, 40, 3)
                pygame.draw.rect(screen, (35,48,56), bar)
                bar.width = max(0, round(40*emitter.hp/self.config["emitter_hp"]))
                pygame.draw.rect(screen, (155,235,220), bar)

    def update(self, dt):
        for index, emitter in enumerate(self.emitters):
            if not emitter.alive():
                warning = self.warning_sprites.pop(index, None)
                if warning is not None:
                    warning.kill()
                self.pending.pop(index, None)
        if not any(e.alive() for e in self.emitters):
            self.pause -= dt
            if self.pause <= 0:
                self.wave += 1
                if self.wave >= self.config["waves"]:
                    self.complete = True
                else:
                    self.pause = 1.0
                    self.start_wave()
            return
        self.time += dt
        schedule = self._schedule()
        while self.next_event < len(schedule) and self.time >= schedule[self.next_event][0]:
            _, action, index = schedule[self.next_event]
            self.attack(action, index)
            self.next_event += 1
        if self.time >= self.config["cycle"]:
            self.time -= self.config["cycle"]
            self.next_event = 0


class GameSceneLearningMixin:
    def _init_learning(self):
        self._learning_rest_done = False
        self._learning_done = False
        self._learning_encounter = None
        self._checkpoint_boss_saved = False
        shared = self.game.shared
        cp = shared.checkpoint
        if shared.resume_checkpoint and cp and cp["stage"] == self._stage_id:
            shared.resume_checkpoint = False
            self._restore_checkpoint(cp)
        elif not self._is_debug_stage:
            self._save_checkpoint("road", "章のはじめ", refill=False)

    def _safe_restart_position(self, wanted=(120, 280)):
        obstacles = list(iter_collidable_terrain(self.terrain))
        candidates = [(x, y) for x in (120, 180, 240, 80, 300)
                      for y in range(90, 500, 12)]
        for x, y in sorted(candidates, key=lambda pos: math.dist(pos, wanted)):
            rect = self.player.rect.copy()
            rect.topleft = x, y
            if not any(rect.colliderect(t.rect) for t in obstacles):
                self.player.sx, self.player.sy = float(x), float(y)
                self.player.rect.topleft = x, y
                self.player._entering = False
                return
        raise RuntimeError("No safe checkpoint position in authored terrain")

    def _save_checkpoint(self, kind, label, *, refill=True):
        if self._is_debug_stage:
            return
        if refill:
            self.player.hp = PLAYER_MAX_HP
            self.enemy_bullets.empty()
            self.player_bullets.empty()
            from src.entities.laser_beam import LaserBeam
            self.laser = LaserBeam()
            self.player._invincible_timer = 0
            self.player._cooldown = 0
            if self._heat:
                from src.core.battle_systems import HeatSystem
                self._heat = HeatSystem()
            if self._companion:
                self._companion.rest(self.player)
        companion = self._companion.snapshot() if self._companion else self.game.shared.stage_start_companion
        self.game.shared.checkpoint = copy.deepcopy(dict(
            stage=self._stage_id, kind=kind, label=label, camera_x=self.camera.x,
            player_position=(self.player.sx, self.player.sy),
            world_index=self.spawner._world_index, event_index=self.spawner._index,
            elapsed=self._stage_elapsed, weapon=self.player.weapon.snapshot(),
            companion=companion, story=self.game.story.snapshot(),
            score=self.game.shared.score, kills=self.game.shared.kill_count,
            support_pickups=self.game.shared.support_pickups, rng=random.getstate(),
            rest_done=self._learning_rest_done, challenge_done=self._learning_done,
            terrain={terrain_key(t):getattr(t,"hp",None) for t in self.terrain},
        ))

    def _restore_checkpoint(self, cp):
        self.camera.x = cp["camera_x"]
        self.spawner._world_index = cp["world_index"]
        self.spawner._index = cp["event_index"]
        self.spawner._elapsed = self.stage.elapsed = self._stage_elapsed = cp["elapsed"]
        self.spawner.spawn_terrain_events(self.stage.world_events[:cp["world_index"]], self.camera)
        self.terrain.update(0, self.camera)
        self.player.restore_state(PLAYER_MAX_HP, cp["weapon"])
        self._learning_rest_done = cp["rest_done"]
        self._learning_done = cp["challenge_done"]
        self._stage_banner_timer = 0
        self._bgm_delay = .1
        self._safe_restart_position(cp["player_position"])
        if self._companion:
            if cp["companion"]:
                self._companion.restore_state(cp["companion"])
            if cp["kind"] == "final_pair":
                self._companion.set_max()
            self._companion.rest(self.player)
        if cp["kind"] in ("boss", "final", "final_pair"):
            self._active_boss_stage_id = self._stage_id
            self._prepare_boss_terrain(self._stage_id)
            self.spawner.confirm_spawn_boss(self._stage_id)
            self._boss = self.spawner.boss
            self._boss.camera = self.camera
            self._boss.summon_turret_fn = self._summon_boss_turrets
            self._boss.video_effect_fn = self._play_video_effect
            self._boss.sx, self._boss.sy = 580., 300.
            self._boss._state = "fight"
            self._boss.rect.center = (580, 300)
            if cp["kind"] in ("final", "final_pair"):
                self._boss._form2 = True
                self._boss._transform_form3()
                self._final._final_phase = 1
                if cp["kind"] == "final_pair":
                    from src.entities.enemies.boss import _FORM3_ACT2_HP
                    self._boss.begin_act2(_FORM3_ACT2_HP)
                    self._final._final_phase = 2
            self._boss_intro_state = "fight_banner"
            self._boss_intro_timer = .8
            self._checkpoint_boss_saved = True
            self.camera.scroll_speed = 0
            self.spawner.skip_all_events()
            from src.scenes.game.config import BOSS_BGM
            self._bgm_path = BOSS_BGM[self._stage_id]
        for terrain in list(self.terrain):
            key = terrain_key(terrain)
            if key not in cp["terrain"]:
                terrain.kill()
            elif cp["terrain"][key] is not None:
                terrain.hp = cp["terrain"][key]
        self._safe_restart_position(cp["player_position"])
        random.setstate(cp["rng"])
        self._spawn_popup("再挑戦", self.player.rect.centerx, self.player.rect.top-22,
                          color=(140,230,205),life=1.0)

    def _update_learning(self, dt):
        config = self.stage.learning
        if (not config or self._boss_intro_state or self._post_boss
                or self._pending_boss_stage_id is not None or self._boss is not None):
            return
        # Let visible authored rewards be collected or scroll away before clearing
        # the approach. A rest point must never silently delete a reward in reach.
        pending_reward = any(type(item).__name__ == "WeaponItem" and item.rect.right > 0
                             for item in self.items)
        pending_reward |= any(getattr(enemy, "fixed_drop", None) == "WeaponItem"
                              and enemy.rect.right > 0 for enemy in self.enemies)
        if (not self._learning_rest_done and self.camera.x >= config["checkpoint_x"]
                and not pending_reward):
            self._learning_rest_done = True
            self.enemies.empty()
            self.items.empty()
            self._save_checkpoint("road", config["name"])
            self._spawn_popup("休息地点 / HP回復", 210, 108, color=(140,230,205),life=2)
        if self._learning_rest_done and not self._learning_done:
            if self._learning_encounter is None and self.camera.x >= config["encounter_x"]:
                self.enemies.empty()
                self.enemy_bullets.empty()
                self.camera.scroll_speed = 0
                self._learning_encounter = LearningEncounter(self, config)
                self._spawn_popup(config["name"], 400, 110, color=(255,185,100),life=2)
                self._spawn_popup("砲台を倒して進め", 400, 138, color=(180,230,215),life=2)
            if self._learning_encounter:
                self._learning_encounter.update(dt)
                if self._learning_encounter.complete:
                    self._learning_encounter = None
                    self._learning_done = True
                    self.camera.scroll_speed = self._stage_scroll_speed
                    self.enemy_bullets.empty()
                    self._spawn_popup("突破", 400, 110, color=(140,230,205),life=1.4)
