"""Entity factory helpers derived from registries.

敵・アイテムの実体生成分岐をここに集約し、spawner / debug UI /
random drop が同じ生成表を見るようにする。
"""
from __future__ import annotations

import random
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame
    from src.core.game import Game


def _weapon_item_class():
    from src.entities.items.weapon_item import WeaponItem
    return WeaponItem


def _heal_item_class():
    from src.entities.items.heal import HealItem
    return HealItem


_ITEM_CLASSES: dict[str, Callable] = {
    "WeaponItem": _weapon_item_class,
    "HealItem": _heal_item_class,
}


def item_factory_names() -> set[str]:
    return set(_ITEM_CLASSES)


def random_item_names() -> set[str]:
    from src.core.registries import ITEM_DEFS
    return {d.name for d in ITEM_DEFS if d.drop_weight > 0 and d.name in _ITEM_CLASSES}


def make_item(name: str, wx: float, wy: float):
    class_getter = _ITEM_CLASSES.get(name)
    if class_getter is None:
        return None
    return class_getter()(wx, wy)


def random_item(world_x: float, world_y: float, *, spread: float = 0.0):
    """ランダムアイテムを1つ生成する。重みは ITEM_DEFS.drop_weight がSSOT。"""
    from src.core.registries import ITEM_DEFS

    random_names = random_item_names()
    pool = [(d.name, d.drop_weight) for d in ITEM_DEFS if d.name in random_names]
    names, weights = zip(*pool)
    ox = world_x + random.uniform(-spread, spread)
    oy = world_y + random.uniform(-spread, spread)
    return make_item(random.choices(names, weights=weights, k=1)[0], ox, oy)


def _enemy_virus(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.virus import EnemyVirus
    return EnemyVirus(game, wx, wy, enhanced=ctx["enhanced"])


def _enemy_takeshi(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.takeshi import EnemyTakeshi
    return EnemyTakeshi(game, wx, wy, enhanced=ctx["enhanced"])


def _enemy_broly(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.broly import EnemyBroly
    player = ctx.get("player")
    target_y = getattr(player, "sy", None)
    return EnemyBroly(
        game, wx, wy,
        target_y=target_y,
        enemy_bullets=ctx.get("enemy_bullets"),
        player=player,
        enhanced=ctx["enhanced"],
    )


def _enemy_pachemon(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.pachemon import EnemyPachemon
    return EnemyPachemon(
        game, wx, wy, ctx.get("enemy_bullets"), ctx.get("player"),
        enhanced=ctx["enhanced"],
    )


def _enemy_cough_sprayer(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.cough_sprayer import EnemyCoughSprayer
    return EnemyCoughSprayer(
        game, wx, wy, ctx.get("enemy_bullets"), ctx.get("player"),
        enhanced=ctx["enhanced"],
    )


def _enemy_spore_splitter(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.spore_splitter import EnemySporeSplitter
    return EnemySporeSplitter(
        game, wx, wy, ctx.get("enemy_bullets"), ctx.get("player"),
        enhanced=ctx["enhanced"],
    )


def _enemy_spore_pod(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.spore_splitter import EnemySporePod
    return EnemySporePod(game, wx, wy, enhanced=ctx["enhanced"])


def _enemy_billy(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.billy import EnemyBilly
    return EnemyBilly(game, wx, wy)


def _enemy_turret(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.turret import EnemyTurret
    return EnemyTurret(
        game, wx, wy, ctx.get("enemy_bullets"), ctx.get("player"),
        surface=ctx.get("surface", "bottom"),
        enhanced=ctx["enhanced"],
    )


def _enemy_crawler(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.crawler import EnemyCrawler
    return EnemyCrawler(
        game, wx, wy, ctx.get("enemy_bullets"), ctx.get("player"), ctx.get("terrain"),
        surface=ctx.get("surface", "bottom"),
        enhanced=ctx["enhanced"],
    )


def _enemy_debris_large(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.debris import EnemyDebrisLarge
    return EnemyDebrisLarge(game, wx, wy, enhanced=ctx["enhanced"])


def _enemy_debris_shard(game: "Game", wx: float, wy: float, ctx: dict):
    from src.entities.enemies.debris import EnemyDebrisShard
    return EnemyDebrisShard(game, wx, wy, enhanced=ctx["enhanced"])


_ENEMY_BUILDERS: dict[str, Callable] = {
    "EnemyVirus": _enemy_virus,
    "EnemyTakeshi": _enemy_takeshi,
    "EnemyBroly": _enemy_broly,
    "EnemyPachemon": _enemy_pachemon,
    "EnemyCoughSprayer": _enemy_cough_sprayer,
    "EnemySporeSplitter": _enemy_spore_splitter,
    "EnemySporePod": _enemy_spore_pod,
    "EnemyBilly": _enemy_billy,
    "EnemyTurret": _enemy_turret,
    "EnemyCrawler": _enemy_crawler,
    "EnemyDebrisLarge": _enemy_debris_large,
    "EnemyDebrisShard": _enemy_debris_shard,
}


def enemy_factory_names() -> set[str]:
    return set(_ENEMY_BUILDERS)


def make_enemy(
    name: str,
    game: "Game",
    wx: float,
    wy: float,
    *,
    enemy_bullets: "pygame.sprite.Group | None" = None,
    player=None,
    terrain: "pygame.sprite.Group | None" = None,
    surface: str = "bottom",
    enhanced: bool = False,
):
    builder = _ENEMY_BUILDERS.get(name)
    if builder is None:
        return None
    return builder(game, wx, wy, {
        "enemy_bullets": enemy_bullets,
        "player": player,
        "terrain": terrain,
        "surface": surface,
        "enhanced": enhanced,
    })
