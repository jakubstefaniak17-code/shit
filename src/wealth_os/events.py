from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Generic, TypeVar

from .serialization import stable_hash


class EventType(str, Enum):
    MARKET = "market"
    SYSTEM = "system"
    TIMER = "timer"


@dataclass(frozen=True, slots=True)
class OHLCV:
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol is required")
        if min(self.open, self.high, self.low, self.close, self.volume) < 0:
            raise ValueError("OHLCV values must be non-negative")
        if self.high < max(self.open, self.low, self.close) or self.low > min(self.open, self.high, self.close):
            raise ValueError("Invalid OHLC price range")


@dataclass(frozen=True, slots=True)
class SystemData:
    name: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class TimerData:
    name: str


PayloadT = TypeVar("PayloadT", OHLCV, SystemData, TimerData)


@dataclass(frozen=True, slots=True)
class Event(Generic[PayloadT]):
    event_id: str
    schema_version: int
    event_type: EventType
    timestamp: datetime
    sequence: int
    source: str
    data: PayloadT

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("Event timestamp must be timezone-aware")
        if self.sequence < 0:
            raise ValueError("Event sequence must be non-negative")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        if not self.event_id or not self.source:
            raise ValueError("event_id and source are required")


MarketEvent = Event[OHLCV]
SystemEvent = Event[SystemData]
TimerEvent = Event[TimerData]


def make_event(*, event_type: EventType, timestamp: datetime, sequence: int, source: str, data: PayloadT) -> Event[PayloadT]:
    identity = {
        "schema_version": 1,
        "event_type": event_type,
        "timestamp": timestamp,
        "sequence": sequence,
        "source": source,
        "data": data,
    }
    return Event(stable_hash(identity), 1, event_type, timestamp, sequence, source, data)
