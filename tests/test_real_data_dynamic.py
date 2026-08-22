from datetime import datetime
from decimal import Decimal
from pathlib import Path

from wealth_os.clock import ReplayClock
from wealth_os.market_data import load_real_dataset
from wealth_os.observation_api import ObservationApi
from wealth_os.observation_export import build_observation_timeline
from wealth_os.real_data_demo import build_real_run
from wealth_os.replay_controller import ReplayController


ROOT = Path(__file__).parents[1]


def test_real_dataset_is_canonical_versioned_and_quality_checked() -> None:
    dataset, report, manifest = load_real_dataset(ROOT)
    assert report.passed and report.duplicate_count == 0
    assert dataset.metadata.hash == manifest["content_hash"]
    assert dataset.metadata.frequency == "1 day"
    assert manifest["adjustment"] == "RAW"
    assert manifest["dataset_kind"] == "REAL HISTORICAL DATASET"
    assert all(event.timestamp.tzinfo is not None for event in dataset.events)
    assert all(event.data.high >= max(event.data.open, event.data.close) for event in dataset.events)
    assert all(event.data.low <= min(event.data.open, event.data.close) and event.data.volume >= 0 for event in dataset.events)


def test_real_research_run_and_gui_export_are_reproducible() -> None:
    first = build_real_run("same-commit")[0]
    second = build_real_run("same-commit")[0]
    assert first == second and first.result_hash == second.result_hash
    assert build_observation_timeline("same-commit") == build_observation_timeline("same-commit")


def test_dynamic_projection_changes_without_future_leakage_and_resets() -> None:
    result, dataset, config, _, _ = build_real_run("dynamic-test")
    controller = ReplayController(dataset.events, ReplayClock(dataset.events[0].timestamp, dataset.events[-1].timestamp))
    start = ObservationApi.build(result, dataset, controller.state(), config)
    assert start.replay.event_index == 0 and len(start.market["recent_events"]) == 1
    assert start.portfolio["positions"] == {} and not start.decisions
    start_price = start.market["event"]["data"]["close"]
    controller.play()
    for _ in range(18):
        controller.next_event()
    middle = ObservationApi.build(result, dataset, controller.state(), config)
    assert middle.market["event"]["data"]["close"] != start_price
    assert len(middle.market["recent_events"]) <= 10
    assert all(datetime.fromisoformat(row["timestamp"]) <= datetime.fromisoformat(middle.replay.timestamp) for row in middle.market["recent_events"])
    controller.reset()
    reset = ObservationApi.build(result, dataset, controller.state(), config)
    assert reset == start


def test_ui_contract_exposes_dynamic_controls_and_runtime_feed() -> None:
    page = (ROOT / "ui" / "app" / "page.tsx").read_text(encoding="utf-8")
    for text in ("RESET RUN", "AUTO PAUSE: FILL", "EVENT STREAM", "REAL HISTORICAL MARKET DATA", "Pipeline", "setInterval"):
        assert text in page
    assert "useState(0)" in page
