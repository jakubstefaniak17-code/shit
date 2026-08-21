# WEALTH OS

WEALTH OS is being built toward version 0.1: a closed-loop inside trading system. The current development iteration is **0.1-A — Foundation & State**, not a separate product release.

## What 0.1-A implements

The current flow is:

```text
versioned OHLCV dataset
        ↓
deterministic ReplayClock
        ↓
typed MarketEvent
        ↓
synchronous Event Bus
        ↓
Portfolio State projection
        ↑
append-only Ledger
```

Implemented components:

- immutable, snapshotable runtime configuration and stable configuration hash;
- typed, explicitly schema-versioned `MarketEvent`, `SystemEvent` and `TimerEvent` contracts;
- logical ReplayClock with play, pause, step and speed-control API;
- deterministic Event Bus with explicit ordering and subscriptions;
- validated OHLCV CSV loader and point-in-time dataset metadata/content hash;
- clearly labelled synthetic fixture used only for runtime tests;
- append-only financial ledger and reconstructable Portfolio State;
- deterministic run metadata: run ID, dataset ID, config hash, code commit, seed and logical start time;
- automated invariant and reproducibility tests.

## Current boundaries

There are no strategies, signals, feature engine, ML, risk engine, orders, fills, execution simulation, broker integration, live/paper trading, L2/L3 market twin or application UI. The fixture is synthetic and is **not market data**. Persistence is currently in memory.

## Requirements and setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e . pytest
```

## Run tests

```bash
python -m pytest
```

## Run the minimal replay demo

From the repository root:

```bash
python -m wealth_os.demo
```

The demo replays the labelled fixture, emits no trades, and ends with unchanged starting cash and no positions.

## Project map

- `src/wealth_os/` — configuration, event, replay, data, ledger, portfolio and runtime code;
- `data/fixtures/` — synthetic test-only OHLCV input;
- `tests/` — invariants and reproducibility contract;
- `docs/adr/` — architecture decision records.

The four direction-setting project documents named in the 0.1-A brief were not present in the initially empty repository. When they are added, they belong under `docs/` and remain authoritative over implementation choices. Any conflict should be documented as a proposed deviation rather than silently changing those documents.
