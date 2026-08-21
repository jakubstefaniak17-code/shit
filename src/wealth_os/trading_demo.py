from __future__ import annotations

import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .config import RuntimeConfig
from .data import CsvDatasetLoader, DatasetMetadata
from .execution import ExecutionConfig
from .features import FeatureConfig
from .risk import DrawdownThresholds, RiskLimits
from .strategies import MomentumStrategy, StrategyConfig
from .trading_runtime import TradingRuntime, TradingRuntimeConfig


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "uncommitted"


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    start = datetime.fromisoformat("2024-01-02T09:30:00+00:00")
    end = datetime.fromisoformat("2024-01-02T09:45:00+00:00")
    metadata = DatasetMetadata("trading-fixture-v1", "TEST FIXTURE — NOT MARKET DATA", ("AAPL", "SPY", "XLK"), start, end, "1min", "unadjusted-v1", datetime.fromisoformat("2026-08-20T00:00:00+00:00"))
    dataset = CsvDatasetLoader().load(root / "data" / "fixtures" / "trading_ohlcv_fixture.csv", metadata)
    config = RuntimeConfig("development", metadata.dataset_id, 42, Decimal("100000"), start, end)
    limits = RiskLimits(Decimal("0.20"), Decimal("1"), Decimal("0.50"), Decimal("5000"), Decimal("5000"), Decimal("0.20"), Decimal("100000"), DrawdownThresholds(Decimal("0.05"), Decimal("0.10"), Decimal("0.20")))
    trading = TradingRuntimeConfig(Decimal("2"), Decimal("5"), ExecutionConfig(Decimal("1"), 10, Decimal("0.01")), limits)
    strategy = MomentumStrategy(StrategyConfig(Decimal("0.001"), Decimal("10"), Decimal("0.5"), "15m", ("AAPL",)))
    feature_config = FeatureConfig(5, 5, 5, 5, "SPY", (("AAPL", "XLK"),))
    result = TradingRuntime(config, trading, dataset, _commit(), strategy, feature_config).run()
    first_intent = result.intents[0]
    first_features = next(snapshot for snapshot in result.features if snapshot.timestamp == first_intent.timestamp and snapshot.symbol == first_intent.symbol)
    first_request, first_risk, first_order, first_execution = result.requests[0], result.assessments[0], result.orders[0], result.executions[0]
    first_fill = result.fills[0]

    print("WEALTH OS - 0.1-B TRADING CORE\n")
    print(f"RUN ID\n{result.metadata.run_id}\n")
    print(f"REPLAY\n{start.isoformat()} -> {end.isoformat()}\n")
    print(f"MARKET EVENT\n{first_intent.symbol} @ {first_intent.timestamp.isoformat()}\n")
    print(f"FEATURES\nreturn_5m={first_features.return_5m} vwap_distance={first_features.vwap_distance}\n")
    print(f"STRATEGY\n{first_intent.strategy_id}\n")
    print(f"TRADE INTENT\n{first_intent.intent_id} {first_intent.side.value} desired_qty={first_intent.desired_qty}\n")
    print(f"PORTFOLIO\nrequested_qty={first_request.requested_qty}\n")
    print(f"RISK\n{first_risk.decision.value.upper()} approved_qty={first_risk.approved_qty}\n")
    print(f"ORDER\n{first_order.order_id} status={first_order.status.value} qty={first_order.qty}\n")
    print(f"EXECUTION\n{first_execution.outcome.value} latency_ms={trading.execution.latency_ms}\n")
    print(f"FILL\n{first_fill.fill_id} qty={first_fill.qty} price={first_fill.price} fee={first_fill.fee}\n")
    print(f"LEDGER\nentries={len(result.ledger_entry_ids)}\n")
    print(f"PORTFOLIO STATE\ncash={result.portfolio.cash} positions={dict(result.portfolio.positions)} NAV={result.portfolio.nav}\n")
    print("REPLAY COMPLETE")


if __name__ == "__main__":
    main()
