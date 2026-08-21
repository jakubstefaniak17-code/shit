from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .data import MarketDataset
from .events import MarketEvent
from .execution import ExecutionResult, Fill
from .features import FeatureSnapshot
from .intents import TradeIntent
from .ledger import LedgerEntry, LedgerEntryType
from .orders import Order
from .policy import PortfolioRequest
from .portfolio import PortfolioProjector, PortfolioState
from .risk import RiskAssessment
from .serialization import stable_hash
from .trading_runtime import TradingRunResult


class EvidenceStatus(str, Enum):
    FACT = "fact"
    ESTIMATE = "estimate"
    ASSUMPTION = "assumption"
    UNCERTAINTY = "uncertainty"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class MetricValue:
    value: Decimal | int | None
    status: EvidenceStatus
    reason: str = ""


@dataclass(frozen=True, slots=True)
class EquityPoint:
    timestamp: datetime
    cash: Decimal
    positions_value: Decimal
    nav: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    drawdown: Decimal


@dataclass(frozen=True, slots=True)
class RunMetrics:
    gross_pnl: MetricValue
    execution_costs: MetricValue
    net_pnl: MetricValue
    total_return: MetricValue
    cagr: MetricValue
    sharpe: MetricValue
    sortino: MetricValue
    calmar: MetricValue
    maximum_drawdown: MetricValue
    profit_factor: MetricValue
    expectancy: MetricValue
    turnover: MetricValue
    trade_count: MetricValue
    win_rate: MetricValue


@dataclass(frozen=True, slots=True)
class StrategyExplanation:
    strategy: str
    symbol: str
    timestamp: datetime
    signal_score: Decimal
    reason_codes: tuple[str, ...]
    key_features: tuple[tuple[str, Decimal | None], ...]
    human_readable_explanation: str
    evidence_status: EvidenceStatus = EvidenceStatus.FACT


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    trace_id: str
    market_event: MarketEvent
    features: FeatureSnapshot
    intent: TradeIntent
    explanation: StrategyExplanation
    portfolio_request: PortfolioRequest
    risk_assessment: RiskAssessment
    order: Order
    execution: ExecutionResult
    fill: Fill
    ledger_entries: tuple[LedgerEntry, ...]
    portfolio_state: PortfolioState
    pnl: Decimal


@dataclass(frozen=True, slots=True)
class SimpleDecisionView:
    what_happened: str
    why: str
    strategy_proposal: str
    risk_action: str
    execution_result: str
    result: str


@dataclass(frozen=True, slots=True)
class DecisionRepresentation:
    simple: SimpleDecisionView
    advanced: DecisionTrace


class EquityCurveBuilder:
    @staticmethod
    def build(entries: tuple[LedgerEntry, ...]) -> tuple[EquityPoint, ...]:
        if not entries:
            return ()
        prices: dict[str, Decimal] = {}
        points: list[EquityPoint] = []
        high_water = Decimal("0")
        for index, entry in enumerate(entries):
            if entry.entry_type is LedgerEntryType.FILL and entry.symbol and entry.price is not None:
                prices[entry.symbol] = entry.price
            if entry.entry_type not in {LedgerEntryType.DEPOSIT, LedgerEntryType.NAV}:
                continue
            state = PortfolioProjector.reconstruct(entries[: index + 1], prices)
            positions_value = sum((quantity * prices.get(symbol, Decimal("0")) for symbol, quantity in state.positions.items()), Decimal("0"))
            high_water = max(high_water, state.nav)
            drawdown = (high_water - state.nav) / high_water if high_water else Decimal("0")
            points.append(EquityPoint(entry.timestamp, state.cash, positions_value, state.nav, state.realized_pnl, state.unrealized_pnl, drawdown))
        return tuple(points)


