from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .clock import ReplayClock
from .observation_api import ObservationApi
from .replay_controller import ReplayController
from .real_data_demo import build_real_run


def current_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "uncommitted"


def build_observation_timeline(code_commit: str | None = None) -> dict:
    result, dataset, config_snapshot, quality, manifest = build_real_run(code_commit or current_commit())
    controller = ReplayController(
        dataset.events,
        ReplayClock(dataset.events[0].timestamp, dataset.events[-1].timestamp),
    )
    snapshots = []
    for index in range(len(dataset.events)):
        if index:
            controller.next_event()
        snapshot = ObservationApi.build(result, dataset, controller.state(), config_snapshot).as_dict()
        # The UI needs the current audit window, not duplicated full-run history in every frame.
        snapshot["ledger"] = snapshot["ledger"][-10:]
        snapshot["decisions"] = snapshot["decisions"][-1:]
        snapshots.append(snapshot)
    return {
        "schema_version": 2,
        "source": "wealth_os.observation_api.ObservationApi",
        "dataset": manifest,
        "data_quality": quality.__dict__ if hasattr(quality, "__dict__") else {
            "row_count": quality.row_count, "duplicate_count": quality.duplicate_count,
            "missing_bar_count": quality.missing_bar_count, "passed": quality.passed,
        },
        "snapshots": snapshots,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    destination = root / "ui" / "app" / "run-data.json"
    destination.write_text(
        json.dumps(build_observation_timeline(), separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(destination)


if __name__ == "__main__":
    main()
