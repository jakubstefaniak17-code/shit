from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal

from .serialization import stable_hash


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    environment: str
    dataset_id: str
    seed: int
    starting_cash: Decimal
    replay_start: datetime
    replay_end: datetime
    base_currency: str = "USD"
    strict_validation: bool = True

    def __post_init__(self) -> None:
        if self.replay_start.tzinfo is None or self.replay_end.tzinfo is None:
            raise ValueError("Replay boundaries must be timezone-aware")
        if self.replay_start > self.replay_end:
            raise ValueError("replay_start must not be after replay_end")
        if self.starting_cash < 0:
            raise ValueError("starting_cash must be non-negative")

    def snapshot(self) -> dict[str, object]:
        return asdict(self)

    @property
    def config_hash(self) -> str:
        return stable_hash(self.snapshot())
