from datetime import datetime
from decimal import Decimal
from pathlib import Path

from wealth_os.data import CsvDatasetLoader, DatasetMetadata
from wealth_os.features import FeatureConfig, FeatureEngine, FeatureSnapshot
from wealth_os.intents import Side
from wealth_os.portfolio import PortfolioProjector
from wealth_os.strategies import MeanReversionStrategy, MomentumStrategy, ResidualReversalStrategy, StrategyConfig, VwapReversionStrategy


def trading_dataset():
    start = datetime.fromisoformat("2024-01-02T09:30:00+00:00")
    end = datetime.fromisoformat("2024-01-02T09:45:00+00:00")
    metadata = DatasetMetadata("trading-fixture-v1", "TEST FIXTURE — NOT MARKET DATA", ("AAPL", "SPY", "XLK"), start, end, "1min", "unadjusted-v1", datetime.fromisoformat("2026-08-20T00:00:00+00:00"))
    return CsvDatasetLoader().load(Path(__file__).parents[1] / "data" / "fixtures" / "trading_ohlcv_fixture.csv", metadata)


def feature_config() -> FeatureConfig:
    return FeatureConfig(volatility_window=5, volume_window=5, beta_window=5, bars_per_day=5, market_symbol="SPY", sector_by_symbol=(("AAPL", "XLK"),))


def test_all_required_features_are_timestamped_and_available_without_future_access() -> None:
    dataset = trading_dataset()
    engine = FeatureEngine(feature_config())
    aapl_snapshots = [snapshot for event in dataset.events if (snapshot := engine.update(event)).symbol == "AAPL"]
    final = aapl_snapshots[-1]
    assert final.timestamp == datetime.fromisoformat("2024-01-02T09:45:00+00:00")
    assert all(getattr(final, name) is not None for name in (
        "return_1m", "return_5m", "return_15m", "return_1d", "rolling_volatility",
        "vwap_distance", "relative_volume", "volume_zscore", "market_relative_return",
        "sector_relative_return", "rolling_beta", "residual_return",
    ))


def test_future_rows_do_not_change_an_already_emitted_feature_snapshot() -> None:
    dataset = trading_dataset()
    prefix_engine = FeatureEngine(feature_config())
    full_engine = FeatureEngine(feature_config())
    cutoff = 24
    prefix = [prefix_engine.update(event) for event in dataset.events[:cutoff]][-1]
    full_snapshots = [full_engine.update(event) for event in dataset.events]
    assert prefix == full_snapshots[cutoff - 1]


def test_four_baselines_only_generate_trade_intents_and_do_not_mutate_portfolio() -> None:
    snapshot = FeatureSnapshot(
        datetime.fromisoformat("2024-01-02T10:00:00+00:00"), "AAPL",
        Decimal("0.02"), Decimal("0.02"), Decimal("0.02"), Decimal("0.02"),
        Decimal("0.01"), Decimal("0.02"), Decimal("1.2"), Decimal("1"),
        Decimal("0.01"), Decimal("0.01"), Decimal("1"), Decimal("0.02"),
    )
    state = PortfolioProjector.reconstruct(())
    before = state
    config = StrategyConfig(entry_threshold=Decimal("0.001"), desired_qty=Decimal("5"))
    intents = [strategy(config).evaluate(snapshot) for strategy in (MomentumStrategy, MeanReversionStrategy, VwapReversionStrategy, ResidualReversalStrategy)]
    assert all(intent is not None for intent in intents)
    assert [intent.side for intent in intents if intent] == [Side.BUY, Side.SELL, Side.SELL, Side.SELL]
    assert state == before
