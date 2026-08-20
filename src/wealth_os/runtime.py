from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .bus import DeterministicEventBus
from .clock import ReplayClock
from .config import RuntimeConfig
from .data import MarketDataset
from .events import Event
from .ledger import AppendOnlyLedger, LedgerEntryType, make_ledger_entry
from .portfolio import PortfolioProjector, PortfolioState
from .serialization import stable_hash


@dataclass(frozen=True, slots=True)
class RunMetadata:
    run_id: str
    dataset_id: str
    config_hash: str
    code_commit: str
    random_seed: int
    started_at: datetime


@dataclass(frozen=True, slots=True)
class RunResult:
    metadata: RunMetadata
    event_ids: tuple[str, ...]
    ledger_entry_ids: tuple[str, ...]
    portfolio: PortfolioState

    @property
    def result_hash(self) -> str:
        return stable_hash(self)


class FoundationRuntime:
    def __init__(self, config: RuntimeConfig, dataset: MarketDataset, code_commit: str) -> None:
        if config.dataset_id != dataset.metadata.dataset_id:
            raise ValueError("Configured dataset_id does not match loaded dataset")
        self.config = config
        self.dataset = dataset
        self.code_commit = code_commit

    def run(self) -> RunResult:
        identity = {
            "dataset_id": self.dataset.metadata.dataset_id,
            "dataset_hash": self.dataset.metadata.hash,
            "config_hash": self.config.config_hash,
            "code_commit": self.code_commit,
            "seed": self.config.seed,
        }
        metadata = RunMetadata(
            run_id=stable_hash(identity)[:24],
            dataset_id=self.dataset.metadata.dataset_id,
            config_hash=self.config.config_hash,
            code_commit=self.code_commit,
            random_seed=self.config.seed,
            started_at=self.config.replay_start,
        )
        clock = ReplayClock(self.config.replay_start, self.config.replay_end)
        bus = DeterministicEventBus()
        ledger = AppendOnlyLedger()
        observed: list[Event] = []
        last_prices: dict[str, Decimal] = {}
        bus.subscribe(observed.append)
        bus.subscribe(lambda event: last_prices.__setitem__(event.data.symbol, event.data.close))

        ledger.append(make_ledger_entry(
            entry_type=LedgerEntryType.DEPOSIT,
            timestamp=self.config.replay_start,
            sequence=0,
            amount=self.config.starting_cash,
            description="Starting cash from immutable run configuration",
        ))
        clock.play()
        for event in self.dataset.events:
            if event.timestamp < self.config.replay_start:
                continue
            if event.timestamp > self.config.replay_end:
                break
            clock.advance_to(event.timestamp)
            bus.publish(event)
        clock.pause()
        portfolio = PortfolioProjector.reconstruct(ledger.entries, last_prices)
        return RunResult(metadata, tuple(event.event_id for event in observed), tuple(entry.entry_id for entry in ledger.entries), portfolio)
