# WEALTH OS

WEALTH OS is being built toward version 0.1: a closed-loop inside trading system. **0.1-A — Foundation & State** is complete; the current development iteration is **0.1-B — Trading Core**. These are development labels, not separate product releases.

## Status

**0.1-A — Foundation & State: complete.** It supplies deterministic replay, event ordering, versioned datasets, append-only ledger and reconstructable state.

**0.1-B — Trading Core: implemented on the current development branch.** It adds the first closed, deterministic decision and execution loop.

## Trading Core flow

```text
MarketEvent → Feature Engine → Strategy → TradeIntent
→ Portfolio Policy → Global Risk Engine → Order
→ Execution → Fill → Ledger → Portfolio State
```

A `TradeIntent` is a strategy's requested action, not an order. It records why, how strongly, in which direction and over what horizon the strategy wants exposure. Portfolio Policy translates that request using current NAV. Global Risk Engine is mandatory and can pass, resize, reject or halt it. Only a risk-authorized order reaches execution, and only a fill can create financial ledger changes and therefore change a position.

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

## Run the 0.1-B Trading Core demo

```bash
python -m wealth_os.trading_demo
```

This uses a synthetic, explicitly labelled fixture to show actual feature, Momentum intent, risk, order, partial/full fill, ledger and reconstructed portfolio flow. It does not manufacture a target profit.

## Project map

- `src/wealth_os/` — configuration, event, replay, data, ledger, portfolio and runtime code;
- `data/fixtures/` — synthetic test-only OHLCV input;
- `tests/` — invariants and reproducibility contract;
- `docs/adr/` — architecture decision records.

The four direction-setting project documents named in the briefs were not present in the initially empty repository. When they are added, they belong under `docs/` and remain authoritative over implementation choices. Any conflict should be documented as a proposed deviation rather than silently changing those documents.

## Current boundaries

0.1-B contains four transparent baseline strategies: Momentum, Mean Reversion, VWAP Reversion and Residual Reversal. It has no final UI, dashboards, ML, Regime Engine, Meta Allocator, Portfolio Optimizer, live or paper broker, real capital, L2/L3 market twin, queue model, impact model, TCA, cloud deployment or 0.1-C functionality. Execution and ledger persistence are in-memory baselines.
