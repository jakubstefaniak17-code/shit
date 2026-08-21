from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from .policy import PortfolioRequest

_RISK_AUTHORITY = object()


class RiskDecision(str, Enum):
    PASS = "pass"
    RESIZE = "resize"
    REJECT = "reject"
    HALT = "halt"


class DrawdownState(str, Enum):
    NORMAL = "normal"
    CAUTION = "caution"
    DEFENSIVE = "defensive"
    HALT = "halt"


@dataclass(frozen=True, slots=True)
class DrawdownThresholds:
    caution: Decimal
    defensive: Decimal
    halt: Decimal

    def __post_init__(self) -> None:
        if not (Decimal("0") <= self.caution < self.defensive < self.halt):
            raise ValueError("Drawdown thresholds must be non-negative and strictly increasing")


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_position_weight: Decimal
    max_gross_exposure: Decimal
    max_net_exposure: Decimal
    max_order_notional: Decimal
    max_daily_loss: Decimal
    max_drawdown: Decimal
    max_turnover: Decimal
    drawdown_thresholds: DrawdownThresholds

    def __post_init__(self) -> None:
        values = (self.max_position_weight, self.max_gross_exposure, self.max_net_exposure, self.max_order_notional, self.max_daily_loss, self.max_drawdown, self.max_turnover)
        if any(value <= 0 for value in values):
            raise ValueError("All risk limits must be positive")
        if self.drawdown_thresholds.halt > self.max_drawdown:
            raise ValueError("Drawdown HALT threshold cannot exceed max_drawdown")


@dataclass(frozen=True, slots=True)
class RiskContext:
    nav: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    daily_pnl: Decimal
    drawdown: Decimal
    turnover: Decimal


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    decision: RiskDecision
    approved_qty: Decimal
    drawdown_state: DrawdownState
    reason_codes: tuple[str, ...]
    _authority: object | None = field(default=None, repr=False, compare=False, metadata={"serialize": False})

    @property
    def is_authoritative(self) -> bool:
        return self._authority is _RISK_AUTHORITY


class GlobalRiskEngine:
    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits

    def drawdown_state(self, drawdown: Decimal) -> DrawdownState:
        thresholds = self.limits.drawdown_thresholds
        if drawdown >= thresholds.halt:
            return DrawdownState.HALT
        if drawdown >= thresholds.defensive:
            return DrawdownState.DEFENSIVE
        if drawdown >= thresholds.caution:
            return DrawdownState.CAUTION
        return DrawdownState.NORMAL

    def assess(self, request: PortfolioRequest, context: RiskContext) -> RiskAssessment:
        state = self.drawdown_state(context.drawdown)
        if context.nav <= 0 or context.daily_pnl <= -self.limits.max_daily_loss or context.drawdown >= self.limits.max_drawdown or state is DrawdownState.HALT:
            return RiskAssessment(RiskDecision.HALT, Decimal("0"), DrawdownState.HALT, ("loss_or_drawdown_halt",), _RISK_AUTHORITY)
        if request.requested_qty == 0:
            return RiskAssessment(RiskDecision.REJECT, Decimal("0"), state, ("zero_requested_qty",), _RISK_AUTHORITY)

        sign = Decimal("1") if request.requested_qty > 0 else Decimal("-1")
        requested_abs = abs(request.requested_qty)
        current_sign = Decimal("1") if request.current_qty > 0 else Decimal("-1") if request.current_qty < 0 else Decimal("0")
        position_capacity = context.nav * self.limits.max_position_weight / request.price
        position_order_cap = max(Decimal("0"), position_capacity - abs(request.current_qty)) if current_sign in {Decimal("0"), sign} else abs(request.current_qty) + position_capacity
        caps = [
            self.limits.max_order_notional / request.price,
            position_order_cap,
            max(Decimal("0"), context.nav * self.limits.max_gross_exposure - context.gross_exposure) / request.price,
            max(Decimal("0"), self.limits.max_turnover - context.turnover) / request.price,
        ]
        if sign > 0:
            caps.append(max(Decimal("0"), context.nav * self.limits.max_net_exposure - context.net_exposure) / request.price)
        else:
            caps.append(max(Decimal("0"), context.nav * self.limits.max_net_exposure + context.net_exposure) / request.price)
        approved_abs = min([requested_abs, *caps]).to_integral_value(rounding="ROUND_FLOOR")
        if state is DrawdownState.DEFENSIVE:
            approved_abs = min(approved_abs, (requested_abs / Decimal("2")).to_integral_value(rounding="ROUND_FLOOR"))
        elif state is DrawdownState.CAUTION:
            approved_abs = min(approved_abs, (requested_abs * Decimal("0.75")).to_integral_value(rounding="ROUND_FLOOR"))
        if approved_abs <= 0:
            return RiskAssessment(RiskDecision.REJECT, Decimal("0"), state, ("risk_capacity_exhausted",), _RISK_AUTHORITY)
        approved = sign * approved_abs
        if approved_abs < requested_abs:
            return RiskAssessment(RiskDecision.RESIZE, approved, state, ("risk_limit_resize",), _RISK_AUTHORITY)
        return RiskAssessment(RiskDecision.PASS, approved, state, ("within_limits",), _RISK_AUTHORITY)
