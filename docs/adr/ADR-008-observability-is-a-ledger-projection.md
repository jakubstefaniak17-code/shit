# ADR-008 — Observability is a ledger projection

## Decision

Metrics, equity history, portfolio views and audit traces are deterministic projections of run events and the append-only ledger. The UI never owns financial state.

## Context

0.1-C must make the trading loop understandable without creating a second source of truth or presenting weak statistics as facts.

## Alternatives considered

- Let the frontend calculate and store portfolio values.
- Maintain a separate monitoring database with independent financial state.
- Build read-only observation models from the runtime and ledger.

## Chosen solution

Python observation services construct equity points, metrics, explainability, SIMPLE/ADVANCED decision representations and a complete `DecisionTrace`. The frontend consumes a deterministic snapshot and labels every value as FACT, ESTIMATE, ASSUMPTION, UNCERTAINTY or INSUFFICIENT DATA.

## Reason

One financial source of truth keeps monitoring auditable and prevents display logic from silently changing results.

## Consequences

UI refreshes must originate from a new runtime snapshot. Small fixtures intentionally show unavailable metrics instead of fabricated precision.

## Date

2026-08-21

## Related version

WEALTH OS 0.1, iteration 0.1-C
