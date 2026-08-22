from __future__ import annotations

from decimal import Decimal

from .execution import Fill
from .intents import Side
from .ledger import AppendOnlyLedger, LedgerEntryType, make_ledger_entry
from .portfolio import PortfolioProjector, PortfolioState


class FillSettlement:
    """The sole 0.1-B gateway from a fill to financial ledger mutations."""

    @staticmethod
    def settle(fill: Fill, ledger: AppendOnlyLedger, last_prices: dict[str, Decimal]) -> PortfolioState:
        if any(entry.entry_type is LedgerEntryType.FILL and entry.description == fill.fill_id for entry in ledger.entries):
            raise ValueError(f"Duplicate fill: {fill.fill_id}")
        sequence = ledger.entries[-1].sequence + 1 if ledger.entries else 0
        signed_qty = fill.qty if fill.side is Side.BUY else -fill.qty
        signed_cash = -(fill.qty * fill.price) if fill.side is Side.BUY else fill.qty * fill.price
        entries = (
            make_ledger_entry(entry_type=LedgerEntryType.FILL, timestamp=fill.timestamp, sequence=sequence, symbol=fill.symbol, quantity=signed_qty, price=fill.price, description=fill.fill_id),
            make_ledger_entry(entry_type=LedgerEntryType.CASH_CHANGE, timestamp=fill.timestamp, sequence=sequence + 1, amount=signed_cash, description=fill.fill_id),
            make_ledger_entry(entry_type=LedgerEntryType.POSITION_CHANGE, timestamp=fill.timestamp, sequence=sequence + 2, symbol=fill.symbol, quantity=signed_qty, price=fill.price, description=fill.fill_id),
            make_ledger_entry(entry_type=LedgerEntryType.FEE, timestamp=fill.timestamp, sequence=sequence + 3, amount=fill.fee, description=fill.fill_id),
        )
        for entry in entries:
            ledger.append(entry)
        # Compute a fresh mark after this fill. Prior NAV/P&L ledger marks remain audit
        # history and must not override the new point-in-time calculation.
        state = PortfolioProjector.reconstruct(ledger.entries, last_prices, respect_recorded_marks=False)
        ledger.append(make_ledger_entry(entry_type=LedgerEntryType.REALIZED_PNL, timestamp=fill.timestamp, sequence=sequence + 4, amount=Decimal("0"), description=fill.fill_id))
        ledger.append(make_ledger_entry(entry_type=LedgerEntryType.UNREALIZED_PNL, timestamp=fill.timestamp, sequence=sequence + 5, amount=state.unrealized_pnl, description=fill.fill_id))
        ledger.append(make_ledger_entry(entry_type=LedgerEntryType.NAV, timestamp=fill.timestamp, sequence=sequence + 6, amount=state.nav, description=fill.fill_id))
        return PortfolioProjector.reconstruct(ledger.entries, last_prices)
