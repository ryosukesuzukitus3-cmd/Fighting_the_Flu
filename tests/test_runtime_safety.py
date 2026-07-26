from __future__ import annotations

import pygame
import pytest

from src.core.registries import next_stage_id, stage_ids
from src.entities.bullets.enemy_bullet import EnemyBullet
from src.entities.bullets.player_bullet import NormalBullet
from src.scenes.game_scene import GameScene
from tools.headless import build_game_scene


@pytest.fixture(scope="module")
def game():
    built_game, _ = build_game_scene(stage_ids()[0])
    yield built_game
    pygame.quit()


@pytest.fixture
def scene(game) -> GameScene:
    built_scene = GameScene(game, stage_id=stage_ids()[0])
    game._scene = built_scene
    built_scene.on_enter()
    return built_scene


def test_stage_progression_uses_authored_stage_ids_outside_repo_cwd(
    game, monkeypatch, tmp_path
) -> None:
    ids = stage_ids()
    monkeypatch.chdir(tmp_path)

    assert next_stage_id(ids[0]) == ids[1]
    assert next_stage_id(ids[-1]) is None
    with pytest.raises(ValueError, match="unknown stage_id"):
        next_stage_id(999_999)

    played: list[str] = []
    monkeypatch.setattr(
        game.sound,
        "play_se",
        lambda path, **kwargs: played.append(path),
    )
    built_scene = GameScene(game, stage_id=ids[0])
    game._scene = built_scene
    built_scene.on_enter()

    assert f"music/rounds/round{ids[0]}.wav" in played

    played.clear()
    final_scene = GameScene(game, stage_id=ids[-1])
    game._scene = final_scene
    final_scene.on_enter()

    assert "music/rounds/final.wav" in played


def test_frozen_build_uses_platform_user_data_even_when_bundle_is_writable(
    monkeypatch, tmp_path
) -> None:
    from src.core import user_data

    bundle_data = tmp_path / "bundle" / "data"
    platform_data = tmp_path / "platform-data"
    platform_data.mkdir()
    monkeypatch.setattr(user_data, "_cached_dir", None)
    monkeypatch.setattr(user_data, "_DEV_DATA_DIR", bundle_data)
    monkeypatch.setattr(user_data.sys, "frozen", True, raising=False)
    monkeypatch.setattr(user_data, "_platform_user_data_dir", lambda: platform_data)

    assert user_data.user_data_dir() == platform_data
    assert not bundle_data.exists()


def test_playlog_uses_shared_user_data_root(monkeypatch, tmp_path) -> None:
    from src.managers import playlog

    monkeypatch.setattr(playlog, "user_data_dir", lambda: tmp_path)
    logger = playlog.PlayLogger()
    logger.begin_run()
    logger.end_run(cleared=True, score=1234, kill_count=5)

    assert logger._path.parent == tmp_path / "playlogs"
    assert playlog.PlayLogger.load_all_sessions()[0]["score"] == 1234


class _DamageableEnemy(pygame.sprite.Sprite):
    def __init__(self, center: tuple[int, int]) -> None:
        super().__init__()
        self.image = pygame.Surface((20, 20), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=center)
        self.hp = 3

    def blocks_projectile_damage(self, bullet) -> bool:
        return False

    def take_damage(self, amount: int) -> bool:
        self.hp -= amount
        return self.hp <= 0


def test_non_piercing_bullet_damages_only_one_overlapping_enemy(scene) -> None:
    center = (320, 240)
    enemies = [_DamageableEnemy(center), _DamageableEnemy(center)]
    bullet = NormalBullet(*center)
    scene.enemies = pygame.sprite.Group(*enemies)
    scene.player_bullets = pygame.sprite.Group(bullet)
    scene.enemy_bullets = pygame.sprite.Group()
    scene.terrain = pygame.sprite.Group()
    scene.items = pygame.sprite.Group()
    scene._companion = None

    scene._process_collisions()

    assert sorted(enemy.hp for enemy in enemies) == [2, 3]
    assert not bullet.alive()


@pytest.mark.parametrize(
    ("persistent", "expected_alive"),
    [(False, False), (True, True)],
)
def test_enemy_bullet_is_consumed_unless_persistent(
    scene, persistent: bool, expected_alive: bool
) -> None:
    scene.enemies = pygame.sprite.Group()
    scene.player_bullets = pygame.sprite.Group()
    scene.terrain = pygame.sprite.Group()
    scene.items = pygame.sprite.Group()
    scene._companion = None
    scene.player._invincible_timer = 0.0
    bullet = EnemyBullet(*scene.player.hit_rect.center, 0.0, 0.0)
    bullet.persistent = persistent
    scene.enemy_bullets = pygame.sprite.Group(bullet)

    scene._process_collisions()

    assert bullet.alive() is expected_alive
