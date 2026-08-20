from datetime import datetime
from decimal import Decimal
from pathlib import Path

from wealth_os.config import RuntimeConfig
from wealth_os.data import CsvDatasetLoader, DatasetMetadata
from wealth_os.runtime import FoundationRuntime


def test_same_inputs_produce_identical_complete_result() -> None:
    start = datetime.fromisoformat("2024-01-02T09:30:00+00:00")
    end = datetime.fromisoformat("2024-01-02T09:31:00+00:00")
    metadata = DatasetMetadata("fixture-v1", "fixture", ("AAPL", "MSFT"), start, end, "1min", "v1", datetime.fromisoformat("2026-08-20T00:00:00+00:00"))
    path = Path(__file__).parents[1] / "data" / "fixtures" / "ohlcv_fixture.csv"
    dataset = CsvDatasetLoader().load(path, metadata)
    config = RuntimeConfig("test", "fixture-v1", 42, Decimal("100000"), start, end)
    first = FoundationRuntime(config, dataset, "abc123").run()
    second = FoundationRuntime(config, dataset, "abc123").run()
    assert first == second
    assert first.result_hash == second.result_hash
