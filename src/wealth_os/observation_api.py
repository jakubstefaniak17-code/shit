from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .data import MarketDataset
from .observability import AuditTrailBuilder, DecisionRepresentation, EquityCurveBuilder, MetricsCalculator, RunMetrics
from .replay_controller import ReplayState
from .serialization import to_primitive
from .trading_runtime import TradingRunResult


@dataclass(frozen=True, slots=True)
class HealthState:
    label: str
    status: str
    evidence: str


@dataclass(frozen=True, slots=True)
class ObservationSnapshot:
    run: dict[str, Any]
    replay: ReplayState
    market: dict[str, Any]
    strategies: tuple[dict[str, Any], ...]
    portfolio: dict[str, Any]
    ledger: tuple[dict[str, Any], ...]
    metrics: RunMetrics
    equity_curve: tuple[Any, ...]
    decisions: tuple[DecisionRepresentation, ...]
    health: tuple[HealthState, ...]
    config_snapshot: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)


class ObservationApi:
    STRATEGIES = ("momentum", "mean_reversion", "vwap_reversion", "residual_reversal")

    @classmethod
    def build(cls, result: TradingRunResult, dataset: MarketDataset, replay: ReplayState, config_snapshot: dict[str, Any]) -> ObservationSnapshot:
        curve = EquityCurveBuilder.build(result.ledger_entries)
        metrics = MetricsCalculator.calculate(result.ledger_entries, curve)
        traces = AuditTrailBuilder.build(result, dataset)
        decisions = tuple(AuditTrailBuilder.represent(trace) for trace in traces)
        latest_event = dataset.events[min(replay.event_index, len(dataset.events) - 1)]
        latest_feature = next((feature for feature in reversed(result.features) if feature.symbol == latest_event.data.symbol and feature.timestamp <= latest_event.timestamp), None)
        strategy_rows = []
        for strategy_id in cls.STRATEGIES:
            strategy_traces = tuple(trace for trace in traces if trace.intent.strategy_id == strategy_id)
            costs = sum((trace.fill.fee for trace in strategy_traces), Decimal("0"))
            strategy_rows.append({
                "strategy_id": strategy_id,
                "status": "NORMAL",
                "signals": sum(1 for intent in result.intents if intent.strategy_id == strategy_id),
                "intents": sum(1 for intent in result.intents if intent.strategy_id == strategy_id),
                "trades": len(strategy_traces),
                "net_pnl": str(-costs) if strategy_traces else None,
                "costs": str(costs) if strategy_traces else None,
                "win_rate": None,
                "performance_status": "INSUFFICIENT DATA",
            })
        gross = sum((abs(quantity * result.portfolio.last_prices.get(symbol, Decimal("0"))) for symbol, quantity in result.portfolio.positions.items()), Decimal("0"))
        net = sum((quantity * result.portfolio.last_prices.get(symbol, Decimal("0")) for symbol, quantity in result.portfolio.positions.items()), Decimal("0"))
        run = {
            **to_primitive(result.metadata),
            "status": replay.status,
            "event_count": len(result.features),
            "ledger_entry_count": len(result.ledger_entries),
            "result_hash": result.result_hash,
        }
        market = {"event": to_primitive(latest_event), "features": to_primitive(latest_feature) if latest_feature else None, "recent_events": to_primitive(dataset.events[max(0, replay.event_index - 9): replay.event_index + 1])}
        portfolio = {**to_primitive(result.portfolio), "gross_exposure": str(gross), "net_exposure": str(net), "drawdown": str(curve[-1].drawdown if curve else Decimal("0"))}
        health = tuple(HealthState(label, "GREEN / NORMAL", "FACT") for label in ("Data Health", "Strategy Health", "Execution Health", "System Health"))
        return ObservationSnapshot(run, replay, market, tuple(strategy_rows), portfolio, tuple(to_primitive(entry) for entry in result.ledger_entries), metrics, curve, decisions, health, to_primitive(config_snapshot))
