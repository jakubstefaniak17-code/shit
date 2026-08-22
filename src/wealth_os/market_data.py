from __future__ import annotations

import csv
import json
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

from .data import CsvDatasetLoader, DatasetMetadata, MarketDataset


class AdjustmentPolicy(str, Enum):
    RAW = "RAW"
    ADJUSTED = "ADJUSTED"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    TOTAL_RETURN_ADJUSTED = "TOTAL_RETURN_ADJUSTED"


@dataclass(frozen=True, slots=True)
class CorporateActionsContract:
    splits: str = "not applied; raw exchange OHLC"
    dividends: str = "not applied; price-only series"


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    row_count: int
    duplicate_count: int
    missing_bar_count: int
    symbols: tuple[str, ...]
    sorted: bool
    timezone_aware: bool
    ohlc_valid: bool
    volume_valid: bool
    hash_verified: bool

    @property
    def passed(self) -> bool:
        return self.duplicate_count == 0 and self.sorted and self.timezone_aware and self.ohlc_valid and self.volume_valid and self.hash_verified


class MarketDataProvider(ABC):
    @abstractmethod
    def fetch(self, symbols: tuple[str, ...], start: datetime, end: datetime) -> list[dict[str, str]]: ...

    def store(self, rows: list[dict[str, str]], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CsvDatasetLoader.REQUIRED_COLUMNS)
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda row: (row["timestamp"], row["symbol"])))


class YahooChartProvider(MarketDataProvider):
    """Small no-key research adapter. Runtime consumes only the canonical CSV."""

    endpoint = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    def fetch(self, symbols: tuple[str, ...], start: datetime, end: datetime) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        eastern = ZoneInfo("America/New_York")
        for symbol in symbols:
            url = self.endpoint.format(symbol=symbol) + f"?period1={int(start.timestamp())}&period2={int(end.timestamp())}&interval=1d&events=history"
            request = urllib.request.Request(url, headers={"User-Agent": "WEALTH-OS-Research/0.2"})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)["chart"]["result"][0]
            quotes = payload["indicators"]["quote"][0]
            for index, epoch in enumerate(payload["timestamp"]):
                values = {name: quotes[name][index] for name in ("open", "high", "low", "close", "volume")}
                if any(value is None for value in values.values()):
                    continue
                stamp = datetime.fromtimestamp(epoch, timezone.utc).astimezone(eastern).replace(hour=16, minute=0, second=0, microsecond=0)
                rows.append({"timestamp": stamp.isoformat(), "symbol": symbol, **{name: str(value) for name, value in values.items()}})
        return rows


def load_real_dataset(root: Path) -> tuple[MarketDataset, DataQualityReport, dict]:
    manifest = json.loads((root / "data" / "market" / "real_historical_sample.manifest.json").read_text(encoding="utf-8"))
    metadata = DatasetMetadata(
        manifest["dataset_id"], manifest["source"], tuple(manifest["symbols"]),
        datetime.fromisoformat(manifest["start"]), datetime.fromisoformat(manifest["end"]),
        manifest["frequency"], manifest["adjustment"], datetime.fromisoformat(manifest["created_at"]),
    )
    dataset = CsvDatasetLoader().load(root / "data" / "market" / "real_historical_sample.csv", metadata)
    events = dataset.events
    keys = [(event.timestamp, event.data.symbol) for event in events]
    key_set = set(keys)
    timestamps = {event.timestamp for event in events}
    missing_bar_count = sum((timestamp, symbol) not in key_set for timestamp in timestamps for symbol in metadata.symbols)
    report = DataQualityReport(
        len(events), len(keys) - len(key_set), missing_bar_count, metadata.symbols, keys == sorted(keys),
        all(event.timestamp.tzinfo is not None for event in events),
        all(event.data.high >= max(event.data.open, event.data.close) and event.data.low <= min(event.data.open, event.data.close) for event in events),
        all(event.data.volume >= Decimal("0") for event in events), dataset.metadata.hash == manifest["content_hash"],
    )
    if not report.passed:
        raise ValueError(f"Real dataset quality failed: {asdict(report)}")
    return dataset, report, manifest
