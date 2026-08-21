from datetime import datetime
from decimal import Decimal

import pytest

from wealth_os.execution import ExecutionConfig, ExecutionOutcome, ExecutionSimulator, Quote
from wealth_os.intents import Side, make_trade_intent
from wealth_os.orders import OrderFactory, OrderStatus, OrderType
from wealth_os.policy import PortfolioRequest
from wealth_os.risk import DrawdownState, DrawdownThresholds, GlobalRiskEngine, RiskAssessment, RiskContext, RiskDecision, RiskLimits


NOW = datetime.fromisoformat("2024-01-02T10:00:00+00:00")


def request(qty: str = "10", price: str = "100") -> PortfolioRequest:
    intent = make_trade_intent(strategy_id="test", strategy_version="1", timestamp=NOW, symbol="AAPL", side=Side.BUY, signal_score=Decimal("1"), expected_alpha=Decimal("0.01"), horizon="5m", desired_qty=Decimal(qty), urgency=Decimal("0.5"), reason_codes=("test",))
    return PortfolioRequest(intent, Decimal(qty), Decimal("0"), Decimal(price))


def limits(max_order: str = "5000") -> RiskLimits:
    return RiskLimits(Decimal("0.20"), Decimal("1.0"), Decimal("0.50"), Decimal(max_order), Decimal("1000"), Decimal("0.20"), Decimal("100000"), DrawdownThresholds(Decimal("0.05"), Decimal("0.10"), Decimal("0.20")))


def context(**changes) -> RiskContext:
    values = dict(nav=Decimal("100000"), gross_exposure=Decimal("0"), net_exposure=Decimal("0"), daily_pnl=Decimal("0"), drawdown=Decimal("0"), turnover=Decimal("0"))
    values.update(changes)
    return RiskContext(**values)


def test_risk_engine_pass_resize_reject_and_halt() -> None:
    assert GlobalRiskEngine(limits()).assess(request(), context()).decision is RiskDecision.PASS
    resized = GlobalRiskEngine(limits("500")).assess(request(), context())
    assert resized.decision is RiskDecision.RESIZE and resized.approved_qty == Decimal("5")
    rejected = GlobalRiskEngine(limits()).assess(request(), context(gross_exposure=Decimal("100000")))
    assert rejected.decision is RiskDecision.REJECT
    halted = GlobalRiskEngine(limits()).assess(request(), context(daily_pnl=Decimal("-1000")))
    assert halted.decision is RiskDecision.HALT and halted.drawdown_state is DrawdownState.HALT


def test_drawdown_state_machine_thresholds_are_configurable() -> None:
    engine = GlobalRiskEngine(limits())
    assert engine.drawdown_state(Decimal("0.01")) is DrawdownState.NORMAL
    assert engine.drawdown_state(Decimal("0.05")) is DrawdownState.CAUTION
    assert engine.drawdown_state(Decimal("0.10")) is DrawdownState.DEFENSIVE
    assert engine.drawdown_state(Decimal("0.20")) is DrawdownState.HALT


def test_order_creation_cannot_bypass_risk_engine() -> None:
    rejected = RiskAssessment(RiskDecision.REJECT, Decimal("0"), DrawdownState.NORMAL, ("test",))
    with pytest.raises(PermissionError):
        OrderFactory.create(request(), rejected)
    forged_pass = RiskAssessment(RiskDecision.PASS, Decimal("10"), DrawdownState.NORMAL, ("forged",))
    with pytest.raises(PermissionError):
        OrderFactory.create(request(), forged_pass)


def test_execution_lifecycle_partial_fill_and_fill_invariant() -> None:
    assessment = GlobalRiskEngine(limits()).assess(request(), context())
    order = OrderFactory.create(request(), assessment)
    simulator = ExecutionSimulator(ExecutionConfig(Decimal("1"), 10, Decimal("0.01")))
    result = simulator.execute(order, Quote(NOW, "AAPL", Decimal("99.9"), Decimal("100.1"), Decimal("4"), Decimal("4")))
    assert result.outcome is ExecutionOutcome.PARTIAL
    assert result.order.status is OrderStatus.PARTIALLY_FILLED
    assert result.fill is not None and result.fill.qty <= order.qty


def test_limit_order_can_remain_open_then_be_cancelled() -> None:
    assessment = GlobalRiskEngine(limits()).assess(request(), context())
    order = OrderFactory.create(request(), assessment, OrderType.LIMIT, Decimal("99"))
    simulator = ExecutionSimulator(ExecutionConfig(Decimal("0"), 0, Decimal("0")))
    result = simulator.execute(order, Quote(NOW, "AAPL", Decimal("99.9"), Decimal("100.1"), Decimal("10"), Decimal("10")))
    assert result.outcome is ExecutionOutcome.OPEN
    assert simulator.cancel(result.order).status is OrderStatus.CANCELLED
    assert simulator.expire(result.order).status is OrderStatus.EXPIRED


def test_execution_rejects_symbol_mismatch() -> None:
    assessment = GlobalRiskEngine(limits()).assess(request(), context())
    order = OrderFactory.create(request(), assessment)
    simulator = ExecutionSimulator(ExecutionConfig(Decimal("0"), 0, Decimal("0")))
    result = simulator.execute(order, Quote(NOW, "MSFT", Decimal("99"), Decimal("100"), Decimal("10"), Decimal("10")))
    assert result.outcome is ExecutionOutcome.REJECTED
    assert result.order.status is OrderStatus.REJECTED
