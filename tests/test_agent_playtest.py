"""Acceptance checks for frame-stepped play through the ordinary game loop.

Prepared gameplay states are diagnostic fixtures, not claims of a full clear.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import random
import subprocess
import sys
import textwrap

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
import pytest

from src.core.scene import Scene

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def session(tmp_path):
    from tools.agent_playtest import Session

    instance = Session(tmp_path / "session", seed=29, diagnostic=True)
    try:
        yield instance
    finally:
        instance.close()


class InputProbe(Scene):
    """A scene whose update and draw have externally observable side effects."""

    def __init__(self, game):
        super().__init__(game)
        self.events = []
        self.frames = []
        self.draw_count = 0

    def handle_event(self, event):
        if event.type in (pygame.KEYDOWN, pygame.KEYUP):
            self.events.append((event.type, event.key))

    def update(self, dt):
        inp = self.game.input
        self.frames.append((dt, set(inp._pressed), set(inp._just_pressed),
                            set(inp._just_released)))

    def draw(self, screen):
        self.draw_count += 1
        screen.fill((random.randrange(256), self.draw_count % 256, 50))


def install_probe(session):
    probe = InputProbe(session.game)
    session.game.change_scene(probe)
    session.command({"step": 1, "actions": []})
    return probe


def install_gameplay(session):
    from src.scenes.game_scene import GameScene

    session.game.start_new_run()
    scene = GameScene(session.game, stage_id=1)
    session.game.change_scene(scene)
    session.command({"step": 1, "actions": []})
    return scene


def screen_bytes(session):
    return pygame.image.tobytes(session.game.screen, "RGB")


def assert_response_image(session, response):
    path = Path(response["image"])
    assert path.is_file()
    saved = pygame.image.load(str(path))
    assert saved.get_size() == session.game.screen.get_size()
    assert pygame.image.tobytes(saved, "RGB") == screen_bytes(session)


def test_normal_startup_returns_the_same_frame_and_screen(session):
    initial = session.command({"observe": True})
    assert initial["type"] == "observation"
    assert initial["frame"] == 1
    assert initial["elapsed"] == pytest.approx(1 / 60)
    assert initial["scene"] == "DisclaimerScene"
    assert initial["held_actions"] == []
    assert_response_image(session, initial)

    session.command({"tap": "ui_accept"})
    boundary = session.command({"step": 60, "actions": []})
    assert boundary["scene"] == "DisclaimerScene"
    assert boundary["advanced"] < 60
    assert type(session.game._next_scene).__name__ == "TitleScene"
    assert_response_image(session, boundary)
    arrived = session.command({"step": 1, "actions": []})
    assert arrived["scene"] == "TitleScene"
    assert type(session.game._scene).__name__ == "TitleScene"
    assert_response_image(session, arrived)


def test_step_holds_keys_without_retriggering_and_draws_every_frame(session):
    probe = install_probe(session)
    start = session.command({"observe": True})
    response = session.command({"step": 4, "actions": ["fire", "move_right"]})
    held = {session.game.settings.get_key(name) for name in ("fire", "move_right")}
    assert response["frame"] == start["frame"] + 4
    assert response["elapsed"] - start["elapsed"] == pytest.approx(4 / 60)
    assert probe.draw_count == 5
    assert all(frame[1] == held for frame in probe.frames[-4:])
    assert probe.frames[-4][2] == held
    assert all(not frame[2] for frame in probe.frames[-3:])

    session.command({"step": 2, "actions": ["move_right", "fire"]})
    assert len(probe.events) == 2
    session.command({"step": 1, "actions": ["fire"]})
    assert probe.frames[-1][1] == {session.game.settings.get_key("fire")}
    assert probe.frames[-1][3] == {session.game.settings.get_key("move_right")}
    session.command({"step": 1, "actions": []})
    assert not session.game.input._pressed
    assert sum(kind == pygame.KEYDOWN for kind, _ in probe.events) == 2
    assert sum(kind == pygame.KEYUP for kind, _ in probe.events) == 2


def test_observation_and_capture_do_not_redraw_or_consume_rng(session):
    probe = install_probe(session)
    baseline = session.command({"step": 3, "actions": ["fire"]})
    state = random.getstate()
    pixels = screen_bytes(session)
    count = probe.draw_count
    for command in ({"observe": True}, {"capture": "same-frame"}, {"observe": True}):
        response = session.command(command)
        assert response["frame"] == baseline["frame"]
        assert response["elapsed"] == baseline["elapsed"]
        assert response["held_actions"] == ["fire"]
        assert random.getstate() == state
        assert probe.draw_count == count
        assert screen_bytes(session) == pixels
        assert_response_image(session, response)


def test_invalid_commands_are_atomic_and_leave_session_usable(session):
    probe = install_probe(session)
    before = session.command({"step": 1, "actions": ["fire"]})
    rng = random.getstate()
    pixels = screen_bytes(session)
    count = probe.draw_count
    invalid = [
        {}, *({"step": value, "actions": []} for value in (0, -1, True, 1.5, 601)),
        {"step": "1", "actions": []}, {"step": 1, "actions": "fire"},
        {"step": 1, "actions": ["fire", "nonexistent-action"]},
        {"tap": "nonexistent-action"}, {"capture": "../../outside"},
        {"observe": True, "step": 1},
    ]
    for command in invalid:
        with pytest.raises(ValueError):
            session.command(command)
        after = session.command({"observe": True})
        assert after["frame"] == before["frame"]
        assert after["elapsed"] == before["elapsed"]
        assert after["held_actions"] == ["fire"]
        assert probe.draw_count == count
        assert random.getstate() == rng
        assert screen_bytes(session) == pixels
    session.command({"step": 1, "actions": []})
    assert not session.game.input._pressed


def test_actions_resolve_current_bindings_and_shared_keys_release_once(session):
    probe = install_probe(session)
    assert session.game.settings.set_key_binding("fire", pygame.K_SPACE)
    assert session.game.settings.set_key_binding("move_down", pygame.K_s)
    session.command({"step": 1, "actions": ["fire", "laser"]})
    assert probe.events == [(pygame.KEYDOWN, pygame.K_SPACE)]
    session.command({"step": 1, "actions": ["laser"]})
    assert session.game.input.is_pressed(pygame.K_SPACE)
    assert len(probe.events) == 1
    session.command({"step": 1, "actions": ["move_down", "menu_down"]})
    assert probe.frames[-1][1] == {pygame.K_s, pygame.K_DOWN}
    assert probe.events.count((pygame.KEYUP, pygame.K_SPACE)) == 1


def test_tap_delivers_press_and_release_in_distinct_frames(session):
    probe = install_probe(session)
    accept = session.game.settings.get_key("ui_accept")
    response = session.command({"tap": "ui_accept"})
    assert probe.events == [(pygame.KEYDOWN, accept), (pygame.KEYUP, accept)]
    assert any(accept in row[2] and accept in row[1] for row in probe.frames)
    assert not session.game.input._pressed
    assert response["held_actions"] == []


def test_pause_settings_round_trip_preserves_the_actual_game_scene(session):
    scene = install_gameplay(session)
    scene.player.hp = 73
    scene._combo_count, scene._combo_timer = 8, 0.1
    scene._heat.heat = 60
    before = (scene.camera.x, scene._stage_elapsed, scene.player.hp)
    session.command({"step": 3, "actions": ["pause"]})
    assert scene._paused
    assert (scene.camera.x, scene._stage_elapsed, scene.player.hp) == before
    assert (scene._combo_count, scene._combo_timer, scene._heat.heat) == (8, 0.1, 60)
    session.command({"step": 2, "actions": ["pause"]})
    assert scene._paused
    session.command({"step": 1, "actions": []})
    session.command({"tap": "menu_down"})
    session.command({"tap": "ui_accept"})
    assert type(session.game._scene).__name__ == "SettingsScene"
    session.command({"tap": "ui_back"})
    assert session.game._scene is scene
    assert scene._paused
    assert (scene.camera.x, scene._stage_elapsed, scene.player.hp) == before
    session.command({"tap": "pause"})
    assert not scene._paused
    session.command({"step": 1, "actions": []})
    assert scene._stage_elapsed > before[1]


def test_laser_hold_then_release_uses_real_player_input(session):
    scene = install_gameplay(session)
    scene.player._entering = False
    scene.player.weapon.laser_level = 1
    session.command({"step": 15, "actions": ["laser"]})
    assert scene.player.laser_fire_held
    assert scene.laser.state == "firing"
    assert scene._heat.heat > 0
    session.command({"step": 1, "actions": []})
    assert not scene.player.laser_fire_held
    assert scene.laser.state == "ending"
    assert not scene.laser.is_active
    session.command({"step": 12, "actions": []})
    assert scene.laser.state == "ready"
    session.command({"step": 1, "actions": ["laser"]})
    assert scene.laser.state == "starting"


def test_final_gate_requires_release_and_fresh_fire_and_observe_preserves_request(session):
    scene = install_gameplay(session)
    from src.entities.enemies.boss import Boss
    scene._boss = Boss(session.game, stage_id=4)
    scene._boss._transform_form2()
    scene._boss._transform_form3()
    scene._boss.begin_act2(240)
    scene._boss.rect.center = (650, 250)
    session.command({"step": 1, "actions": ["fire"]})
    scene._final._begin_input_gate("final_ready")
    session.command({"step": 4, "actions": ["fire"]})
    assert scene._final.input_gate_active
    assert not scene._final._gate_released
    session.command({"step": 1, "actions": []})
    assert scene._final._gate_released
    session.command({"tap": "ui_accept"})
    assert scene._final.input_gate_active
    session.command({"step": 1, "actions": ["fire"]})
    assert scene._final.final_strike_active
    assert scene._final._final_shot_requested
    session.command({"observe": True})
    session.command({"capture": "final-request"})
    assert scene._final._final_shot_requested
    session.command({"step": 1, "actions": []})
    assert not scene._final._final_shot_requested
    assert any(getattr(bullet, "final_strike", False) for bullet in scene.player_bullets)


def test_continue_through_menu_consumes_one_life_and_restores_chapter_loadout(session):
    from src.scenes.gameover import GameOverScene

    scene = install_gameplay(session)
    session.game.shared.score = 1234
    session.game.shared.kill_count = 12
    session.game.shared.stage_start_weapon["main_level"] = 2
    scene.player.weapon.main_level = 4
    scene.player.hp = 0
    session.game.change_scene(GameOverScene(session.game))
    session.command({"step": 1, "actions": []})
    session.command({"tap": "ui_accept"})
    resumed = session.game._scene
    assert type(resumed).__name__ == "GameScene"
    assert resumed is not scene and resumed._stage_id == 1
    assert session.game.shared.lives == 2
    assert session.game.shared.score == 1234
    assert session.game.shared.kill_count == 12
    assert resumed.player.hp == resumed.player.max_hp
    assert resumed.player.weapon.main_level == 2


def test_quit_releases_input_and_close_is_idempotent(session, monkeypatch):
    install_probe(session)
    before = session.command({"step": 1, "actions": ["fire"]})
    saves = []
    save = session.game.settings.save

    def tracked_save():
        saves.append(True)
        save()

    monkeypatch.setattr(session.game.settings, "save", tracked_save)
    session.command({"quit": True})
    session.close()
    assert not session.game.input._pressed
    assert session.game._closed
    assert session.game.elapsed_time == before["elapsed"]
    assert saves == [True]


_REPLAY_SCRIPT = textwrap.dedent("""
    import hashlib, json, random, sys
    import pygame
    from tools.agent_playtest import Session
    from src.scenes.game_scene import GameScene

    session = Session(sys.argv[1], seed=int(sys.argv[2]), diagnostic=True)
    try:
        session.game.start_new_run()
        scene = GameScene(session.game, stage_id=1)
        session.game.change_scene(scene)
        session.command({'step': 1, 'actions': []})
        for actions, frames in [(['fire', 'move_right'], 12), (['fire'], 8), ([], 3)]:
            response = session.command({'step': frames, 'actions': actions})
        print(json.dumps({
            'frame': response['frame'], 'elapsed': response['elapsed'],
            'player': [scene.player.sx, scene.player.sy, scene.player.hp],
            'stage': [scene._stage_elapsed, scene.camera.x],
            'bullets': [(b.rect.x, b.rect.y) for b in scene.player_bullets],
            'rng': hashlib.sha256(repr(random.getstate()).encode()).hexdigest(),
            'pixels': hashlib.sha256(pygame.image.tobytes(session.game.screen, 'RGB')).hexdigest(),
        }))
    finally:
        session.close()
