"""A diagnostic policy must keep progressing when extra stock has no use."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from tools.agent_campaign import Campaign
from tools.agent_playtest import Session
from src.scenes.game_scene import GameScene


@pytest.mark.parametrize("unused_player_stock", [0, 2])
def test_fully_upgraded_companion_stock_does_not_reopen_empty_upgrade_menu(
    tmp_path, unused_player_stock,
):
    session = Session(tmp_path / "campaign", seed=7, diagnostic=True)
    bot = None
    try:
        session.game.start_new_run()
        scene = GameScene(session.game, stage_id=1)
        session.game.change_scene(scene)
        session.command({"step": 1, "actions": []})
        # Test fixture only: reproduce both trees' caps and unused natural stock.
        weapon = scene.player.weapon
        weapon.main_level = 4
        weapon.speed_level = 5
        weapon.laser_level = 6
        weapon.homing_level = 7
        weapon.weapon_stock = unused_player_stock
        companion = scene._companion
        assert companion is not None
        companion.lv_hp = companion.lv_shot = companion.lv_supply = companion.lv_magnet = 3
        companion.stock = 3
        assert scene._top_available_indices() == scene._bottom_available_indices() == []

        bot = Campaign(session)
        before = scene._stage_elapsed
        for _ in range(3):
            actions = bot.decide()
            assert "weapon_select" not in actions
            bot.advance(actions)
            assert session.game._scene is scene and not scene._upgrading
        assert scene._stage_elapsed >= before + 0.5
        assert weapon.weapon_stock == unused_player_stock
        assert companion.stock == 3
    finally:
        if bot is not None:
            bot._trace.close()
        session.close()


def test_return_to_title_on_last_budgeted_batch_counts_as_complete(tmp_path, monkeypatch):
    from src.scenes.title import TitleScene

    session = Session(tmp_path / "final-return", seed=7, diagnostic=True)
    try:
        bot = Campaign(session, interval=12, max_frames=session.frame + 12)
        # A diagnostic fixture models the credits callback returning to title.
        bot.victory_reached = True
        session.game.change_scene(TitleScene(session.game))
        monkeypatch.setattr(bot, "decide", lambda: [])
        result = bot.run()
        assert result["frame"] == bot.max_frames
        assert result["victory_reached"] and result["completed"]
        assert result["reason"] == "completed campaign and returned to title"
    finally:
        session.close()
