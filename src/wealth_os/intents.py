from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .serialization import stable_hash


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class TradeIntent:
    intent_id: str
    strategy_id: str
    strategy_version: str
    timestamp: datetime
    symbol: str
    side: Side
    signal_score: Decimal
    expected_alpha: Decimal
    horizon: str
    desired_qty: Decimal
    urgency: Decimal
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("TradeIntent timestamp must be timezone-aware")
        if not self.intent_id or not self.strategy_id or not self.strategy_version or not self.symbol:
            raise ValueError("TradeIntent identity fields are required")
        if self.desired_qty <= 0 or not Decimal("0") <= self.urgency <= Decimal("1"):
            raise ValueError("TradeIntent quantity must be positive and urgency must be between 0 and 1")


def make_trade_intent(*, strategy_id: str, strategy_version: str, timestamp: datetime, symbol: str, side: Side, signal_score: Decimal, expected_alpha: Decimal, horizon: str, desired_qty: Decimal, urgency: Decimal, reason_codes: tuple[str, ...]) -> TradeIntent:
    values = dict(strategy_id=strategy_id, strategy_version=strategy_version, timestamp=timestamp, symbol=symbol, side=side, signal_score=signal_score, expected_alpha=expected_alpha, horizon=horizon, desired_qty=desired_qty, urgency=urgency, reason_codes=reason_codes)
    return TradeIntent(stable_hash(values), **values)
