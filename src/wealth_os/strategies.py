from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .features import FeatureSnapshot
from .intents import Side, TradeIntent, make_trade_intent


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    entry_threshold: Decimal = Decimal("0.001")
    desired_qty: Decimal = Decimal("10")
    urgency: Decimal = Decimal("0.5")
    horizon: str = "15m"
    symbols: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.entry_threshold < 0 or self.desired_qty <= 0:
            raise ValueError("Strategy threshold must be non-negative and desired_qty positive")
        if not Decimal("0") <= self.urgency <= Decimal("1"):
            raise ValueError("Strategy urgency must be between 0 and 1")


class BaselineStrategy:
    strategy_id = "baseline"
    strategy_version = "1.0"
    feature_name = "return_1m"
    reverse = False

    def __init__(self, config: StrategyConfig = StrategyConfig()) -> None:
        self.config = config

    def evaluate(self, features: FeatureSnapshot) -> TradeIntent | None:
        if self.config.symbols and features.symbol not in self.config.symbols:
            return None
        value = getattr(features, self.feature_name)
        if value is None or abs(value) < self.config.entry_threshold:
            return None
        direction = -value if self.reverse else value
        side = Side.BUY if direction > 0 else Side.SELL
        return make_trade_intent(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            timestamp=features.timestamp,
            symbol=features.symbol,
            side=side,
            signal_score=direction,
            expected_alpha=abs(value),
            horizon=self.config.horizon,
            desired_qty=self.config.desired_qty,
            urgency=self.config.urgency,
            reason_codes=(f"{self.feature_name}_threshold",),
        )


class MomentumStrategy(BaselineStrategy):
    strategy_id = "momentum"
    feature_name = "return_5m"


class MeanReversionStrategy(BaselineStrategy):
    strategy_id = "mean_reversion"
    feature_name = "return_5m"
    reverse = True


class VwapReversionStrategy(BaselineStrategy):
    strategy_id = "vwap_reversion"
    feature_name = "vwap_distance"
    reverse = True


class ResidualReversalStrategy(BaselineStrategy):
    strategy_id = "residual_reversal"
    feature_name = "residual_return"
    reverse = True
