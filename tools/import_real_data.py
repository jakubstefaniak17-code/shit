from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from wealth_os.data import CsvDatasetLoader, DatasetMetadata
from wealth_os.market_data import AdjustmentPolicy, CorporateActionsContract, YahooChartProvider


ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ("AAPL", "MSFT", "SPY")
START = datetime.fromisoformat("2025-01-02T00:00:00-05:00")
END = datetime.fromisoformat("2025-02-01T00:00:00-05:00")
CREATED = datetime.fromisoformat("2026-08-22T00:00:00+00:00")


def main() -> None:
    destination = ROOT / "data" / "market" / "real_historical_sample.csv"
    provider = YahooChartProvider()
    provider.store(provider.fetch(SYMBOLS, START, END), destination)
    metadata = DatasetMetadata("yahoo-aapl-msft-spy-1d-2025-01-v1", "Yahoo Finance Chart API", SYMBOLS, datetime.fromisoformat("2025-01-02T16:00:00-05:00"), datetime.fromisoformat("2025-01-31T16:00:00-05:00"), "1 day", AdjustmentPolicy.RAW.value, CREATED)
    dataset = CsvDatasetLoader().load(destination, metadata)
    manifest = {
        "schema_version": 1, "dataset_id": metadata.dataset_id, "dataset_kind": "REAL HISTORICAL DATASET",
        "source": metadata.source, "symbols": list(SYMBOLS), "start": metadata.start_date.isoformat(),
        "end": metadata.end_date.isoformat(), "frequency": metadata.frequency, "timezone": "America/New_York",
        "adjustment": AdjustmentPolicy.RAW.value, "created_at": CREATED.isoformat(), "content_hash": dataset.metadata.hash,
        "corporate_actions": asdict(CorporateActionsContract()),
    }
    destination.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{destination}\nrows={len(dataset.events)}\nhash={dataset.metadata.hash}")


if __name__ == "__main__":
    main()
