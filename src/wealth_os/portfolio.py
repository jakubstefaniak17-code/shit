from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType

from .ledger import LedgerEntry, LedgerEntryType


@dataclass(frozen=True, slots=True)
class PortfolioState:
    cash: Decimal = Decimal("0")
    positions: Mapping[str, Decimal] = field(default_factory=lambda: MappingProxyType({}))
    nav: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    last_prices: Mapping[str, Decimal] = field(default_factory=lambda: MappingProxyType({}))


class PortfolioProjector:
    """Builds a replaceable view. The ledger remains the financial source of truth."""

    @staticmethod
    def reconstruct(entries: tuple[LedgerEntry, ...], last_prices: dict[str, Decimal] | None = None) -> PortfolioState:
        cash = Decimal("0")
        positions: dict[str, Decimal] = {}
        cost_basis: dict[str, Decimal] = {}
        realized = Decimal("0")
        recorded_unrealized: Decimal | None = None
        recorded_nav: Decimal | None = None

        for entry in entries:
            if entry.entry_type in {LedgerEntryType.DEPOSIT, LedgerEntryType.CASH_CHANGE, LedgerEntryType.REALIZED_PNL}:
                cash += entry.amount
            elif entry.entry_type in {LedgerEntryType.WITHDRAWAL, LedgerEntryType.FEE}:
                cash -= entry.amount
            if entry.entry_type == LedgerEntryType.REALIZED_PNL:
                realized += entry.amount
            elif entry.entry_type == LedgerEntryType.UNREALIZED_PNL:
                recorded_unrealized = entry.amount
            elif entry.entry_type == LedgerEntryType.NAV:
                recorded_nav = entry.amount
            elif entry.entry_type == LedgerEntryType.POSITION_CHANGE:
                if not entry.symbol:
                    raise ValueError("position_change requires symbol")
                if entry.price is None:
                    raise ValueError("position_change requires price")
                old_quantity = positions.get(entry.symbol, Decimal("0"))
                old_basis = cost_basis.get(entry.symbol, Decimal("0"))
                new_quantity = old_quantity + entry.quantity
                positions[entry.symbol] = new_quantity

                if old_quantity == 0 or old_quantity * entry.quantity > 0:
                    cost_basis[entry.symbol] = old_basis + entry.quantity * entry.price
                elif new_quantity == 0:
                    del positions[entry.symbol]
                    del cost_basis[entry.symbol]
                elif old_quantity * new_quantity > 0:
                    cost_basis[entry.symbol] = (old_basis / old_quantity) * new_quantity
                else:
                    cost_basis[entry.symbol] = new_quantity * entry.price

        prices = dict(last_prices or {})
        market_value = sum((quantity * prices.get(symbol, Decimal("0")) for symbol, quantity in positions.items()), Decimal("0"))
        calculated_unrealized = market_value - sum(cost_basis.values(), Decimal("0"))
        calculated_nav = cash + market_value
        nav = recorded_nav if recorded_nav is not None else calculated_nav
        unrealized = recorded_unrealized if recorded_unrealized is not None else calculated_unrealized
        return PortfolioState(
            cash,
            MappingProxyType(dict(positions)),
            nav,
            realized,
            unrealized,
            MappingProxyType(prices),
        )
