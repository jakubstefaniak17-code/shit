from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .config import RuntimeConfig
from .execution import ExecutionConfig
from .features import FeatureConfig
from .market_data import load_real_dataset
from .risk import DrawdownThresholds, RiskLimits
from .strategies import MomentumStrategy, StrategyConfig
from .trading_runtime import TradingRuntime, TradingRuntimeConfig


def build_real_run(code_commit: str = "0.2-a-real-data"):
    root = Path(__file__).resolve().parents[2]
    dataset, report, manifest = load_real_dataset(root)
    config = RuntimeConfig("research", dataset.metadata.dataset_id, 42, Decimal("100000"), dataset.metadata.start_date, dataset.metadata.end_date)
    limits = RiskLimits(Decimal("0.20"), Decimal("1"), Decimal("0.50"), Decimal("10000"), Decimal("5000"), Decimal("0.20"), Decimal("200000"), DrawdownThresholds(Decimal("0.05"), Decimal("0.10"), Decimal("0.20")))
    trading = TradingRuntimeConfig(Decimal("2"), Decimal("25"), ExecutionConfig(Decimal("1"), 1000, Decimal("0.01")), limits)
    # Keep this foundation demo long-only without introducing a short engine.
    strategy = MomentumStrategy(StrategyConfig(Decimal("0.06"), Decimal("10"), Decimal("0.5"), "5d", ("AAPL",)))
    features = FeatureConfig(5, 5, 5, 1, "SPY")
    result = TradingRuntime(config, trading, dataset, code_commit, strategy, features).run()
    snapshot = config.snapshot() | {"dataset_kind": "REAL HISTORICAL DATASET", "source": dataset.metadata.source, "frequency": dataset.metadata.frequency, "timezone": manifest["timezone"], "adjustment": manifest["adjustment"], "dataset_hash": dataset.metadata.hash, "strategy": "momentum", "simulated_execution": True}
    return result, dataset, snapshot, report, manifest


def main() -> None:
    result, dataset, _, report, manifest = build_real_run()
    print("WEALTH OS 0.2-A — REAL HISTORICAL DATA RESEARCH REPLAY")
    print(f"dataset={dataset.metadata.dataset_id} source={dataset.metadata.source} frequency={dataset.metadata.frequency}")
    print(f"symbols={','.join(dataset.metadata.symbols)} period={dataset.metadata.start_date.date()}..{dataset.metadata.end_date.date()}")
    print(f"quality={'PASS' if report.passed else 'FAIL'} events={len(dataset.events)} hash={dataset.metadata.hash}")
    print(f"intents={len(result.intents)} fills={len(result.fills)} cash={result.portfolio.cash} NAV={result.portfolio.nav}")
    print(f"result_hash={result.result_hash}")


if __name__ == "__main__":
    main()
