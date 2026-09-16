"""会話パネルの折り返しの回帰テスト。"""
from __future__ import annotations

from src.scenes.dialogue_panel import _visible_lines, _wrap_lines


class _FixedWidthFont:
    def size(self, text: str) -> tuple[int, int]:
        return len(text) * 10, 20


def test_wrap_lines_preserves_typewriter_character_order() -> None:
    wrapped = _wrap_lines(_FixedWidthFont(), ["abcdef", "gh"], 25)

    assert wrapped == ["ab", "cd", "ef", "gh"]
    assert "".join(wrapped) == "abcdefgh"
    assert _visible_lines(wrapped, 3) == ("ab", "c")


def test_balanced_wrap_does_not_start_second_line_with_punctuation() -> None:
    wrapped = _wrap_lines(_FixedWidthFont(), ["あいうえお。かきくけ"], 80)

    assert "".join(wrapped) == "あいうえお。かきくけ"
    assert wrapped[0].endswith("。")
    assert not wrapped[1].startswith("。")
