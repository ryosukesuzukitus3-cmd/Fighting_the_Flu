"""Render result/record screens with real fonts and inspect visible text bounds."""
from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from src.managers.resource import ResourceManager
from src.scenes.disclaimer_scene import DisclaimerScene
from src.scenes.gameclear import GameClearScene
from src.scenes.gameover import GameOverScene
from src.scenes.highscore_scene import HighScoreScene
from src.scenes.meta_ui import ACCENT_GOLD
from src.scenes.stageclear import StageClearScene
from src.scenes.stats_scene import PlayLogger, StatsScene
from src.story.script import BOOT_DISCLAIMER, GAME_CLEAR, GAMEOVER_LINES


class _Font:
    def __init__(self, font, rendered):
        self.font, self.rendered = font, rendered

    def size(self, text):
        return self.font.size(text)

    def get_linesize(self):
        return self.font.get_linesize()

    def render(self, text, antialias, color):
        surface = self.font.render(text, antialias, color)
        # Keep surfaces alive, so their IDs cannot be reused while recording blits.
        self.rendered[id(surface)] = (surface, text, color)
        return surface


class _Screen(pygame.Surface):
    def __init__(self, rendered):
        super().__init__((800, 600))
        self.rendered, self.text = rendered, []

    def blit(self, source, dest, *args, **kwargs):
        if id(source) in self.rendered:
            _, text, color = self.rendered[id(source)]
            position = dest.topleft if isinstance(dest, pygame.Rect) else dest
            self.text.append((text, source.get_rect(topleft=position), color))
        return super().blit(source, dest, *args, **kwargs)


def _make_game():
    rendered = {}
    resources = ResourceManager()
    keys = {"ui_accept": "RIGHT SHIFT", "ui_back": "LEFT CTRL"}
    scores, sounds = [], []
    input_state = SimpleNamespace(actions=set(), keys=set())
    input_state.is_action_just_pressed = lambda action: action in input_state.actions
    input_state.is_just_pressed = lambda key: key in input_state.keys
    noop = lambda *args, **kwargs: None
    return SimpleNamespace(
        resources=SimpleNamespace(
            pixelfont=lambda size: _Font(resources.pixelfont(size), rendered), image=resources.image,
        ),
        rendered=rendered, scores=scores, keys=keys, sounds=sounds, input=input_state,
        settings=SimpleNamespace(key_display=keys.__getitem__),
        highscore=SimpleNamespace(get_scores=lambda: scores, add=noop),
        sound=SimpleNamespace(stop_bgm=noop, play_bgm=noop, play_se=lambda *args, **kwargs: sounds.append(args)),
        playlog=SimpleNamespace(end_run=noop),
        shared=SimpleNamespace(score=123456789012, stage=4, lives=3, kill_count=65432,
                               carry_hp=87, carry_weapon={"main_level": 5}),
    )


@pytest.fixture
def game():
    pygame.init()
    pygame.display.set_mode((800, 600))
    yield _make_game()
    pygame.quit()


def _draw(scene):
    screen = _Screen(scene.game.rendered)
    scene.draw(screen)
    for text, rect, _color in screen.text:
        assert pygame.Rect(20, 0, 760, 600).contains(rect), (text, rect)
    return screen


def _sessions():
    return [dict(
        stage_reached=stage, score=123456789012, cleared=stage == 4,
        events=[
            dict(type="boss_killed", stage=stage, elapsed_sec=234.5),
            dict(type="player_death", stage=stage, elapsed_sec=115.0, weapon=dict(
                main_level=2, speed_level=3, laser_level=2, homing_level=4,
                magnet_level=0, has_barrier=True,
            )),
        ],
    ) for stage in range(1, 5)]


def test_highscore_columns_keep_long_names_and_large_scores_inside_panel(game):
    game.scores.extend(dict(rank=i + 1, name="長いプレイヤー名" * 10,
                            score=game.shared.score - i, stage=4) for i in range(10))
    scene = HighScoreScene(game)
    scene.on_enter()
    screen = _draw(scene)
    score_rect = next(rect for text, rect, _ in screen.text if text == "123,456,789,012")
    assert score_rect.left >= 366 and score_rect.right == 586
    names = [(text, rect) for text, rect, _ in screen.text if text.startswith("長い")]
    assert len(names) == 10
    assert all(text.endswith("…") and rect.right <= 350 for text, rect in names)
    rows = [rect for text, rect, _ in screen.text if text == "第4章"]
    assert len(rows) == 10 and max(rect.bottom for rect in rows) <= 516


def test_empty_highscore_explains_when_records_appear(game):
    scene = HighScoreScene(game)
    scene.on_enter()
    text = [text for text, _rect, _color in _draw(scene).text]
    assert "まだ記録がありません" in text
    assert "プレイを終えると、ここにスコアが残ります。" in text
    assert "順位" not in text


