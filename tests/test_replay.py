from datetime import datetime
from decimal import Decimal

import pytest

from wealth_os.bus import DeterministicEventBus
from wealth_os.clock import ReplayClock
from wealth_os.events import EventType, OHLCV, make_event


def event(timestamp: str, sequence: int, symbol: str = "AAPL"):
    return make_event(
        event_type=EventType.MARKET,
        timestamp=datetime.fromisoformat(timestamp),
        sequence=sequence,
        source="test",
        data=OHLCV(symbol, *(Decimal("1") for _ in range(5))),
    )


def test_bus_preserves_event_and_subscription_order() -> None:
    bus = DeterministicEventBus()
    calls: list[str] = []
    bus.subscribe(lambda item: calls.append(f"all:{item.sequence}"))
    bus.subscribe(lambda item: calls.append(f"market:{item.sequence}"), EventType.MARKET)
    bus.publish(event("2024-01-02T09:30:00+00:00", 0))
    bus.publish(event("2024-01-02T09:31:00+00:00", 1))
    assert calls == ["all:0", "market:0", "all:1", "market:1"]


def test_bus_rejects_time_travel_and_duplicates() -> None:
    bus = DeterministicEventBus()
    bus.publish(event("2024-01-02T09:31:00+00:00", 1))
    with pytest.raises(ValueError):
        bus.publish(event("2024-01-02T09:30:00+00:00", 2))


def test_clock_never_uses_wall_time_and_cannot_move_backwards() -> None:
    start = datetime.fromisoformat("2024-01-02T09:30:00+00:00")
    end = datetime.fromisoformat("2024-01-02T10:00:00+00:00")
    clock = ReplayClock(start, end)
    clock.play()
    clock.step(datetime.fromisoformat("2024-01-02T09:31:00+00:00"))
    assert clock.now.isoformat() == "2024-01-02T09:31:00+00:00"
    with pytest.raises(ValueError):
        clock.step(start)