""")


def test_same_seed_reproduces_state_and_frame_across_fresh_processes(tmp_path):
    results = []
    for index, (seed, hash_seed) in enumerate(((41, "71"), (41, "99"), (42, "71"))):
        env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                   PYGAME_HIDE_SUPPORT_PROMPT="1", PYTHONHASHSEED=hash_seed,
                   PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        completed = subprocess.run(
            [sys.executable, "-c", _REPLAY_SCRIPT, str(tmp_path / f"run-{index}"), str(seed)],
            cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, timeout=90,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        results.append(json.loads(completed.stdout.strip().splitlines()[-1]))
    assert results[0] == results[1]
    assert results[0]["rng"] != results[2]["rng"]



def test_nonempty_evidence_directory_is_rejected_without_overwriting(tmp_path):
    from tools.agent_playtest import Session

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    sentinel = evidence / "keep.txt"
    sentinel.write_text("existing evidence", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        Session(evidence)
    assert sentinel.read_text(encoding="utf-8") == "existing evidence"
    assert list(evidence.iterdir()) == [sentinel]


def test_jsonl_errors_recover_and_recorded_commands_replay_in_a_new_process(tmp_path):
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
               PYGAME_HIDE_SUPPORT_PROMPT="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    recording = tmp_path / "recording"
    commands = "\n".join([
        "not json", json.dumps({"step": 4, "actions": []}),
        json.dumps({"capture": "proof"}), json.dumps({"quit": True}), "",
    ])
    completed = subprocess.run(
        [sys.executable, "tools/agent_playtest.py", "--output", str(recording), "--seed", "73"],
        input=commands, cwd=ROOT, env=env, text=True, encoding="utf-8",
        capture_output=True, timeout=90,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    # Every stdout line is protocol JSON, including the recoverable error.
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    assert [row["type"] for row in responses] == [
        "ready", "error", "observation", "observation", "closed",
    ]
    assert responses[0]["frame"] == responses[1]["frame"] == 1
    assert [row["frame"] for row in responses[2:]] == [5, 5, 5]
    assert Path(responses[3]["image"]).is_file()
    assert (recording / "user-data" / "settings.json").is_file()
    log = [json.loads(line) for line in (recording / "actions.jsonl").read_text().splitlines()]
    assert [row["command"] for row in log] == [{"step": 4, "actions": []}]

    replay = subprocess.run(
        [sys.executable, "tools/agent_playtest.py", "--output", str(tmp_path / "replay"),
         "--replay", str(recording)],
        cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, timeout=90,
    )
    assert replay.returncode == 0, replay.stdout + replay.stderr
    verified = json.loads(replay.stdout)
    assert verified["type"] == "replay_verified"
    assert verified["commands"] == 1 and verified["frame"] == 5


def test_tutorial_dialogue_and_choice_are_observable_input_boundaries(session):
    from src.scenes.tutorial_scene import TutorialScene
    from src.story.script import TUTORIAL

    scene = TutorialScene(session.game, with_offer=True)
    session.game.change_scene(scene)
    first = session.command({"step": 1, "actions": []})
    assert first["mode"] == "dialogue"
    assert first["dialogue"]["lines"] == list(TUTORIAL["offer"][0].lines)
    second = session.command({"step": 60, "actions": ["ui_accept"]})
    assert second["advanced"] == 1
    assert scene._dialogue_idx == 1
    assert second["dialogue"]["lines"] == list(TUTORIAL["offer"][1].lines)
    session.command({"step": 1, "actions": []})
    choice = session.command({"tap": "ui_accept"})
    assert scene._choosing
    assert choice["mode"] == "choice"
    assert choice["choice"] == scene._choice == 0
    moved = session.command({"tap": "menu_right"})
    assert moved["choice"] == scene._choice == 1


def test_blackhole_is_observed_as_dialogue_without_revealing_untyped_text(session):
    from src.scenes.blackhole_scene import BlackholeScene
    from src.story.lines import page

    scene = BlackholeScene(session.game, [page("S", "A long current line"),
                                         page("S", "Future line")], lambda: None)
    session.game.change_scene(scene)
    response = session.command({"step": 1, "actions": []})
    assert response["scene"] == "BlackholeScene"
    assert response["mode"] == "dialogue"
    assert response["dialogue"]["lines"] == ["A long current line"[:int(scene._chars)]]
    assert "Future line" not in json.dumps(response)
    revealed = session.command({"tap": "ui_accept"})
    assert revealed["dialogue"]["lines"] == ["A long current line"]



def test_visible_replay_close_reports_last_completed_frame(session, monkeypatch):
    probe = install_probe(session)
    baseline = session.frame
    rendered = []
    original_draw = probe.draw

    def remember(screen):
        original_draw(screen)
        rendered.append(screen.copy())

    monkeypatch.setattr(probe, "draw", remember)
    event_batches = iter([[], [], [pygame.event.Event(pygame.QUIT)]])
    monkeypatch.setattr(pygame.event, "get", lambda: next(event_batches))
    session.visible = True  # SDL remains dummy: no desktop window is operated.
    response = session.command({"step": 5, "actions": ["fire"]})
    assert response["type"] == "closed"
    assert response["frame"] == session.frame == baseline + 2
    assert response["advanced"] == 2
    assert response["held_actions"] == []
    saved = pygame.image.load(response["image"])
    assert pygame.image.tobytes(saved, "RGB") == pygame.image.tobytes(rendered[-1], "RGB")


@pytest.mark.parametrize("already_held, completed_frames", [
    (False, 0), (True, 0), (True, 1),
])
def test_visible_replay_close_during_tap_stops_remaining_steps(
    session, monkeypatch, already_held, completed_frames,
):
    probe = install_probe(session)
    if already_held:
        session.command({"step": 1, "actions": ["ui_accept"]})
    baseline_frame, baseline_draws = session.frame, probe.draw_count
    rendered = [session.game.screen.copy()]
    original_draw = probe.draw

    def remember(screen):
        original_draw(screen)
        rendered.append(screen.copy())

    monkeypatch.setattr(probe, "draw", remember)
    original_get = pygame.event.get
    calls = 0

    def close_between_tap_steps():
        nonlocal calls
        if calls == completed_frames:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        calls += 1
        return original_get()

    monkeypatch.setattr(pygame.event, "get", close_between_tap_steps)
    session.visible = True  # The fixture still uses SDL dummy, never a GUI.
    response = session.command({"tap": "ui_accept"})
    assert response["type"] == "closed"
    assert response["frame"] == baseline_frame + completed_frames
    assert response["advanced"] == completed_frames
    assert probe.draw_count == baseline_draws + completed_frames
    assert response["held_actions"] == []
    assert session.held_actions == session._held_keys == session.game.input._pressed == set()
    assert calls == completed_frames + 1
    saved = pygame.image.load(response["image"])
    assert pygame.image.tobytes(saved, "RGB") == pygame.image.tobytes(rendered[-1], "RGB")


def test_visible_replay_cancelled_during_recorded_tap(session, tmp_path, monkeypatch):
    from tools.agent_playtest import replay

    session.command({"tap": "ui_accept"})
    source = session.output_dir
    session.close()
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    original_get = pygame.event.get

    def request_close():
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        return original_get()

    monkeypatch.setattr(pygame.event, "get", request_close)
    result = replay(source, tmp_path / "cancelled-replay", visible=True)
    assert result == {"type": "replay_cancelled", "commands": 1, "frame": 1}


def test_session_close_restores_callers_environment(tmp_path, monkeypatch):
    from tools.agent_playtest import Session

    previous = str(tmp_path / "caller-profile")
    monkeypatch.setenv("FLU_USER_DATA_DIR", previous)
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    instance = Session(tmp_path / "isolated-session")
    assert os.environ["FLU_USER_DATA_DIR"] != previous
    instance.close()
    assert os.environ["FLU_USER_DATA_DIR"] == previous
    assert not Path(previous).exists()


def test_automatic_png_saving_does_not_change_frames_rng_or_pixels(tmp_path):
    from tools.agent_playtest import Session

    traces = []
    for save_images in (True, False):
        instance = Session(tmp_path / str(save_images), seed=71,
                           save_step_images=save_images)
        try:
            probe = install_probe(instance)
            trace = []
            for actions in (["fire"], ["move_up"], []):
                result = instance.command({"step": 12, "actions": actions})
                assert ("image" in result) == save_images
                trace.append((result["frame"], result["state_digest"], result["image_digest"]))
            assert probe.draw_count == 37  # Rendering still happens on every frame.
            shot = instance.command({"capture": "explicit"})
            assert Path(shot["image"]).is_file()
            if not save_images:
                assert not (instance.output_dir / "latest.png").exists()
            traces.append(trace)
        finally:
            instance.close()
    assert traces[0] == traces[1]
