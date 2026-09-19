"""Real-font layout and configurable input checks for narrative screens."""
from types import SimpleNamespace
from unittest.mock import Mock

import pygame
import pytest

from src.managers.input import InputManager
from src.managers.resource import ResourceManager
from src.managers.settings import SettingsManager
from src.scenes import dialogue_panel as panels
from src.scenes.credits_roll import CreditsRollScene
from src.scenes.blackhole_scene import BlackholeScene
from src.scenes.cutscene_scene import CutsceneScene
from src.scenes.tutorial_scene import TutorialScene
from src.story import script
from src.story.lines import Line, page
from src.story.speakers import NARRATION


@pytest.fixture
def game(monkeypatch, tmp_path):
    import src.managers.settings as settings_module
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setattr(settings_module, "_SETTINGS_PATH", tmp_path / "settings.json")
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    settings = SettingsManager()
    yield SimpleNamespace(screen=screen, resources=ResourceManager(), settings=settings,
                          input=InputManager(settings), sound=Mock(), change_scene=Mock())
    pygame.quit()


def test_authored_story_text_stays_inside_its_panel(game):
    # Includes the four-row prologue that previously drew below the panel.
    background = (231, 21, 187)
    for beat in script.STORY_BEATS:
        if beat.scene == "credits":
            continue
        for index, pg in enumerate(beat.pages):
            game.screen.fill(background)
            panels.draw_story_panel(game.screen, game.resources, pg.speaker, pg.lines,
                                    show_portrait=False, hint_text="ENTER: 次へ　X: 会話を省略")
            below = game.screen.subsurface((0, 566, 800, 34))
            unchanged = pygame.mask.from_threshold(below, background, (1, 1, 1, 255))
            assert unchanged.count() == 800 * 34, (beat.key, index)
            wrapped = panels._wrap_lines(game.resources.pixelfont(26), pg.lines, 668)
            assert "".join(wrapped) == "".join(pg.lines)
            assert all(game.resources.pixelfont(26).size(line)[0] <= 668 for line in wrapped)


def test_long_key_hints_reserve_space_below_name_and_body(game):
    rect = pygame.Rect(40, 382, 720, 184)
    hint = "RIGHTBRACKET: 全文表示（長押し可）　PRINTSCREEN: 会話を省略"
    lines, height = panels._footer_layout(game.resources, rect, hint, 66, 18)
    font = game.resources.pixelfont(18)
    assert "".join(lines) == hint
    assert all(font.size(line)[0] <= 760 - 46 - 66 for line in lines)
    assert height >= len(lines) * font.get_height() + 16
    body = game.resources.pixelfont(26)
    text = panels._wrap_lines(body, script.story_beat("prologue").pages[12].lines, 668)
    name_height = panels._name_height(game.resources, "カロナール先輩")
    expanded = panels._panel_for_text(rect, body, text, height, name_height)
    assert expanded.top > 100
    assert expanded.top + 18 + name_height + len(text) * (body.get_height() + 2) - 2 <= expanded.bottom - height


