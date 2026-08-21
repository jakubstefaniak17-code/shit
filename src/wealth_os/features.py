from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .events import MarketEvent


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    timestamp: datetime
    symbol: str
    return_1m: Decimal | None
    return_5m: Decimal | None
    return_15m: Decimal | None
    return_1d: Decimal | None
    rolling_volatility: Decimal | None
    vwap_distance: Decimal | None
    relative_volume: Decimal | None
    volume_zscore: Decimal | None
    market_relative_return: Decimal | None
    sector_relative_return: Decimal | None
    rolling_beta: Decimal | None
    residual_return: Decimal | None


@dataclass(frozen=True, slots=True)
class FeatureConfig:
    volatility_window: int = 15
    volume_window: int = 15
    beta_window: int = 15
    bars_per_day: int = 390
    market_symbol: str = "SPY"
    sector_by_symbol: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if min(self.volatility_window, self.volume_window, self.beta_window, self.bars_per_day) <= 0:
            raise ValueError("Feature windows must be positive")


def _return(prices: deque[Decimal], periods: int) -> Decimal | None:
    if len(prices) <= periods or prices[-periods - 1] == 0:
        return None
    return prices[-1] / prices[-periods - 1] - Decimal("1")


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _variance(values: list[Decimal]) -> Decimal | None:
    if len(values) < 2:
        return None
    mean = _mean(values)
    return sum(((value - mean) ** 2 for value in values), Decimal("0")) / Decimal(len(values))


class FeatureEngine:
    """Point-in-time feature calculator; update sees only the current and prior events."""

    def __init__(self, config: FeatureConfig = FeatureConfig()) -> None:
        self.config = config
        capacity = max(16, config.bars_per_day + 1, config.volatility_window + 1, config.volume_window + 1, config.beta_window + 1)
        self._prices: dict[str, deque[Decimal]] = defaultdict(lambda: deque(maxlen=capacity))
        self._volumes: dict[str, deque[Decimal]] = defaultdict(lambda: deque(maxlen=config.volume_window))
        self._returns: dict[str, deque[Decimal]] = defaultdict(lambda: deque(maxlen=config.beta_window))
        self._cumulative_value: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        self._cumulative_volume: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        self._latest_1m: dict[str, Decimal] = {}
        self._last_timestamp: datetime | None = None
        self._sector_by_symbol = dict(config.sector_by_symbol)

    def update(self, event: MarketEvent) -> FeatureSnapshot:
        if self._last_timestamp is not None and event.timestamp < self._last_timestamp:
            raise ValueError("FeatureEngine cannot consume future data out of order")
        self._last_timestamp = event.timestamp
        symbol = event.data.symbol
        prices = self._prices[symbol]
        previous_close = prices[-1] if prices else None
        prices.append(event.data.close)
        one_minute = None if previous_close in {None, Decimal("0")} else event.data.close / previous_close - Decimal("1")
        if one_minute is not None:
            self._returns[symbol].append(one_minute)
            self._latest_1m[symbol] = one_minute

        prior_volumes = list(self._volumes[symbol])
        self._volumes[symbol].append(event.data.volume)
        typical = (event.data.high + event.data.low + event.data.close) / Decimal("3")
        self._cumulative_value[symbol] += typical * event.data.volume
        self._cumulative_volume[symbol] += event.data.volume
        vwap = self._cumulative_value[symbol] / self._cumulative_volume[symbol] if self._cumulative_volume[symbol] else None

        volume_mean = _mean(prior_volumes) if prior_volumes else None
        volume_variance = _variance(prior_volumes)
        volume_std = volume_variance.sqrt() if volume_variance is not None and volume_variance > 0 else None
        return_variance = _variance(list(self._returns[symbol]))
        volatility = return_variance.sqrt() if return_variance is not None else None

        market_return = self._latest_1m.get(self.config.market_symbol)
        sector_return = self._latest_1m.get(self._sector_by_symbol.get(symbol, ""))
        market_relative = one_minute - market_return if one_minute is not None and market_return is not None and symbol != self.config.market_symbol else None
        sector_relative = one_minute - sector_return if one_minute is not None and sector_return is not None else None

        asset_returns = list(self._returns[symbol])
        market_returns = list(self._returns[self.config.market_symbol])
        paired = min(len(asset_returns), len(market_returns), self.config.beta_window)
        beta = None
        if paired >= 2 and symbol != self.config.market_symbol:
            xs, ys = market_returns[-paired:], asset_returns[-paired:]
            x_mean, y_mean = _mean(xs), _mean(ys)
            market_var = sum(((x - x_mean) ** 2 for x in xs), Decimal("0"))
            if market_var != 0:
                beta = sum(((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)), Decimal("0")) / market_var
        residual = one_minute - beta * market_return if one_minute is not None and beta is not None and market_return is not None else None

        return FeatureSnapshot(
            event.timestamp,
            symbol,
            one_minute,
            _return(prices, 5),
            _return(prices, 15),
            _return(prices, self.config.bars_per_day),
            volatility,
            event.data.close / vwap - Decimal("1") if vwap else None,
            event.data.volume / volume_mean if volume_mean else None,
            (event.data.volume - volume_mean) / volume_std if volume_mean is not None and volume_std else None,
            market_relative,
            sector_relative,
            beta,
            residual,
        )
