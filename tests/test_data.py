from datetime import datetime
from pathlib import Path

import pytest

from wealth_os.data import CsvDatasetLoader, DatasetMetadata


def metadata() -> DatasetMetadata:
    return DatasetMetadata(
        "fixture-v1",
        "TEST FIXTURE — NOT MARKET DATA",
        ("AAPL", "MSFT"),
        datetime.fromisoformat("2024-01-02T09:30:00+00:00"),
        datetime.fromisoformat("2024-01-02T09:31:00+00:00"),
        "1min",
        "unadjusted-v1",
        datetime.fromisoformat("2026-08-20T00:00:00+00:00"),
    )


def test_loader_validates_and_versions_fixture() -> None:
    path = Path(__file__).parents[1] / "data" / "fixtures" / "ohlcv_fixture.csv"
    dataset = CsvDatasetLoader().load(path, metadata())
    assert len(dataset.events) == 4
    assert len(dataset.metadata.hash) == 64
    assert list(dataset.events) == sorted(dataset.events, key=lambda item: (item.timestamp, item.data.symbol))


def test_loader_rejects_future_rows_against_metadata(tmp_path: Path) -> None:
    path = tmp_path / "future.csv"
    path.write_text("timestamp,symbol,open,high,low,close,volume\n2024-01-03T09:30:00+00:00,AAPL,1,1,1,1,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="outside dataset metadata"):
        CsvDatasetLoader().load(path, metadata())


def test_metadata_requires_point_in_time_aware_boundaries() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        DatasetMetadata(
            "fixture-v1", "fixture", ("AAPL",), datetime(2024, 1, 1),
            datetime.fromisoformat("2024-01-02T09:31:00+00:00"), "1min", "v1",
            datetime.fromisoformat("2026-08-20T00:00:00+00:00"),
        )
