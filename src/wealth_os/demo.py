from __future__ import annotations

import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .config import RuntimeConfig
from .data import CsvDatasetLoader, DatasetMetadata
from .runtime import FoundationRuntime


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "uncommitted"


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    start = datetime.fromisoformat("2024-01-02T09:30:00+00:00")
    end = datetime.fromisoformat("2024-01-02T09:31:00+00:00")
    metadata = DatasetMetadata(
        dataset_id="fixture-ohlcv-us-2024-01-02-v1",
        source="TEST FIXTURE — NOT MARKET DATA",
        symbols=("AAPL", "MSFT"),
        start_date=start,
        end_date=end,
        frequency="1min",
        adjustment_version="unadjusted-v1",
        created_at=datetime.fromisoformat("2026-08-20T00:00:00+00:00"),
    )
    dataset = CsvDatasetLoader().load(root / "data" / "fixtures" / "ohlcv_fixture.csv", metadata)
    config = RuntimeConfig("development", metadata.dataset_id, 42, Decimal("100000"), start, end)
    result = FoundationRuntime(config, dataset, _commit()).run()

    print("WEALTH OS\n")
    print(f"RUN ID:\n{result.metadata.run_id}\n")
    print(f"DATASET:\n{result.metadata.dataset_id} ({metadata.source})\n")
    print(f"REPLAY START:\n{config.replay_start.isoformat()}\n")
    for number, event in enumerate(dataset.events, 1):
        print(f"EVENT {number}\nMarketEvent\n{event.data.symbol}\n{event.timestamp:%H:%M}\n")
    print("PORTFOLIO STATE\n")
    print(f"Cash:\n{result.portfolio.cash}\n")
    print(f"Positions:\n{result.portfolio.positions or 'none'}\n")
    print(f"NAV:\n{result.portfolio.nav}\n")
    print(f"LEDGER EVENTS:\n{len(result.ledger_entry_ids)} (starting cash deposit)\n")
    print("REPLAY COMPLETE")


if __name__ == "__main__":
    main()
