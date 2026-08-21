# ADR-005 — Deterministic replay

## Decision

Drive backtest logic exclusively with timezone-aware dataset timestamps and strictly ordered sequence numbers.

## Context

Research results must be repeatable. Wall-clock time, accidental concurrency and ambiguous ordering would make identical inputs produce different outputs.

## Alternatives considered

- Wall-clock scheduling.
- Concurrent event processing.
- A logical replay clock with synchronous dispatch.

## Chosen solution

ReplayClock advances only to event timestamps, never backwards. EventBus accepts a strictly increasing `(timestamp, sequence)` key.

## Reason

Logical time makes replay independent of machine speed and execution date.

## Consequences

Current play, pause, step and speed APIs describe control state; speed does not sleep or alter logical outcomes. UI scheduling is outside 0.1-A.

## Date

2026-08-20

## Related version

WEALTH OS 0.1, iteration 0.1-A
