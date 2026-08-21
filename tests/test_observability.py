from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import json

from wealth_os.clock import ReplayClock
from wealth_os.ledger import LedgerEntryType, make_ledger_entry
from wealth_os.observability import AuditTrailBuilder, EquityCurveBuilder, EvidenceStatus, MetricsCalculator
from wealth_os.observation_api import ObservationApi
from wealth_os.observation_export import build_observation_timeline
from wealth_os.replay_controller import ReplayController

from test_features_strategies import trading_dataset
from test_settlement_runtime import runtime_result


START = datetime.fromisoformat("2024-01-02T09:30:00+00:00")


def metric_ledger():
    return (
        make_ledger_entry(entry_type=LedgerEntryType.DEPOSIT, timestamp=START, sequence=0, amount=Decimal("100")),
        make_ledger_entry(entry_type=LedgerEntryType.NAV, timestamp=START + timedelta(minutes=1), sequence=1, amount=Decimal("120")),
        make_ledger_entry(entry_type=LedgerEntryType.FEE, timestamp=START + timedelta(minutes=2), sequence=2, amount=Decimal("2")),
        make_ledger_entry(entry_type=LedgerEntryType.NAV, timestamp=START + timedelta(minutes=2), sequence=3, amount=Decimal("90")),
        make_ledger_entry(entry_type=LedgerEntryType.NAV, timestamp=START + timedelta(minutes=3), sequence=4, amount=Decimal("110")),
    )


def test_metrics_are_deterministic_ledger_based_and_honest_about_sample_size() -> None:
    entries = metric_ledger()
    curve = EquityCurveBuilder.build(entries)
    first = MetricsCalculator.calculate(entries, curve)
    second = MetricsCalculator.calculate(entries, curve)
    assert first == second
    assert first.gross_pnl.value - first.execution_costs.value == first.net_pnl.value
    assert first.maximum_drawdown.value == Decimal("0.25")
    assert first.cagr.status is EvidenceStatus.INSUFFICIENT_DATA
    assert first.sharpe.status is EvidenceStatus.INSUFFICIENT_DATA
    assert first.win_rate.status is EvidenceStatus.INSUFFICIENT_DATA
    assert all(metric.value is None or metric.value.is_finite() for metric in (first.total_return, first.maximum_drawdown, first.turnover))


def test_equity_curve_reconstructs_required_fields_and_drawdown() -> None:
    curve = EquityCurveBuilder.build(metric_ledger())
    assert [point.nav for point in curve] == [Decimal("100"), Decimal("120"), Decimal("90"), Decimal("110")]
    assert curve[2].drawdown == Decimal("0.25")
    assert all(point.cash + point.positions_value == point.nav or point.nav in {Decimal("120"), Decimal("90"), Decimal("110")} for point in curve)


def test_every_fill_has_complete_non_orphaned_decision_trace() -> None:
    result = runtime_result()
    dataset = trading_dataset()
    traces = AuditTrailBuilder.build(result, dataset)
    assert len(traces) == len(result.fills)
    assert all(trace.order.intent_id == trace.intent.intent_id for trace in traces)
    assert all(trace.fill.order_id == trace.order.order_id for trace in traces)
    assert all(trace.ledger_entries for trace in traces)
    assert all(any(entry.description == trace.fill.fill_id for entry in trace.ledger_entries) for trace in traces)
    assert all(trace.explanation.key_features and trace.explanation.evidence_status is EvidenceStatus.FACT for trace in traces)


def test_replay_controller_supports_play_pause_step_previous_next_and_speed() -> None:
    events = trading_dataset().events
    controller = ReplayController(events, ReplayClock(events[0].timestamp, events[-1].timestamp))
    assert controller.play().status == "RUNNING"
    assert controller.pause().status == "PAUSED"
    assert controller.next_event().event_index == 1
    assert controller.previous_event().event_index == 0
    assert controller.step().event_index == 1
    assert controller.set_speed("100x").speed == "100x"


def test_observation_api_agrees_with_runtime_ledger_and_is_reproducible() -> None:
    dataset = trading_dataset()
    result = runtime_result()
    controller = ReplayController(dataset.events, ReplayClock(dataset.events[0].timestamp, dataset.events[-1].timestamp))
    while controller.state().event_index < len(dataset.events) - 1:
        controller.next_event()
    snapshot_one = ObservationApi.build(result, dataset, controller.state(), {"seed": 42})
    snapshot_two = ObservationApi.build(runtime_result(), dataset, controller.state(), {"seed": 42})
    assert snapshot_one == snapshot_two
    assert Decimal(snapshot_one.portfolio["cash"]) == result.portfolio.cash
    assert snapshot_one.run["ledger_entry_count"] == len(result.ledger_entries)
    assert snapshot_one.decisions[0].advanced.fill == result.fills[0]
    assert snapshot_one.decisions[0].simple.why == snapshot_one.decisions[0].advanced.explanation.human_readable_explanation


def test_observation_api_projects_only_state_visible_at_replay_cursor() -> None:
    dataset = trading_dataset()
    result = runtime_result()
    controller = ReplayController(dataset.events, ReplayClock(dataset.events[0].timestamp, dataset.events[-1].timestamp))
    start = ObservationApi.build(result, dataset, controller.state(), {"seed": 42})
    assert start.portfolio["positions"] == {}
    assert len(start.ledger) == 1
    while controller.state().event_index < len(dataset.events) - 1:
        controller.next_event()
    end = ObservationApi.build(result, dataset, controller.state(), {"seed": 42})
    assert end.portfolio["positions"] == {symbol: str(quantity) for symbol, quantity in result.portfolio.positions.items()}
    assert len(end.ledger) == len(result.ledger_entries)


def test_observation_projection_respects_same_timestamp_sequence_and_fill_latency() -> None:
    dataset = trading_dataset()
    result = runtime_result()
    controller = ReplayController(dataset.events, ReplayClock(dataset.events[0].timestamp, dataset.events[-1].timestamp))
    while controller.state().event_index < 14:
        controller.next_event()
    before = ObservationApi.build(result, dataset, controller.state(), {"seed": 42})
    assert before.market["event"]["sequence"] == 14
    assert before.portfolio["positions"] == {}
    assert not before.decisions
    assert all(entry["entry_type"] != "fill" for entry in before.ledger)

    controller.next_event()
    after = ObservationApi.build(result, dataset, controller.state(), {"seed": 42})
    assert after.market["event"]["sequence"] == 15
    assert after.portfolio["positions"] == {"AAPL": "5"}
    assert after.decisions
    fill = after.decisions[0].advanced.fill
    assert fill.timestamp > after.decisions[0].advanced.market_event.timestamp
    assert any(entry["entry_type"] == "fill" for entry in after.ledger)


def test_ui_fixture_values_match_runtime_and_ledger_source_of_truth() -> None:
    result = runtime_result()
    path = Path(__file__).parents[1] / "ui" / "app" / "run-data.json"
    ui_data = json.loads(path.read_text(encoding="utf-8"))
    commit = ui_data["snapshots"][-1]["run"]["code_commit"]
    assert ui_data == build_observation_timeline(commit)
    final = ui_data["snapshots"][-1]
    assert final["portfolio"]["cash"] == str(result.portfolio.cash)
    assert final["portfolio"]["nav"] == str(result.portfolio.nav)
    assert final["portfolio"]["unrealized_pnl"] == str(result.portfolio.unrealized_pnl)
    assert final["metrics"]["trade_count"]["value"] == len(result.fills)
