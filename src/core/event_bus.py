from collections import defaultdict
from typing import Callable


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event_name: str, callback: Callable) -> None:
        self._listeners[event_name].append(callback)

    def off(self, event_name: str, callback: Callable) -> None:
        self._listeners[event_name].remove(callback)

    def emit(self, event_name: str, **kwargs) -> None:
        for callback in list(self._listeners[event_name]):
            callback(**kwargs)
