"""Packaging must cover authored terrain and exercise an isolated runtime."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from src.core import runtime_assets


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_contains_every_stage_catalog_and_mask():
    files = set(runtime_assets.runtime_data_files())
    resources = runtime_assets.terrain_resource_paths()
    assert resources
    for resource in resources:
        required = {path for path in resource.rglob("*") if path.is_file()} if resource.is_dir() else {resource}
        assert required <= files
    from src.core.registries import stage_ids
    for stage in stage_ids():
        assert ROOT / "data" / "stages" / f"stage{stage}.json" in files


def test_manifest_excludes_unselected_candidates_but_keeps_aliased_sounds():
    files = set(runtime_assets.runtime_data_files())
    graphics = ROOT / "assets" / "graphic" / "candidates"
    sounds = ROOT / "assets" / "music" / "se" / "candidates"
    assert not any(path.is_relative_to(graphics) for path in files)
    selected = {ROOT / "assets" / path for path in runtime_assets.SE.values()
                if path and path.startswith("music/se/candidates/")}
    assert selected
    assert {path for path in files if path.is_relative_to(sounds)} == selected
    datas = runtime_assets.pyinstaller_datas()
    for source, destination in datas:
        assert Path(destination) / Path(source).name == Path(source).relative_to(ROOT)


@pytest.mark.parametrize("missing", ["catalog", "masks"])
def test_manifest_rejects_missing_authored_terrain(tmp_path, missing):
    stages = tmp_path / "data" / "stages"
    stages.mkdir(parents=True)
    tools = tmp_path / "tools"
    tools.mkdir()
    if missing != "catalog":
        (tools / "terrain.json").write_text("{}", encoding="utf-8")
    if missing != "masks":
        (tools / "masks").mkdir()
    (stages / "stage1.json").write_text(json.dumps({
        "terrain_layout": [{"renderer": "terrain_composer", "composer_rects": "tools/terrain.json",
                            "composer_mask_dir": "tools/masks"}],
    }), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="missing terrain resource"):
        runtime_assets.terrain_resource_paths(tmp_path)


def test_unfrozen_smoke_refuses_to_touch_player_data(tmp_path, monkeypatch):
    from src.core.packaged_smoke import run_smoke_test
    monkeypatch.delattr(sys, "frozen", raising=False)
    report_path = tmp_path / "result.json"
    assert run_smoke_test(report_path) == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert "requires the built executable" in report["error"]


def test_smoke_checks_initialize_all_stages_and_reload_isolated_saves(tmp_path, monkeypatch):
    # Exercise the same checks before building, with frozen storage selection.
    # This does not replace run_packaged_smoke.py against the actual executable.
    if sys.platform not in {"win32", "linux"}:
        pytest.skip("packaged smoke storage targets Windows and Linux")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("APPDATA", str(tmp_path / "userdata"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "userdata"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    from src.core import user_data
    monkeypatch.setattr(user_data, "_cached_dir", None)
    storage = user_data.user_data_dir()
    # Other test modules may already have imported these managers at collection.
    from src.managers import settings, highscore
    monkeypatch.setattr(settings, "_SETTINGS_PATH", storage / "settings.json")
    monkeypatch.setattr(highscore, "_HIGHSCORE_PATH", storage / "highscore.json")
    monkeypatch.chdir(tmp_path)
    from src.core.packaged_smoke import _run_checks
    from src.core.registries import stage_ids
    result = _run_checks(tmp_path / "userdata")
    assert [stage["stage"] for stage in result["stages"]] == stage_ids()
    assert result["stages"][-1]["next_stage"] is None
    assert result["settings_saved"] and result["highscore_saved"] and result["playlog_saved"]
    assert json.loads((storage / "settings.json").read_text(encoding="utf-8"))["bgm_volume"] == 0.37


def test_host_runner_rejects_early_exit_and_discards_stale_success(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tools import run_packaged_smoke as runner
    executable = tmp_path / "stub.exe"
    executable.touch()
    report = tmp_path / "result.json"
    report.write_text('{"status":"passed"}', encoding="utf-8")
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError, match="without a JSON report"):
        runner.run_packaged_smoke(executable, report)
    assert not report.exists()
