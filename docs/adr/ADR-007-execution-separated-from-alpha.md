# ADR-007 — Execution separated from alpha

## Decision

Keep strategy alpha, risk authorization, order lifecycle, execution simulation and fill settlement as separate deterministic components.

## Context

Execution assumptions must not leak into signals, and an order must never mutate a position directly.

## Alternatives considered

- Strategies simulate their own fills.
- Orders directly update positions.
- Execution emits fills which settle through the ledger.

## Chosen solution

Execution handles market/limit rules, quotes, spread, deterministic slippage, latency, liquidity, partial fills, rejection and cancellation. Only `FillSettlement` writes financial changes to the append-only ledger.

## Reason

This preserves the invariant `Order → Execution → Fill → Ledger → Position` and makes execution assumptions independently testable.

## Consequences

The baseline has no L2/L3 queue, market impact, adverse selection or broker integration.

## Date

2026-08-21

## Related version

WEALTH OS 0.1, iteration 0.1-B
