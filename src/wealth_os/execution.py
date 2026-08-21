from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from .intents import Side
from .orders import Order, OrderStatus, OrderType
from .serialization import stable_hash


@dataclass(frozen=True, slots=True)
class Quote:
    timestamp: datetime
    symbol: str
    bid: Decimal
    ask: Decimal
    bid_size: Decimal
    ask_size: Decimal

    def __post_init__(self) -> None:
        if self.bid <= 0 or self.ask < self.bid or self.bid_size < 0 or self.ask_size < 0:
            raise ValueError("Invalid quote")


class ExecutionOutcome(str, Enum):
    FILLED = "filled"
    PARTIAL = "partial"
    OPEN = "open"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    slippage_bps: Decimal
    latency_ms: int
    commission_per_unit: Decimal

    def __post_init__(self) -> None:
        if self.slippage_bps < 0 or self.latency_ms < 0 or self.commission_per_unit < 0:
            raise ValueError("Execution parameters must be non-negative")


@dataclass(frozen=True, slots=True)
class Fill:
    fill_id: str
    order_id: str
    timestamp: datetime
    symbol: str
    side: Side
    qty: Decimal
    price: Decimal
    fee: Decimal


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    order: Order
    outcome: ExecutionOutcome
    fill: Fill | None
    acknowledged_at: datetime
    reason: str


class ExecutionSimulator:
    def __init__(self, config: ExecutionConfig) -> None:
        self.config = config

    def execute(self, order: Order, quote: Quote) -> ExecutionResult:
        if order.status is not OrderStatus.RISK_APPROVED or not order.is_risk_authorized:
            raise PermissionError("Execution accepts only risk-approved orders")
        sent = order.transition(OrderStatus.SENT)
        acknowledged = sent.transition(OrderStatus.ACK)
        acknowledged_at = max(order.timestamp, quote.timestamp) + timedelta(milliseconds=self.config.latency_ms)
        if quote.symbol != order.symbol:
            rejected = acknowledged.transition(OrderStatus.REJECTED)
            return ExecutionResult(rejected, ExecutionOutcome.REJECTED, None, acknowledged_at, "symbol_mismatch")
        opened = acknowledged.transition(OrderStatus.OPEN)
        marketable = order.order_type is OrderType.MARKET or (
            order.limit_price is not None and ((order.side is Side.BUY and order.limit_price >= quote.ask) or (order.side is Side.SELL and order.limit_price <= quote.bid))
        )
        if not marketable:
            return ExecutionResult(opened, ExecutionOutcome.OPEN, None, acknowledged_at, "limit_not_marketable")
        available = quote.ask_size if order.side is Side.BUY else quote.bid_size
        fill_qty = min(order.qty, available)
        if fill_qty <= 0:
            return ExecutionResult(opened, ExecutionOutcome.OPEN, None, acknowledged_at, "no_liquidity")
        base_price = quote.ask if order.side is Side.BUY else quote.bid
        direction = Decimal("1") if order.side is Side.BUY else Decimal("-1")
        fill_price = base_price * (Decimal("1") + direction * self.config.slippage_bps / Decimal("10000"))
        fee = fill_qty * self.config.commission_per_unit
        values = dict(order_id=order.order_id, timestamp=acknowledged_at, symbol=order.symbol, side=order.side, qty=fill_qty, price=fill_price, fee=fee)
        fill = Fill(stable_hash(values), **values)
        status = OrderStatus.FILLED if fill_qty == order.qty else OrderStatus.PARTIALLY_FILLED
        final_order = opened.transition(status)
        outcome = ExecutionOutcome.FILLED if status is OrderStatus.FILLED else ExecutionOutcome.PARTIAL
        return ExecutionResult(final_order, outcome, fill, acknowledged_at, outcome.value)

    @staticmethod
    def cancel(order: Order) -> Order:
        return order.transition(OrderStatus.CANCELLED)

    @staticmethod
    def expire(order: Order) -> Order:
        return order.transition(OrderStatus.EXPIRED)
