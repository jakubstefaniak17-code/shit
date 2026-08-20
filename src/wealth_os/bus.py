from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from .events import Event, EventType

Handler = Callable[[Event], None]


class DeterministicEventBus:
    """Synchronous dispatch; subscription order is dispatch order."""

    def __init__(self) -> None:
        self._handlers: dict[EventType | None, list[Handler]] = defaultdict(list)
        self._last_key: tuple[object, int] | None = None
        self._event_ids: set[str] = set()

    def subscribe(self, handler: Handler, event_type: EventType | None = None) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        key = (event.timestamp, event.sequence)
        if self._last_key is not None and key <= self._last_key:
            raise ValueError("Events must have a strictly increasing (timestamp, sequence) key")
        if event.event_id in self._event_ids:
            raise ValueError(f"Duplicate event_id: {event.event_id}")
        self._last_key = key
        self._event_ids.add(event.event_id)
        for handler in (*self._handlers[None], *self._handlers[event.event_type]):
            handler(event)
