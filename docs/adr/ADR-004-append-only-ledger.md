# ADR-004 — Append-only ledger

## Decision

Financial changes are immutable ledger entries; portfolio state is a replaceable projection reconstructed from ledger history.

## Context

Cash, positions and P&L must be auditable and reproducible. Mutable portfolio fields alone cannot explain how a state was reached.

## Alternatives considered

- Store only the latest mutable portfolio state.
- Periodic snapshots without a complete history.
- Append-only entries plus derived projections.

## Chosen solution

Expose ledger history as an immutable tuple and permit only chronologically ordered appends with unique deterministic IDs.

## Reason

Complete history provides an audit trail and deterministic reconstruction with minimal machinery.

## Consequences

Corrections require compensating entries rather than edits. Durable storage and snapshot acceleration remain future work.

## Date

2026-08-20

## Related version

WEALTH OS 0.1, iteration 0.1-A