def test_authored_combat_dialogue_stays_above_boss_gauges(game):
    def dialogue_lines(value):
        if isinstance(value, Line):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from dialogue_lines(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                yield from dialogue_lines(child)

    background = (231, 21, 187)
    for name, value in vars(script).items():
        if not name.isupper():
            continue
        for line in dialogue_lines(value):
            game.screen.fill(background)
            panels.draw_combat_panel(game.screen, game.resources, line.speaker, line.lines,
                                     hint_text="ENTER / Z: 次へ")
            below = game.screen.subsurface((0, 544, 800, 56))
            unchanged = pygame.mask.from_threshold(below, background, (1, 1, 1, 255))
            assert unchanged.count() == 800 * 56, (name, line.lines)


def test_cutscene_hint_matches_typewriter_state_and_custom_keys(game, monkeypatch):
    game.settings.set_key_binding("ui_accept", pygame.K_q)
    game.settings.set_key_binding("ui_back", pygame.K_w)
    scene = CutsceneScene(game, [page(NARRATION, "一文字ずつ表示する会話")] * 2, lambda: None)
    scene.on_enter()
    draw = Mock()
    monkeypatch.setattr("src.scenes.cutscene_scene.draw_story_panel", draw)
    scene.draw(game.screen)
    hint = draw.call_args.kwargs["hint_text"]
    assert "Q: 全文表示" in hint and "W: 会話を省略" in hint
    scene._chars = scene._total_chars()
    scene.draw(game.screen)
    first = draw.call_args.kwargs.copy()
    assert "Q: 次へ" in first["hint_text"]
    assert not {"page_index", "total_pages", "hint_last", "hint_next"} & first.keys()
    scene._page = 1
    scene.draw(game.screen)
    assert draw.call_args.kwargs == first


@pytest.mark.parametrize("kind", ["intro", "cutin", "defeat", "final", "tutorial", "blackhole"])
def test_combat_dialogue_renderer_never_receives_sequence_progress(game, monkeypatch, kind):
    from src.scenes.game.overlay_mixin import GameSceneOverlayMixin
    from src.scenes.game.final_battle import FinalBattleDirector

    game.settings.set_key_binding("ui_accept", pygame.K_q)
    pages = [page(NARRATION, "同じ会話で最初と最後の表示を比較する。")] * 2
    draw = Mock(return_value=pygame.Rect(100, 400, 600, 60))
    if kind in {"intro", "cutin", "defeat"}:
        scene = SimpleNamespace(game=game)
        fields = {
            "intro": ("_boss_intro_pages", "_boss_intro_page_idx", "_draw_boss_intro_dialogue"),
            "cutin": ("_cutin_pages", "_cutin_idx", "_draw_combat_cutin"),
            "defeat": ("_defeat_dialogue_pages", "_defeat_dialogue_index", "_draw_defeat_dialogue"),
        }
        pages_field, index_field, method = fields[kind]
        setattr(scene, pages_field, pages)
        render = lambda: getattr(GameSceneOverlayMixin, method)(scene, game.screen)
        monkeypatch.setattr("src.scenes.game.overlay_mixin.draw_combat_panel", draw)
    elif kind == "final":
        scene = FinalBattleDirector(SimpleNamespace(game=game))
        scene._final_dialogue_pages = pages
        index_field = "_final_dialogue_idx"
        render = lambda: scene._draw_final_dialogue(game.screen)
        monkeypatch.setattr("src.scenes.game.final_battle.draw_combat_panel", draw)
    elif kind == "tutorial":
        scene = TutorialScene(game)
        scene._dialogue = pages
        index_field = "_dialogue_idx"
        render = lambda: scene._draw_panel(game.screen, pages[getattr(scene, index_field)], True)
        monkeypatch.setattr("src.scenes.tutorial_scene.draw_combat_panel", draw)
    else:
        scene = BlackholeScene(game, pages, lambda: None)
        scene._chars = sum(map(len, pages[0].lines))
        index_field = "_page"
        render = lambda: scene._draw_dialogue(game.screen)
        monkeypatch.setattr(panels, "draw_story_panel", draw)
    setattr(scene, index_field, 0)
    render()
    first = draw.call_args.kwargs.copy()
    assert not {"page_index", "total_pages", "hint_last", "hint_next"} & first.keys()
    assert "Q" in first["hint_text"] and "次へ" in first["hint_text"]
    setattr(scene, index_field, 1)
    render()
    assert draw.call_args.kwargs == first


def test_practice_instruction_uses_movement_bindings_and_progress(game):
    for action, key in (("move_left", pygame.K_a), ("move_right", pygame.K_d),
                        ("move_up", pygame.K_w), ("move_down", pygame.K_s)):
        game.settings.set_key_binding(action, key)
    scene = TutorialScene(game)
    scene.on_enter()
    scene._moved_h = True
    title, instruction, progress = scene._practice_labels()
    assert "1 / 4" in title
    assert "A / D" in instruction and "W / S" in instruction
    assert "左右の移動：完了" in progress and "上下の移動：未完了" in progress
    scene._start_shoot()
    scene._shots = 3
    assert "3 / 6" in scene._practice_labels()[2]


def test_practice_back_conflict_does_not_exit_while_firing(game):
    game.settings.set_key_binding("fire", pygame.K_x)
    done = Mock()
    scene = TutorialScene(game, done)
    scene.on_enter()
    scene.player._entering = False
    scene._start_shoot()
    game.input.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x))
    scene.update(0.1)
    done.assert_not_called()
    assert scene._shots == 1
    assert "ESC:" in scene._exit_hint()
    game.input.pre_update()
    game.input.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    scene.update(0.1)
    scene.update(0.1)
    done.assert_called_once()