@pytest.mark.parametrize("page", [0, 1, 2])
def test_statistics_pages_fit_and_identify_selected_page(game, monkeypatch, page):
    monkeypatch.setattr(PlayLogger, "load_all_sessions", lambda: _sessions())
    scene = StatsScene(game)
    scene.on_enter()
    scene._page = page
    screen = _draw(scene)
    assert any(text == scene._PAGE_LABELS[page] and color == ACCENT_GOLD
               for text, _rect, color in screen.text)
    body = [(text, rect) for text, rect, _ in screen.text if 138 <= rect.top < 520]
    assert all(pygame.Rect(70, 138, 660, 378).contains(rect) for _text, rect in body)
    if page == 0:
        assert any(text == "到達率" for text, _rect in body)
        assert any(text == "123,456,789,012" for text, _rect in body)
        assert not any(text == "生存率" for text, _rect in body)
    if page == 2:
        assert any(text == "バリア所持率" for text, _rect in body)
        assert any(text == "100%" for text, _rect in body)


def test_empty_statistics_has_no_active_pagination(game, monkeypatch):
    monkeypatch.setattr(PlayLogger, "load_all_sessions", lambda: [])
    scene = StatsScene(game)
    scene.on_enter()
    game.input.keys.add(pygame.K_RIGHT)
    scene.update(0.1)
    assert scene._page == 0 and not game.sounds
    text = "".join(text for text, _rect, _color in _draw(scene).text)
    assert "まだプレイ記録がありません" in text
    assert "ページ切替" not in text


@pytest.mark.parametrize("page, expected", [(1, "倒れた記録はありません"), (2, "装備が記録されたデータはありません")])
def test_statistics_without_death_events_show_explanatory_empty_state(game, monkeypatch, page, expected):
    monkeypatch.setattr(PlayLogger, "load_all_sessions", lambda: [dict(stage_reached=1, events=[])])
    scene = StatsScene(game)
    scene.on_enter()
    scene._page = page
    assert expected in [text for text, _rect, _color in _draw(scene).text]


@pytest.mark.parametrize("lives", [0, 3])
def test_gameover_menu_explains_retry_and_continue_without_overlap(game, lives):
    game.shared.lives = lives
    scene = GameOverScene(game)
    scene.on_enter()
    for lines in GAMEOVER_LINES:
        scene._mono_lines = lines
        screen = _draw(scene)
        menu_text = [(text, rect) for text, rect, _ in screen.text if 284 <= rect.top < 516]
        for index in range(len(scene._options)):
            row = pygame.Rect(86, 284 + index * 72, 628, 66)
            assert all(row.contains(rect) for _text, rect in menu_text if row.top <= rect.top < row.bottom)
        drawn = "".join(text for text, _rect, _color in screen.text)
        assert all(line in drawn for line in lines)
        assert "スコア・強化・有給を初期状態にして第一章へ" in drawn
        assert ("有給を1日使って続ける" in drawn) == (lives > 0)
        assert ("有給は残っていません" in drawn) == (lives == 0)


def test_stageclear_preserves_zero_hp_and_lives_and_medic_label(game):
    game.shared.carry_hp = game.shared.lives = 0
    scene = StageClearScene(game, 2, 3)
    scene.on_enter()
    scene._timer = 2.0
    screen = _draw(scene)
    text = [text for text, _rect, _color in screen.text]
    assert "0 / 100" in text and "0 日" in text
    assert "MEDIC" in text and "123,456,789,012" in text
    assert any("RIGHT SHIFT: 第三章へ進む" in line for line in text)


def test_gameclear_preserves_story_text_and_large_final_score(game):
    scene = GameClearScene(game, record_result=False)
    scene.on_enter()
    scene._timer = 2.0
    scene._is_high = True
    text = "".join(text for text, _rect, _color in _draw(scene).text)
    assert GAME_CLEAR["subtitle"] in text
    assert GAME_CLEAR["next_preview"] in text
    assert "123,456,789,012" in text and "ハイスコア更新！" in text
    assert "RIGHT SHIFT: スタッフロールへ" in text


def test_disclaimer_wraps_canonical_text_and_shows_configured_skip_key(game):
    scene = DisclaimerScene(game)
    scene.on_enter()
    scene._timer = 1.0
    screen = _draw(scene)
    rendered = [(text, surface.get_width()) for surface, text, _ in game.rendered.values()]
    text = "".join(text for text, _width in rendered)
    assert all(line in text for line in BOOT_DISCLAIMER)
    assert not any(line == "。" for line, _width in rendered)
    assert "RIGHT SHIFT" in text and "LEFT CTRL" in text
    assert all(width <= 752 for _text, width in rendered)
    assert screen.get_at((400, 250)) != screen.get_at((400, 20))