class MetricsCalculator:
    MIN_RETURN_OBSERVATIONS = 30

    @classmethod
    def calculate(cls, entries: tuple[LedgerEntry, ...], curve: tuple[EquityPoint, ...]) -> RunMetrics:
        unavailable = lambda reason: MetricValue(None, EvidenceStatus.INSUFFICIENT_DATA, reason)
        if not curve:
            empty = unavailable("No NAV history")
            return RunMetrics(*(empty for _ in range(14)))
        starting_nav, ending_nav = curve[0].nav, curve[-1].nav
        costs = sum((entry.amount for entry in entries if entry.entry_type in {LedgerEntryType.FEE, LedgerEntryType.EXECUTION_COST}), Decimal("0"))
        net = ending_nav - starting_nav
        gross = net + costs
        total_return = net / starting_nav if starting_nav else None
        max_drawdown = max((point.drawdown for point in curve), default=Decimal("0"))
        fill_entries = tuple(entry for entry in entries if entry.entry_type is LedgerEntryType.FILL)
        turnover_notional = sum((abs(entry.quantity * (entry.price or Decimal("0"))) for entry in fill_entries), Decimal("0"))
        average_nav = sum((point.nav for point in curve), Decimal("0")) / Decimal(len(curve))
        turnover = turnover_notional / average_nav if average_nav else None
        returns = [curve[index].nav / curve[index - 1].nav - Decimal("1") for index in range(1, len(curve)) if curve[index - 1].nav]
        insufficient_returns = len(returns) < cls.MIN_RETURN_OBSERVATIONS
        risk_reason = f"Requires at least {cls.MIN_RETURN_OBSERVATIONS} NAV return observations"
        span_days = (curve[-1].timestamp - curve[0].timestamp).total_seconds() / 86400
        cagr = unavailable("Run duration is too short for annualization") if span_days < 30 or total_return is None else MetricValue((Decimal("1") + total_return) ** (Decimal("365") / Decimal(str(span_days))) - Decimal("1"), EvidenceStatus.FACT)
        if insufficient_returns:
            sharpe = sortino = unavailable(risk_reason)
        else:
            mean_return = sum(returns, Decimal("0")) / Decimal(len(returns))
            variance = sum(((value - mean_return) ** 2 for value in returns), Decimal("0")) / Decimal(len(returns))
            downside = tuple(min(value, Decimal("0")) for value in returns)
            downside_variance = sum((value ** 2 for value in downside), Decimal("0")) / Decimal(len(downside))
            scale = Decimal(len(returns)).sqrt()
            sharpe = MetricValue(mean_return / variance.sqrt() * scale, EvidenceStatus.FACT) if variance > 0 else unavailable("Return variance is zero")
            sortino = MetricValue(mean_return / downside_variance.sqrt() * scale, EvidenceStatus.FACT) if downside_variance > 0 else unavailable("No downside variation")
        calmar = MetricValue(cagr.value / max_drawdown, EvidenceStatus.FACT) if cagr.value is not None and max_drawdown > 0 else unavailable("Requires meaningful CAGR and non-zero drawdown")
        closed_trades = tuple(entry for entry in entries if entry.entry_type is LedgerEntryType.REALIZED_PNL and entry.amount != 0)
        trade_reason = "No closed trades with realized P&L"
        wins = tuple(entry.amount for entry in closed_trades if entry.amount > 0)
        losses = tuple(entry.amount for entry in closed_trades if entry.amount < 0)
        profit_factor = MetricValue(sum(wins, Decimal("0")) / abs(sum(losses, Decimal("0"))), EvidenceStatus.FACT) if wins and losses else unavailable(trade_reason)
        expectancy = MetricValue(sum((entry.amount for entry in closed_trades), Decimal("0")) / Decimal(len(closed_trades)), EvidenceStatus.FACT) if closed_trades else unavailable(trade_reason)
        win_rate = MetricValue(Decimal(len(wins)) / Decimal(len(closed_trades)), EvidenceStatus.FACT) if closed_trades else unavailable(trade_reason)
        return RunMetrics(
            MetricValue(gross, EvidenceStatus.FACT), MetricValue(costs, EvidenceStatus.FACT), MetricValue(net, EvidenceStatus.FACT),
            MetricValue(total_return, EvidenceStatus.FACT) if total_return is not None else unavailable("Starting NAV is zero"),
            cagr, sharpe, sortino, calmar,
            MetricValue(max_drawdown, EvidenceStatus.FACT), profit_factor, expectancy,
            MetricValue(turnover, EvidenceStatus.FACT) if turnover is not None else unavailable("Average NAV is zero"),
            MetricValue(len(fill_entries), EvidenceStatus.FACT), win_rate,
        )


