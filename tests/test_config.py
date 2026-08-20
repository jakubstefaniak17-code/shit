from datetime import datetime
from decimal import Decimal

from wealth_os.config import RuntimeConfig


def test_config_snapshot_and_hash_are_stable() -> None:
    start = datetime.fromisoformat("2024-01-02T09:30:00+00:00")
    config = RuntimeConfig("test", "dataset-v1", 42, Decimal("100000"), start, start)
    assert config.snapshot()["dataset_id"] == "dataset-v1"
    assert config.config_hash == config.config_hash


def test_config_rejects_naive_time() -> None:
    try:
        RuntimeConfig("test", "d", 1, Decimal("1"), datetime(2024, 1, 1), datetime(2024, 1, 1))
    except ValueError as error:
        assert "timezone-aware" in str(error)
    else:
        raise AssertionError("Expected ValueError")
