"""Bounded packaged-runtime checks; this is not a native GUI campaign playtest."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

from src.core.runtime_assets import RUNTIME_ROOT, runtime_data_files


def _run_checks(user_data_base: Path) -> dict:
    # Import game modules only after the smoke entry point has isolated storage
    # and selected SDL's dummy drivers. Normal startup does neither of these.
    import pygame
    from src.core.game import Game
    from src.core.registries import next_stage_id, stage_ids
    from src.core.user_data import user_data_dir
    from src.managers.highscore import HighScoreManager
    from src.managers.playlog import PlayLogger
    from src.managers.settings import SettingsManager
    from src.scenes.game_scene import GameScene

    files = runtime_data_files()
    storage = user_data_dir().resolve()
    if not storage.is_relative_to(user_data_base.resolve()):
        raise RuntimeError(f"user data did not resolve to isolated OS storage: {storage}")
    if storage.is_relative_to(RUNTIME_ROOT):
        raise RuntimeError("user data resolved inside packaged resources")
    ids = stage_ids()
    if not ids:
        raise RuntimeError("no authored campaign stages in the bundle")
    try:
        game = Game()
        stages = []
        for index, stage_id in enumerate(ids):
            scene = GameScene(game, stage_id=stage_id)
            game._scene = scene
            scene.on_enter()
            scene.update(1.0 / 60.0)
            scene.draw(game.screen)
            if not scene.terrain:
                raise RuntimeError(f"stage {stage_id}: initial terrain was not created")
            # Also load boss-room terrain: it can reference catalogs/masks that
            # are not used by the stage's initial layout.
            scene.spawner.spawn_terrain_events(scene.stage.boss_terrain, scene.camera)
            following = next_stage_id(stage_id)
            expected = ids[index + 1] if index + 1 < len(ids) else None
            if following != expected:
                raise RuntimeError(f"stage {stage_id}: next stage {following}, expected {expected}")
            stages.append({"stage": stage_id, "next_stage": following,
                           "initialized": True, "drawn": True})
            scene.on_exit()

        game.settings.set("bgm_volume", 0.37)
        game.settings.save()
        if SettingsManager().get("bgm_volume") != 0.37:
            raise RuntimeError("settings did not survive save/reload")
        game.highscore.add("PACKAGED_SMOKE", 12345, ids[-1])
        if not any(score["name"] == "PACKAGED_SMOKE" and score["score"] == 12345
                   for score in HighScoreManager().get_scores()):
            raise RuntimeError("high score did not survive save/reload")
        game.playlog.begin_run()
        game.playlog.end_run(cleared=False, score=12345, kill_count=0)
        if not any(session.get("score") == 12345 for session in PlayLogger.load_all_sessions()):
            raise RuntimeError("play log did not survive save/reload")
        for path in (storage / "settings.json", storage / "highscore.json", game.playlog._path):
            if not path.is_relative_to(storage) or not path.is_file():
                raise RuntimeError(f"save file is missing or outside user storage: {path}")
        return {"stages": stages, "runtime_data_files": len(files),
                "user_data_dir": str(storage), "settings_saved": True,
                "highscore_saved": True, "playlog_saved": True}
    finally:
        pygame.quit()


def run_smoke_test(output: Path) -> int:
    """Write a success/failure report and exit; never use real player save data."""
    output = output.resolve()
    report = {"kind": "packaged_runtime_smoke", "status": "failed",
              "frozen": bool(getattr(sys, "frozen", False)),
              "cwd": str(Path.cwd()), "resource_root": str(RUNTIME_ROOT),
              "scope": "headless initialization, next-stage lookup, and isolated save/reload; not campaign completion"}
    try:
        if not report["frozen"]:
            raise RuntimeError("--smoke-test requires the built executable")
        if Path.cwd().resolve().is_relative_to(RUNTIME_ROOT):
            raise RuntimeError("run the packaged smoke test from outside the resource directory")
        if sys.platform not in {"win32", "linux"}:
            raise RuntimeError("isolated packaged smoke storage supports Windows and Linux")
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
        # Each explicit smoke invocation receives a fresh OS data directory.
        # The normal frozen user_data_dir resolver must select it itself.
        with tempfile.TemporaryDirectory(prefix="flu-smoke-userdata-") as directory:
            os.environ["APPDATA"] = directory
            os.environ["XDG_DATA_HOME"] = directory
            report.update(_run_checks(Path(directory)))
        report["status"] = "passed"
    except Exception as exc:
        report.update(error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        if sys.stderr is not None:
            print(f"could not write smoke report: {exc}", file=sys.stderr)
        return 1
    return 0 if report["status"] == "passed" else 1
