from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .intents import Side, TradeIntent
from .portfolio import PortfolioState


@dataclass(frozen=True, slots=True)
class PortfolioPolicyConfig:
    max_target_weight: Decimal = Decimal("0.10")

    def __post_init__(self) -> None:
        if not Decimal("0") < self.max_target_weight <= Decimal("1"):
            raise ValueError("max_target_weight must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class PortfolioRequest:
    intent: TradeIntent
    requested_qty: Decimal
    current_qty: Decimal
    price: Decimal


class PortfolioPolicy:
    def __init__(self, config: PortfolioPolicyConfig = PortfolioPolicyConfig()) -> None:
        self.config = config

    def evaluate(self, intent: TradeIntent, state: PortfolioState, price: Decimal) -> PortfolioRequest:
        if price <= 0 or state.nav <= 0:
            raise ValueError("Portfolio evaluation requires positive price and NAV")
        max_qty = (state.nav * self.config.max_target_weight / price).to_integral_value(rounding="ROUND_FLOOR")
        requested = min(intent.desired_qty, max_qty)
        signed = requested if intent.side is Side.BUY else -requested
        return PortfolioRequest(intent, signed, state.positions.get(intent.symbol, Decimal("0")), price)
