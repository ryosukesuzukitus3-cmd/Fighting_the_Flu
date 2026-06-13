"""ボス撃破後フェーズ ミックスイン — GameScene に多重継承で組み込まれる。"""
from __future__ import annotations
import math
import random
from pathlib import Path
import pygame

from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
import pygame
from src.scenes.game.config import (
    POST_BOSS_AUTO_TIMEOUT, POST_BOSS_FINAL_TIMEOUT, POST_BOSS_EDGE_MARGIN,
    MAGNET_SPEED, FINAL_SLOW_FACTOR,
    UPGRADE_SLOTS, random_item,
)
from src.story.script import BOSS_DEFEAT
from src.entities.items.weapon_item import WeaponItem as _WeaponItem
from src.entities.items.heal import HealItem as _HealItem


class GameScenePostBossMixin:
    """ボス撃破後のスロー演出・アイテム取得・ステージ遷移を担当する。"""

    def _update_post_boss_phase(self, dt: float) -> None:
        """ボス撃破後フェーズのゲームロジック全体を更新する。"""
        dt_eff = dt * self._post_boss_slow  # type: ignore[attr-defined]

        self.camera.update(dt)  # type: ignore[attr-defined]   # シェイク減衰は実時間で継続

        # 残弾を動かして画面外で消す
        for bullet in list(self.player_bullets):  # type: ignore[attr-defined]
            bullet.update(dt_eff, self.camera)  # type: ignore[attr-defined]
            if bullet.is_off_screen(self.camera):  # type: ignore[attr-defined]
                bullet.kill()
        for bullet in list(self.enemy_bullets):  # type: ignore[attr-defined]
            bullet.update(dt_eff)
            if bullet.is_off_screen():
                bullet.kill()
        self.particles.update(dt_eff)  # type: ignore[attr-defined]

        # 追加爆発演出
        for i in range(len(self._boss_boom_timers) - 1, -1, -1):  # type: ignore[attr-defined]
            self._boss_boom_timers[i] -= dt  # type: ignore[attr-defined]
            if self._boss_boom_timers[i] <= 0:  # type: ignore[attr-defined]
                bx = self._boss_boom_x + random.uniform(-60, 60)  # type: ignore[attr-defined]
                by = self._boss_boom_y + random.uniform(-50, 50)  # type: ignore[attr-defined]
                self.particles.spawn_explosion(bx, by, color=(255, 200, 60), count=30)  # type: ignore[attr-defined]
                self.particles.spawn_explosion(bx, by, color=(255, 120, 20), count=20)  # type: ignore[attr-defined]
                self.camera.shake(10.0)  # type: ignore[attr-defined]
                self.game.sound.play_se("music/se/game_explosion9.mp3", volume=0.5)  # type: ignore[attr-defined]
                self._boss_boom_timers.pop(i)  # type: ignore[attr-defined]

        # 爆発演出が終わったらスロー倍率を徐々に 1.0 へ戻す
        if not self._boss_boom_timers and self._post_boss_slow < 1.0:  # type: ignore[attr-defined]
            self._post_boss_slow = min(1.0, self._post_boss_slow + dt * 0.5)  # type: ignore[attr-defined]

        # ── 撃破後セリフ遅延カウントダウン（プレイヤーはフリーズ）──────
        if self._defeat_dialogue_delay > 0:  # type: ignore[attr-defined]
            self._defeat_dialogue_delay -= dt  # type: ignore[attr-defined]
            if self._defeat_dialogue_delay <= 0 and self._defeat_dialogue_pages:  # type: ignore[attr-defined]
                self._defeat_dialogue_active = True  # type: ignore[attr-defined]
            return  # 遅延中は遷移しない

        # ── 撃破後セリフ表示中（ENTERで送る、プレイヤーはフリーズ）──────
        if self._defeat_dialogue_active:  # type: ignore[attr-defined]
            inp = self.game.input  # type: ignore[attr-defined]
            if (inp.is_held_with_repeat(pygame.K_RETURN, 0.25, 0.12)
                    or inp.is_held_with_repeat(pygame.K_SPACE, 0.25, 0.12)):
                self._defeat_dialogue_index += 1  # type: ignore[attr-defined]
                if self._defeat_dialogue_index >= len(self._defeat_dialogue_pages):  # type: ignore[attr-defined]
                    self._defeat_dialogue_active = False  # type: ignore[attr-defined]
            return  # セリフ表示中は遷移しない

        is_final = self._post_boss_next_id is None  # type: ignore[attr-defined]
        if not is_final:
            # ── セリフ終了後: プレイヤー操作・アイテム取得を解放 ────────────
            self.player.update(dt)  # type: ignore[attr-defined]   # プレイヤーはスローなし

            # 試し撃ち（ポストボスフェーズ）
            if self.player.shoot_requested:  # type: ignore[attr-defined]
                wx, wy = self.player.muzzle_world(self.camera)  # type: ignore[attr-defined]
                for bullet in self.player.weapon.get_bullets(  # type: ignore[attr-defined]
                        wx, wy, self.enemies, game=self.game):  # type: ignore[attr-defined]
                    self.player_bullets.add(bullet)  # type: ignore[attr-defined]
                self.game.sound.play_se("music/se/laser.wav", volume=0.6)  # type: ignore[attr-defined]
            if self.player.weapon.has_laser:  # type: ignore[attr-defined]
                msx, msy = self.player.muzzle_screen()  # type: ignore[attr-defined]
                self.laser.laser_level = self.player.weapon.laser_level  # type: ignore[attr-defined]
                just_fired, _ = self.laser.update(dt, self.player.laser_fire_held)  # type: ignore[attr-defined]
                if just_fired:
                    self.game.sound.play_se("music/se/laser.wav", volume=0.225)  # type: ignore[attr-defined]
                    self.camera.shake(6.0)  # type: ignore[attr-defined]
                self.laser.hit_check(self.enemies, None, msx, msy)  # type: ignore[attr-defined]
            else:
                self.laser.state = "ready"  # type: ignore[attr-defined]
        else:
            self.laser.state = "ready"  # type: ignore[attr-defined]

        self._post_boss_timer += dt  # type: ignore[attr-defined]
        self._hint_blink      += dt  # type: ignore[attr-defined]

        if self._post_boss_next_id is not None:  # type: ignore[attr-defined]
            # 通常ボス撃破後: アイテムマグネット + 取得 + 遷移判定
            self._update_post_boss_items(dt_eff)
            for item in pygame.sprite.spritecollide(self.player, self.items, True):  # type: ignore[attr-defined]
                if isinstance(item, _WeaponItem):
                    # 即選択せず在庫に加算（V キーで選択）。初回は強めの導線。
                    self._pickup_weapon_item()  # type: ignore[attr-defined]
                else:
                    item.apply(self.player)  # type: ignore[attr-defined]
                    if getattr(item, "popup_text", None):
                        self._spawn_popup(  # type: ignore[attr-defined]
                            item.popup_text,
                            self.player.rect.centerx,  # type: ignore[attr-defined]
                            self.player.rect.top - 10,  # type: ignore[attr-defined]
                        )
            if (self.player.sx >= SCREEN_WIDTH - POST_BOSS_EDGE_MARGIN  # type: ignore[attr-defined]
                    or self._post_boss_timer >= POST_BOSS_AUTO_TIMEOUT):  # type: ignore[attr-defined]
                self._go_next_after_boss()
        else:
            # ラスボス撃破後: タイムアウトで自動クリア
            if self._post_boss_timer >= POST_BOSS_FINAL_TIMEOUT:  # type: ignore[attr-defined]
                self._go_next_after_boss()

    def _update_post_boss_items(self, dt: float) -> None:
        """ボス撃破後: アイテムをプレイヤーに向けて引き寄せる"""
        for item in list(self.items):  # type: ignore[attr-defined]
            # _age 更新・グロウアニメ描画（_magnetizing=True のためドリフトなし）
            item.update(dt, self.camera)  # type: ignore[attr-defined]
            dx = self.player.rect.centerx - item.rect.centerx  # type: ignore[attr-defined]
            dy = self.player.rect.centery - item.rect.centery  # type: ignore[attr-defined]
            d  = math.hypot(dx, dy) or 1
            item.world_x += (dx / d) * MAGNET_SPEED * dt
            item.world_y += (dy / d) * MAGNET_SPEED * dt
            sx = self.camera.to_screen_x(item.world_x)  # type: ignore[attr-defined]
            item.rect.center = (int(sx), int(item.world_y))

    def _draw_post_boss_hint(self, screen: pygame.Surface) -> None:
        """ボス撃破後: 右端移動ガイダンスを点滅表示する（ラスボス後は非表示）"""
        if self._post_boss_next_id is None:  # type: ignore[attr-defined]
            return

        font = self.game.resources.pixelfont(26)  # type: ignore[attr-defined]
        if int(self._hint_blink * 2) % 2 == 0:  # type: ignore[attr-defined]
            hint = font.render("→  右端へ移動で次のステージへ  →", True, (100, 255, 150))
            screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 30))

        remaining = max(0, int(POST_BOSS_AUTO_TIMEOUT - self._post_boss_timer))  # type: ignore[attr-defined]
        count = self.game.resources.pixelfont(20).render(  # type: ignore[attr-defined]
            f"自動遷移まで: {remaining}秒", True, (150, 150, 150)
        )
        screen.blit(count, (SCREEN_WIDTH - count.get_width() - 10, SCREEN_HEIGHT - 30))

    def _on_boss_killed(self) -> None:
        """ボス撃破時の演出・後続フェーズ設定を行う。"""
        self._boss_dialogue_timer = 0.0  # type: ignore[attr-defined]
        self._boss_dialogue_text = ""  # type: ignore[attr-defined]
        self._boss_dialogue_speaker = ""  # type: ignore[attr-defined]
        self._boss_dialogue_queue = []  # type: ignore[attr-defined]

        # デバッグステージではボスをリセットするだけ（GameClearへ進まない）
        if getattr(self, "_is_debug_stage", False):  # type: ignore[attr-defined]
            self._boss = None  # type: ignore[attr-defined]
            self._boss_intro_state = ""  # type: ignore[attr-defined]
            self._active_boss_stage_id = None  # type: ignore[attr-defined]
            self._pending_boss_stage_id = None  # type: ignore[attr-defined]
            self._boss_terrain_spawned = False  # type: ignore[attr-defined]
            self.terrain.empty()  # type: ignore[attr-defined]
            self.enemy_bullets.empty()  # type: ignore[attr-defined]
            self.laser.state = "ready"  # type: ignore[attr-defined]
            return

        bx, by = self._boss.sx, self._boss.sy  # type: ignore[attr-defined]
        sid = self._stage_id  # type: ignore[attr-defined]
        self.game.playlog.log_boss_killed(  # type: ignore[attr-defined]
            self._stage_id,          # type: ignore[attr-defined]
            self._stage_elapsed,     # type: ignore[attr-defined]
            weapon_snapshot=self.player.weapon.snapshot(),  # type: ignore[attr-defined]
        )

        self.particles.spawn_big_explosion(bx, by)  # type: ignore[attr-defined]
        self.particles.spawn_explosion(bx, by, color=(255, 200, 60), count=60)  # type: ignore[attr-defined]
        self.particles.spawn_explosion(bx, by, color=(255, 255, 200), count=30)  # type: ignore[attr-defined]
        self.particles.spawn_glow(bx, by, color=(255, 230, 160), count=20)  # type: ignore[attr-defined]
        self.camera.shake(20.0)  # type: ignore[attr-defined]
        self._hitstop_timer = 0.16  # type: ignore[attr-defined]
        self.game.sound.play_se("music/se/game_explosion9.mp3", volume=0.8)  # type: ignore[attr-defined]
        self.game.sound.play_se("music/se/でたぁ.mp3", volume=1.0)  # type: ignore[attr-defined]
        self.game.sound.stop_bgm(fadeout_ms=800)  # type: ignore[attr-defined]
        self.enemy_bullets.empty()  # type: ignore[attr-defined]
        self.laser.state = "ready"  # type: ignore[attr-defined]

        next_id   = self._stage_id + 1  # type: ignore[attr-defined]
        next_path = Path("data") / "stages" / f"stage{next_id}.json"
        self._post_boss_next_id = next_id if next_path.exists() else None  # type: ignore[attr-defined]
        is_final = (self._post_boss_next_id is None)

        if not is_final:
            # 通常ボス: スロー + 爆発 + ウェポン2個 + 回復4個
            self._post_boss_slow    = 0.35  # type: ignore[attr-defined]
            self._boss_boom_timers  = [0.4, 0.9, 1.5]  # type: ignore[attr-defined]
            wx = self.camera.to_world_x(bx)  # type: ignore[attr-defined]
            self.items.add(_WeaponItem(  # type: ignore[attr-defined]
                wx + random.uniform(-50, 50), by + random.uniform(-30, 30)
            ))
            for _ in range(4):
                self.items.add(_HealItem(  # type: ignore[attr-defined]
                    wx + random.uniform(-70, 70), by + random.uniform(-40, 40)
                ))
            for item in self.items:  # type: ignore[attr-defined]
                item._magnetizing = True
        else:
            # ラスボス: スロー + 爆発 + 閃光
            self._post_boss_slow    = FINAL_SLOW_FACTOR  # type: ignore[attr-defined]
            self._boss_boom_timers  = [0.5, 1.0, 1.6, 2.4]  # type: ignore[attr-defined]
            self._boss_kill_flash_timer = 1.2  # type: ignore[attr-defined]

        self._boss_boom_x = bx  # type: ignore[attr-defined]
        self._boss_boom_y = by  # type: ignore[attr-defined]
        self._boss = None  # type: ignore[attr-defined]
        self._post_boss = True  # type: ignore[attr-defined]

        # 撃破後セリフ設定（爆発演出が落ち着く 2.5 秒後に表示開始）
        pages = BOSS_DEFEAT.get(sid, [])   # list[Line]
        self._defeat_dialogue_pages  = pages  # type: ignore[attr-defined]
        self._defeat_dialogue_index  = 0  # type: ignore[attr-defined]
        self._defeat_dialogue_active = False  # type: ignore[attr-defined]
        self._defeat_dialogue_delay  = 2.5 if pages else 0.0  # type: ignore[attr-defined]

    def _go_next_after_boss(self) -> None:
        """ボス後フェーズ終了: 武器・HPを引き継いで次シーンへ遷移する。"""
        self.game.shared.carry_hp     = self.player.hp  # type: ignore[attr-defined]
        self.game.shared.carry_weapon = self.player.weapon.snapshot()  # type: ignore[attr-defined]

        if self._post_boss_next_id is not None:  # type: ignore[attr-defined]
            from src.scenes.stageclear import StageClearScene
            self.game.change_scene(  # type: ignore[attr-defined]
                StageClearScene(self.game, self._stage_id, self._post_boss_next_id)  # type: ignore[attr-defined]
            )
        else:
            from src.scenes.epilogue_scene import EpilogueScene
            self.game.change_scene(EpilogueScene(self.game))  # type: ignore[attr-defined]
