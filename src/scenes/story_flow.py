"""物語タイムライン（script.STORY_BEATS）の駆動。

ゲームプレイの合間に挟まる全画面会話シーン（プロローグ・ステージ間の遷移・
エピローグ・エンドロール）を「並び」として順に再生し、ゲーム本編へ橋渡しする。
シーン結線をここに集約し、各シーンクラスからカットシーン分岐ロジックを排除する。

会話はステージの属性ではなく遷移なので、ステージ番号には束縛しない
（`StoryBeat.before_stage` が『この後に始まるステージ』を表す）。
"""
from __future__ import annotations

from typing import Callable, Iterable

from src.story.lines import StoryBeat
from src.story.script import intro_beats, story_beat


def _apply_finish(game, hook: str | None) -> None:
    """ビート完了時のストーリーフラグ更新フック。"""
    if hook is None:
        return
    if hook == "karonaru_lost":
        # 承認欲求ブラックホールで相棒が先に溶ける（喪失）。
        game.story.karonaru_available = False
        game.story.karonaru_lost = True
        game.story.blackhole_event_done = True
    else:  # pragma: no cover - 未知フックは設定ミス
        raise ValueError(f"unknown StoryBeat.on_finish hook: {hook!r}")


def _scene_for_beat(game, beat: StoryBeat, on_complete: Callable[[], None]):
    """ビートの種別に応じた再生シーンを生成する。"""
    if beat.scene == "blackhole":
        from src.scenes.blackhole_scene import BlackholeScene
        return BlackholeScene(game, list(beat.pages), on_complete)
    from src.scenes.cutscene_scene import CutsceneScene
    return CutsceneScene(
        game, list(beat.pages), on_complete,
        theme=beat.theme, bgm_alias=beat.bgm, stop_bgm=beat.stop_bgm,
        fade_out_on_finish=beat.fade_out_on_finish,
    )


def play_beats(game, beats: Iterable[StoryBeat], on_done: Callable[[], None]) -> None:
    """beats を順番に再生し、すべて終わったら on_done を呼ぶ。"""
    seq = list(beats)

    def step(i: int) -> None:
        if i >= len(seq):
            on_done()
            return
        beat = seq[i]

        def after() -> None:
            _apply_finish(game, beat.on_finish)
            step(i + 1)

        game.change_scene(_scene_for_beat(game, beat, after))

    step(0)


def start_stage(game, stage_id: int) -> None:
    """stage_id の直前ビート群を再生してから GameScene(stage_id) へ遷移する。"""
    def launch() -> None:
        from src.scenes.game_scene import GameScene
        game.change_scene(GameScene(game, stage_id=stage_id))

    play_beats(game, intro_beats(stage_id), launch)


def play_epilogue(game, on_done: Callable[[], None]) -> None:
    """エピローグビートを再生してから on_done（クリア画面）へ。"""
    play_beats(game, [story_beat("epilogue")], on_done)


def credits_pages() -> list:
    """エンドロール用ページ（CreditsRollScene へ渡す）。"""
    return list(story_beat("credits").pages)
