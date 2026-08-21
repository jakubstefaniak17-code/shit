from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .bus import DeterministicEventBus
from .clock import ReplayClock
from .config import RuntimeConfig
from .data import MarketDataset
from .execution import ExecutionConfig, ExecutionResult, ExecutionSimulator, Fill, Quote
from .features import FeatureConfig, FeatureEngine, FeatureSnapshot
from .intents import TradeIntent
from .ledger import AppendOnlyLedger, LedgerEntryType, make_ledger_entry
from .orders import Order, OrderFactory, OrderType
from .policy import PortfolioPolicy, PortfolioPolicyConfig, PortfolioRequest
from .portfolio import PortfolioProjector, PortfolioState
from .risk import GlobalRiskEngine, RiskAssessment, RiskContext, RiskLimits
from .runtime import RunMetadata
from .serialization import stable_hash
from .settlement import FillSettlement
from .strategies import BaselineStrategy


@dataclass(frozen=True, slots=True)
class TradingRuntimeConfig:
    spread_bps: Decimal
    displayed_liquidity: Decimal
    execution: ExecutionConfig
    risk_limits: RiskLimits
    portfolio_policy: PortfolioPolicyConfig = PortfolioPolicyConfig()

    def __post_init__(self) -> None:
        if self.spread_bps < 0 or self.displayed_liquidity < 0:
            raise ValueError("Spread and displayed liquidity must be non-negative")


@dataclass(frozen=True, slots=True)
class TradingRunResult:
    metadata: RunMetadata
    features: tuple[FeatureSnapshot, ...]
    intents: tuple[TradeIntent, ...]
    requests: tuple[PortfolioRequest, ...]
    assessments: tuple[RiskAssessment, ...]
    orders: tuple[Order, ...]
    executions: tuple[ExecutionResult, ...]
    fills: tuple[Fill, ...]
    ledger_entry_ids: tuple[str, ...]
    portfolio: PortfolioState

    @property
    def result_hash(self) -> str:
        return stable_hash(self)


class TradingRuntime:
    def __init__(self, config: RuntimeConfig, trading_config: TradingRuntimeConfig, dataset: MarketDataset, code_commit: str, strategy: BaselineStrategy, feature_config: FeatureConfig = FeatureConfig()) -> None:
        if config.dataset_id != dataset.metadata.dataset_id:
            raise ValueError("Configured dataset_id does not match loaded dataset")
        self.config = config
        self.trading_config = trading_config
        self.dataset = dataset
        self.code_commit = code_commit
        self.strategy = strategy
        self.feature_config = feature_config

    def run(self) -> TradingRunResult:
        combined_config_hash = stable_hash({
            "runtime": self.config.snapshot(),
            "trading": self.trading_config,
            "features": self.feature_config,
            "strategy_id": self.strategy.strategy_id,
            "strategy_version": self.strategy.strategy_version,
            "strategy_config": self.strategy.config,
        })
        identity = {"dataset_id": self.dataset.metadata.dataset_id, "dataset_hash": self.dataset.metadata.hash, "config_hash": combined_config_hash, "code_commit": self.code_commit, "seed": self.config.seed}
        metadata = RunMetadata(stable_hash(identity)[:24], self.dataset.metadata.dataset_id, combined_config_hash, self.code_commit, self.config.seed, self.config.replay_start)
        clock = ReplayClock(self.config.replay_start, self.config.replay_end)
        bus = DeterministicEventBus()
        features_engine = FeatureEngine(self.feature_config)
        risk_engine = GlobalRiskEngine(self.trading_config.risk_limits)
        execution = ExecutionSimulator(self.trading_config.execution)
        policy = PortfolioPolicy(self.trading_config.portfolio_policy)
        ledger = AppendOnlyLedger()
        ledger.append(make_ledger_entry(entry_type=LedgerEntryType.DEPOSIT, timestamp=self.config.replay_start, sequence=0, amount=self.config.starting_cash, description="Starting cash"))
        snapshots: list[FeatureSnapshot] = []
        intents: list[TradeIntent] = []
        requests: list[PortfolioRequest] = []
        assessments: list[RiskAssessment] = []
        orders: list[Order] = []
        executions: list[ExecutionResult] = []
        fills: list[Fill] = []
        last_prices: dict[str, Decimal] = {}
        turnover_notional = Decimal("0")

        def on_market(event) -> None:
            nonlocal turnover_notional
            snapshot = features_engine.update(event)
            snapshots.append(snapshot)
            last_prices[event.data.symbol] = event.data.close
            intent = self.strategy.evaluate(snapshot)
            if intent is None:
                return
            intents.append(intent)
            state = PortfolioProjector.reconstruct(ledger.entries, last_prices)
            request = policy.evaluate(intent, state, event.data.close)
            requests.append(request)
            gross = sum((abs(qty * last_prices.get(symbol, Decimal("0"))) for symbol, qty in state.positions.items()), Decimal("0"))
            net = sum((qty * last_prices.get(symbol, Decimal("0")) for symbol, qty in state.positions.items()), Decimal("0"))
            assessment = risk_engine.assess(request, RiskContext(state.nav, gross, net, state.realized_pnl, Decimal("0"), turnover_notional))
            assessments.append(assessment)
            if assessment.approved_qty == 0:
                return
            order = OrderFactory.create(request, assessment, OrderType.MARKET)
            ledger_sequence = ledger.entries[-1].sequence + 1
            ledger.append(make_ledger_entry(entry_type=LedgerEntryType.ORDER, timestamp=order.timestamp, sequence=ledger_sequence, symbol=order.symbol, quantity=assessment.approved_qty, description=order.order_id))
            quote_spread = event.data.close * self.trading_config.spread_bps / Decimal("20000")
            quote = Quote(event.timestamp, event.data.symbol, event.data.close - quote_spread, event.data.close + quote_spread, self.trading_config.displayed_liquidity, self.trading_config.displayed_liquidity)
            result = execution.execute(order, quote)
            orders.append(result.order)
            executions.append(result)
            if result.fill is not None:
                fills.append(result.fill)
                turnover_notional += result.fill.qty * result.fill.price
                last_prices[result.fill.symbol] = result.fill.price
                FillSettlement.settle(result.fill, ledger, last_prices)

        bus.subscribe(on_market)
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
        return TradingRunResult(metadata, tuple(snapshots), tuple(intents), tuple(requests), tuple(assessments), tuple(orders), tuple(executions), tuple(fills), tuple(entry.entry_id for entry in ledger.entries), portfolio)