class ExplainabilityEngine:
    FEATURE_KEYS = {
        "momentum": ("return_5m", "market_relative_return"),
        "mean_reversion": ("return_5m", "rolling_volatility"),
        "vwap_reversion": ("vwap_distance", "relative_volume"),
        "residual_reversal": ("residual_return", "rolling_beta"),
    }
    TEMPLATES = {
        "momentum": "{symbol} moved strongly over the configured momentum window; the strategy proposed following that observed direction.",
        "mean_reversion": "{symbol} moved far enough over the configured window for the strategy to propose a reversal toward its recent level.",
        "vwap_reversion": "{symbol} diverged from observed VWAP; the strategy proposed a move back toward VWAP.",
        "residual_reversal": "{symbol}'s return diverged from its benchmark-adjusted expectation; the strategy proposed reversing that residual move.",
    }

    @classmethod
    def explain(cls, intent: TradeIntent, features: FeatureSnapshot) -> StrategyExplanation:
        keys = cls.FEATURE_KEYS.get(intent.strategy_id, ())
        key_features = tuple((key, getattr(features, key)) for key in keys)
        explanation = cls.TEMPLATES.get(intent.strategy_id, "The strategy threshold was met by the observed feature values.").format(symbol=intent.symbol)
        return StrategyExplanation(intent.strategy_id, intent.symbol, intent.timestamp, intent.signal_score, intent.reason_codes, key_features, explanation)


class AuditTrailBuilder:
    @staticmethod
    def build(result: TradingRunResult, dataset: MarketDataset) -> tuple[DecisionTrace, ...]:
        events = {(event.timestamp, event.data.symbol): event for event in dataset.events}
        features = {(snapshot.timestamp, snapshot.symbol): snapshot for snapshot in result.features}
        requests = {request.intent.intent_id: request for request in result.requests}
        assessments = {request.intent.intent_id: assessment for request, assessment in zip(result.requests, result.assessments)}
        orders = {order.intent_id: order for order in result.orders}
        executions = {execution.order.order_id: execution for execution in result.executions}
        fills = {fill.order_id: fill for fill in result.fills}
        traces: list[DecisionTrace] = []
        for intent in result.intents:
            order = orders.get(intent.intent_id)
            if order is None or order.order_id not in fills:
                continue
            fill = fills[order.order_id]
            related = tuple(entry for entry in result.ledger_entries if entry.description in {order.order_id, fill.fill_id})
            if not related:
                raise ValueError(f"Orphan fill without ledger entries: {fill.fill_id}")
            last_index = max(result.ledger_entries.index(entry) for entry in related)
            prices = {fill.symbol: fill.price}
            state = PortfolioProjector.reconstruct(result.ledger_entries[: last_index + 1], prices)
            snapshot = features[(intent.timestamp, intent.symbol)]
            values = {"intent_id": intent.intent_id, "order_id": order.order_id, "fill_id": fill.fill_id}
            traces.append(DecisionTrace(stable_hash(values), events[(intent.timestamp, intent.symbol)], snapshot, intent, ExplainabilityEngine.explain(intent, snapshot), requests[intent.intent_id], assessments[intent.intent_id], order, executions[order.order_id], fill, related, state, -fill.fee))
        return tuple(traces)

    @staticmethod
    def represent(trace: DecisionTrace) -> DecisionRepresentation:
        simple = SimpleDecisionView(
            f"{trace.fill.qty} {trace.fill.symbol} units were {trace.fill.side.value} at {trace.fill.price}.",
            trace.explanation.human_readable_explanation,
            f"{trace.intent.side.value.upper()} {trace.intent.desired_qty}",
            f"{trace.risk_assessment.decision.value.upper()} {trace.risk_assessment.approved_qty}",
            f"{trace.execution.outcome.value.upper()} {trace.fill.qty} units",
            f"Net transaction contribution shown here: {trace.pnl}",
        )
        return DecisionRepresentation(simple, trace)
