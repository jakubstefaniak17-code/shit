from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ReplayClock:
    start: datetime
    end: datetime
    _now: datetime | None = None
    _paused: bool = True
    _speed: float = 1.0

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("ReplayClock boundaries must be timezone-aware")
        if self.start > self.end:
            raise ValueError("start must not be after end")
        self._now = self.start

    @property
    def now(self) -> datetime:
        assert self._now is not None
        return self._now

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def speed(self) -> float:
        return self._speed

    def play(self) -> None:
        self._paused = False

    def pause(self) -> None:
        self._paused = True

    def set_speed(self, multiplier: float) -> None:
        if multiplier <= 0:
            raise ValueError("speed multiplier must be positive")
        self._speed = multiplier

    def advance_to(self, timestamp: datetime) -> datetime:
        if timestamp < self.now:
            raise ValueError("ReplayClock cannot move backwards")
        if timestamp > self.end:
            raise ValueError("timestamp is outside replay range")
        self._now = timestamp
        return self.now

    def step(self, timestamp: datetime) -> datetime:
        return self.advance_to(timestamp)
