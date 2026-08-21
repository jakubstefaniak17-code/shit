from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .intents import Side
from .policy import PortfolioRequest
from .risk import RiskAssessment, RiskDecision, _RISK_AUTHORITY
from .serialization import stable_hash


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    CREATED = "created"
    RISK_APPROVED = "risk_approved"
    SENT = "sent"
    ACK = "ack"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


ALLOWED_TRANSITIONS = {
    OrderStatus.CREATED: {OrderStatus.RISK_APPROVED, OrderStatus.REJECTED},
    OrderStatus.RISK_APPROVED: {OrderStatus.SENT},
    OrderStatus.SENT: {OrderStatus.ACK, OrderStatus.REJECTED},
    OrderStatus.ACK: {OrderStatus.OPEN, OrderStatus.REJECTED},
    OrderStatus.OPEN: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.EXPIRED},
    OrderStatus.PARTIALLY_FILLED: {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.EXPIRED},
}


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    intent_id: str
    timestamp: datetime
    symbol: str
    side: Side
    qty: Decimal
    order_type: OrderType
    limit_price: Decimal | None
    status: OrderStatus
    _risk_authority: object | None = field(default=None, repr=False, compare=False, metadata={"serialize": False})

    @property
    def is_risk_authorized(self) -> bool:
        return self._risk_authority is _RISK_AUTHORITY

    def transition(self, status: OrderStatus) -> "Order":
        if status not in ALLOWED_TRANSITIONS.get(self.status, set()):
            raise ValueError(f"Invalid order transition: {self.status.value} -> {status.value}")
        return replace(self, status=status)


class OrderFactory:
    """The only order constructor; requires an authoritative risk assessment."""

    @staticmethod
    def create(request: PortfolioRequest, assessment: RiskAssessment, order_type: OrderType = OrderType.MARKET, limit_price: Decimal | None = None) -> Order:
        if not assessment.is_authoritative or assessment.decision not in {RiskDecision.PASS, RiskDecision.RESIZE} or assessment.approved_qty == 0:
            raise PermissionError("Order creation requires PASS or RESIZE from GlobalRiskEngine")
        if order_type is OrderType.LIMIT and (limit_price is None or limit_price <= 0):
            raise ValueError("Limit order requires a positive limit_price")
        side = Side.BUY if assessment.approved_qty > 0 else Side.SELL
        values = dict(intent_id=request.intent.intent_id, timestamp=request.intent.timestamp, symbol=request.intent.symbol, side=side, qty=abs(assessment.approved_qty), order_type=order_type, limit_price=limit_price)
        created = Order(stable_hash(values), **values, status=OrderStatus.CREATED, _risk_authority=assessment._authority)
        return created.transition(OrderStatus.RISK_APPROVED)
