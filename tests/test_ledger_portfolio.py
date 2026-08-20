from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from wealth_os.ledger import AppendOnlyLedger, LedgerEntryType, make_ledger_entry
from wealth_os.portfolio import PortfolioProjector


START = datetime.fromisoformat("2024-01-02T09:30:00+00:00")


def entry(kind: LedgerEntryType, sequence: int, amount: str = "0", **kwargs):
    return make_ledger_entry(entry_type=kind, timestamp=START + timedelta(seconds=sequence), sequence=sequence, amount=Decimal(amount), **kwargs)


def test_ledger_is_append_only_and_exposes_immutable_history() -> None:
    ledger = AppendOnlyLedger()
    first = entry(LedgerEntryType.DEPOSIT, 0, "100")
    ledger.append(first)
    assert ledger.entries == (first,)
    with pytest.raises(AttributeError):
        ledger.entries.append(first)  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        ledger.append(first)


def test_cash_and_state_reconstruct_identically_from_history() -> None:
    history = (
        entry(LedgerEntryType.DEPOSIT, 0, "100000"),
        entry(LedgerEntryType.FEE, 1, "5"),
        entry(LedgerEntryType.REALIZED_PNL, 2, "20"),
        entry(LedgerEntryType.POSITION_CHANGE, 3, symbol="AAPL", quantity=Decimal("2"), price=Decimal("100")),
    )
    one = PortfolioProjector.reconstruct(history, {"AAPL": Decimal("110")})
    two = PortfolioProjector.reconstruct(history, {"AAPL": Decimal("110")})
    assert one == two
    assert one.cash == Decimal("100015")
    assert one.positions == {"AAPL": Decimal("2")}
    assert one.nav == Decimal("100235")
    assert one.unrealized_pnl == Decimal("20")
