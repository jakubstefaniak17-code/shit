from __future__ import annotations

from dataclasses import dataclass

from .clock import ReplayClock
from .events import Event


@dataclass(frozen=True, slots=True)
class ReplayState:
    status: str
    timestamp: str
    event_index: int
    event_count: int
    speed: str


class ReplayController:
    SPEEDS = {"1x": 1.0, "10x": 10.0, "100x": 100.0, "MAX": 1_000_000.0}

    def __init__(self, events: tuple[Event, ...], clock: ReplayClock) -> None:
        if not events:
            raise ValueError("ReplayController requires events")
        self._events = events
        self._clock = clock
        self._index = 0
        self._speed = "1x"
        self._clock.step(events[0].timestamp)

    def play(self) -> ReplayState:
        self._clock.play()
        return self.state()

    def pause(self) -> ReplayState:
        self._clock.pause()
        return self.state()

    def next_event(self) -> ReplayState:
        if self._index < len(self._events) - 1:
            self._index += 1
            self._clock.step(self._events[self._index].timestamp)
        return self.state()

    def previous_event(self) -> ReplayState:
        if self._index > 0:
            self._index -= 1
            # Moving the UI cursor backwards creates a new logical clock; it does not mutate a completed run.
            self._clock = ReplayClock(self._events[0].timestamp, self._events[-1].timestamp)
            self._clock.step(self._events[self._index].timestamp)
        return self.state()

    def step(self) -> ReplayState:
        self.pause()
        return self.next_event()

    def set_speed(self, speed: str) -> ReplayState:
        if speed not in self.SPEEDS:
            raise ValueError(f"Unsupported replay speed: {speed}")
        self._speed = speed
        self._clock.set_speed(self.SPEEDS[speed])
        return self.state()

    def state(self) -> ReplayState:
        status = "PAUSED" if self._clock.paused else "RUNNING"
        if self._index == len(self._events) - 1:
            status = "COMPLETE"
        return ReplayState(status, self._clock.now.isoformat(), self._index, len(self._events), self._speed)
