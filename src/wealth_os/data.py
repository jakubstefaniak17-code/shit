from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .events import EventType, MarketEvent, OHLCV, make_event
from .serialization import stable_hash


@dataclass(frozen=True, slots=True)
class DatasetMetadata:
    dataset_id: str
    source: str
    symbols: tuple[str, ...]
    start_date: datetime
    end_date: datetime
    frequency: str
    adjustment_version: str
    created_at: datetime
    hash: str = ""

    def with_computed_hash(self, rows: tuple[tuple[str, ...], ...]) -> "DatasetMetadata":
        unsigned = replace(self, hash="")
        return replace(self, hash=stable_hash({"metadata": unsigned, "rows": rows}))


@dataclass(frozen=True, slots=True)
class MarketDataset:
    metadata: DatasetMetadata
    events: tuple[MarketEvent, ...]


class CsvDatasetLoader:
    REQUIRED_COLUMNS = ("timestamp", "symbol", "open", "high", "low", "close", "volume")

    def load(self, path: Path, metadata: DatasetMetadata) -> MarketDataset:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or any(column not in reader.fieldnames for column in self.REQUIRED_COLUMNS):
                raise ValueError(f"CSV must contain: {', '.join(self.REQUIRED_COLUMNS)}")
            raw_rows = tuple(tuple(row[column] for column in self.REQUIRED_COLUMNS) for row in reader)

        events: list[MarketEvent] = []
        seen_keys: set[tuple[datetime, str]] = set()
        previous: tuple[datetime, str] | None = None
        for sequence, row in enumerate(raw_rows):
            timestamp = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            symbol = row[1]
            key = (timestamp, symbol)
            if timestamp.tzinfo is None:
                raise ValueError("Dataset timestamps must be timezone-aware")
            if previous is not None and key <= previous:
                raise ValueError("Rows must be strictly sorted by timestamp and symbol")
            if key in seen_keys:
                raise ValueError(f"Duplicate market key: {key}")
            if timestamp < metadata.start_date or timestamp > metadata.end_date:
                raise ValueError("Row is outside dataset metadata boundaries")
            previous = key
            seen_keys.add(key)
            data = OHLCV(symbol, *(Decimal(value) for value in row[2:]))
            events.append(make_event(event_type=EventType.MARKET, timestamp=timestamp, sequence=sequence, source=metadata.source, data=data))

        if tuple(sorted({event.data.symbol for event in events})) != tuple(sorted(metadata.symbols)):
            raise ValueError("Dataset symbols do not match metadata")
        return MarketDataset(metadata.with_computed_hash(raw_rows), tuple(events))
