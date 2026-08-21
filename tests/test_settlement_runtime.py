from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from wealth_os.config import RuntimeConfig
from wealth_os.execution import ExecutionConfig, Fill
from wealth_os.features import FeatureConfig
from wealth_os.intents import Side
from wealth_os.ledger import AppendOnlyLedger, LedgerEntryType, make_ledger_entry
from wealth_os.risk import DrawdownThresholds, RiskLimits
from wealth_os.settlement import FillSettlement
from wealth_os.strategies import MomentumStrategy, StrategyConfig
from wealth_os.trading_runtime import TradingRuntime, TradingRuntimeConfig

from test_features_strategies import trading_dataset


START = datetime.fromisoformat("2024-01-02T09:30:00+00:00")


def test_only_fill_settlement_changes_position_and_duplicate_fill_is_rejected() -> None:
    ledger = AppendOnlyLedger()
    ledger.append(make_ledger_entry(entry_type=LedgerEntryType.DEPOSIT, timestamp=START, sequence=0, amount=Decimal("1000")))
    fill = Fill("fill-1", "order-1", START + timedelta(seconds=1), "AAPL", Side.BUY, Decimal("1"), Decimal("100"), Decimal("1"))
    state = FillSettlement.settle(fill, ledger, {"AAPL": Decimal("100")})
    assert state.positions == {"AAPL": Decimal("1")}
    assert state.cash == Decimal("899")
    assert sum((entry.quantity for entry in ledger.entries if entry.entry_type is LedgerEntryType.POSITION_CHANGE), Decimal("0")) == Decimal("1")
    with pytest.raises(ValueError, match="Duplicate fill"):
        FillSettlement.settle(fill, ledger, {"AAPL": Decimal("100")})


def runtime_result(slippage_bps: Decimal = Decimal("1")):
    dataset = trading_dataset()
    config = RuntimeConfig("test", dataset.metadata.dataset_id, 42, Decimal("100000"), dataset.metadata.start_date, dataset.metadata.end_date)
    limits = RiskLimits(Decimal("0.20"), Decimal("1"), Decimal("0.50"), Decimal("5000"), Decimal("5000"), Decimal("0.20"), Decimal("100000"), DrawdownThresholds(Decimal("0.05"), Decimal("0.10"), Decimal("0.20")))
    trading = TradingRuntimeConfig(Decimal("2"), Decimal("5"), ExecutionConfig(slippage_bps, 10, Decimal("0.01")), limits)
    strategy = MomentumStrategy(StrategyConfig(Decimal("0.001"), Decimal("10"), Decimal("0.5"), "15m", ("AAPL",)))
    features = FeatureConfig(5, 5, 5, 5, "SPY", (("AAPL", "XLK"),))
    return TradingRuntime(config, trading, dataset, "commit-abc", strategy, features).run()


def test_complete_trading_loop_is_reproducible_and_fill_drives_position() -> None:
    first = runtime_result()
    second = runtime_result()
    assert first == second
    assert first.result_hash == second.result_hash
    assert first.intents and first.orders and first.fills
    assert first.portfolio.positions["AAPL"] == sum((fill.qty if fill.side is Side.BUY else -fill.qty for fill in first.fills), Decimal("0"))
    assert all(fill.qty <= order.qty for fill, order in zip(first.fills, first.orders))


def test_trading_parameters_are_part_of_config_hash_and_result_identity() -> None:
    baseline = runtime_result(Decimal("1"))
    changed = runtime_result(Decimal("2"))
    assert baseline.metadata.config_hash != changed.metadata.config_hash
    assert baseline.metadata.run_id != changed.metadata.run_id
