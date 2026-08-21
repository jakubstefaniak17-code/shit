from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .serialization import stable_hash


class LedgerEntryType(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    CASH_CHANGE = "cash_change"
    POSITION_CHANGE = "position_change"
    FEE = "fee"
    REALIZED_PNL = "realized_pnl"
    UNREALIZED_PNL = "unrealized_pnl"
    NAV = "nav"
    ORDER = "order"
    FILL = "fill"
    EXECUTION_COST = "execution_cost"
    TAX = "tax"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    entry_id: str
    entry_type: LedgerEntryType
    timestamp: datetime
    sequence: int
    amount: Decimal = Decimal("0")
    symbol: str | None = None
    quantity: Decimal = Decimal("0")
    price: Decimal | None = None
    description: str = ""


def make_ledger_entry(*, entry_type: LedgerEntryType, timestamp: datetime, sequence: int, amount: Decimal = Decimal("0"), symbol: str | None = None, quantity: Decimal = Decimal("0"), price: Decimal | None = None, description: str = "") -> LedgerEntry:
    if timestamp.tzinfo is None:
        raise ValueError("Ledger timestamp must be timezone-aware")
    values = dict(entry_type=entry_type, timestamp=timestamp, sequence=sequence, amount=amount, symbol=symbol, quantity=quantity, price=price, description=description)
    return LedgerEntry(stable_hash(values), **values)


class AppendOnlyLedger:
    def __init__(self) -> None:
        self._entries: tuple[LedgerEntry, ...] = ()

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return self._entries

    def append(self, entry: LedgerEntry) -> None:
        if any(existing.entry_id == entry.entry_id for existing in self._entries):
            raise ValueError(f"Duplicate ledger entry: {entry.entry_id}")
        if self._entries and (entry.timestamp, entry.sequence) <= (self._entries[-1].timestamp, self._entries[-1].sequence):
            raise ValueError("Ledger entries must be appended in strict chronological sequence")
        self._entries = (*self._entries, entry)
