# ADR-002 — Strategies generate TradeIntent

## Decision

Strategies consume immutable feature snapshots and may emit only an immutable `TradeIntent`.

## Context

Alpha logic must remain explainable and isolated from portfolio mutation, risk authorization and execution.

## Alternatives considered

- Strategy creates an order directly.
- Signal changes a position directly.
- Strategy emits a declarative intent.

## Chosen solution

Every baseline strategy maps named features to `TradeIntent` with identity, score, expected alpha, horizon, desired quantity, urgency and reason codes.

## Reason

The intent boundary makes strategy output auditable and allows portfolio and risk layers to independently resize or reject it.

## Consequences

Strategies cannot guarantee execution. Four simple baselines exist; ML and portfolio optimization remain outside 0.1-B.

## Date

2026-08-21

## Related version

WEALTH OS 0.1, iteration 0.1-B
