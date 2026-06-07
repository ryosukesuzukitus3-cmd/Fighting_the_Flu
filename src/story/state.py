"""ストーリー進行フラグ（台本 §2）。

カロナール先輩の同行状況やイベント既読を保持する。`Game` に 1 つ持たせ、
シーンをまたいで保持する。NEW GAME 開始時に reset() で初期化する。
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class StoryState:
    karonaru_joined:      bool = False   # カロナール先輩が同行開始済み
    karonaru_available:   bool = False   # 通常随伴中
    karonaru_retired:     bool = False   # HP0 などで一時撤退中
    karonaru_lost:        bool = False   # Stage3 後に消息不明
    karonaru_max:         bool = False   # 薬効最大形態で復帰済み
    blackhole_event_done: bool = False   # 承認欲求ブラックホールイベント済み
    final_self_distanced: bool = False   # 投了王と自分の分離に成功

    def reset(self) -> None:
        """NEW GAME 開始時に初期状態へ戻す。"""
        for f in self.__dataclass_fields__:
            setattr(self, f, False)

    def begin_journey(self) -> None:
        """プロローグでカロナール先輩が同行を開始した状態にする。"""
        self.reset()
        self.karonaru_joined    = True
        self.karonaru_available = True