def test_practice_does_not_assign_an_exit_over_another_gameplay_key(game):
    game.settings.set_key_binding("fire", pygame.K_x)
    game.settings.set_key_binding("move_up", pygame.K_ESCAPE)
    scene = TutorialScene(game)
    scene.on_enter()
    assert scene._exit_key() is None
    assert scene._exit_hint() == ""


def test_credits_wrap_preserves_text_and_readable_font(game):
    text = "長い名前やクレジットも読みやすい文字の大きさで表示します。" * 3
    scene = CreditsRollScene(game, [page(NARRATION, text)], lambda: None)
    scene.on_enter()
    rows = [(value, kind) for value, kind, _ in scene._entries if value]
    assert len(rows) > 1
    assert "".join(value for value, _ in rows) == text
    assert all(kind == "body" for _, kind in rows)
    assert all(scene._font_for(kind, value).size(value)[0] <= 656 for value, kind in rows)


def test_credits_background_rays_respect_opacity(game):
    scene = CreditsRollScene(game, [], lambda: None)
    scene._timer = 0.0
    game.screen.fill("black")
    scene._draw_slow_rays(game.screen)
    pixels = pygame.image.tobytes(game.screen, "RGB")
    assert 0 < max(pixels) < 30


def test_blackhole_farewell_keeps_original_words_in_every_render(game, monkeypatch):
    pages = list(script.story_beat("3->4").pages)
    scene = BlackholeScene(game, pages, lambda: None)
    draw = Mock()
    monkeypatch.setattr(panels, "draw_story_panel", draw)
    for i, pg in enumerate(pages):
        scene._page = i
        scene._chars = sum(map(len, pg.lines))
        for _ in range(3):
            scene._draw_dialogue(game.screen)
            assert draw.call_args.args[3] == pg.lines
            assert "text_transform" not in draw.call_args.kwargs
            assert not draw.call_args.kwargs.get("text_jitter", 0)
            assert draw.call_args.kwargs["show_portrait"] is False


def test_blackhole_dialogue_window_and_text_origin_remain_fixed(game, monkeypatch):
    scene = BlackholeScene(game, list(script.story_beat("3->4").pages), lambda: None)
    windows, origins = [], []
    original_window = panels._draw_window
    original_text = panels._draw_text

    def record_window(screen, rect, *args, **kwargs):
        windows.append(rect.copy())
        return original_window(screen, rect, *args, **kwargs)

    def record_text(screen, resources, rect, *args, **kwargs):
        origins.append((rect.top, kwargs["text_x"], kwargs["name_height"]))
        return original_text(screen, resources, rect, *args, **kwargs)

    monkeypatch.setattr(panels, "_draw_window", record_window)
    monkeypatch.setattr(panels, "_draw_text", record_text)
    for i, pg in enumerate(scene._pages):
        scene._page = i
        for chars in (0, sum(map(len, pg.lines))):
            scene._chars = chars
            scene._draw_dialogue(game.screen)
    assert windows and all(rect == pygame.Rect(40, 342, 720, 224) for rect in windows)
    assert len(set(origins)) == 1
