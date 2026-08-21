# ADR-006 — Dataset versioning

## Decision

Identify every dataset with explicit point-in-time metadata and a SHA-256 hash over canonical metadata plus raw rows.

## Context

Provider corrections, symbol coverage and adjustment policies can change historical data. A name alone is not sufficient to reproduce a run.

## Alternatives considered

- File name only.
- Provider and date range without content hashing.
- Explicit metadata plus deterministic content hash.

## Chosen solution

Validate required OHLCV fields, time order, duplicate keys, symbols and boundaries, then compute the dataset hash.

## Reason

This catches silent content changes while retaining human-readable dataset identity and provenance.

## Consequences

Any raw-row or metadata change produces a new hash. The fixture is labelled synthetic test data and must never be presented as observed market data.

## Date

2026-08-20

## Related version

WEALTH OS 0.1, iteration 0.1-A
