# ADR-001 — Event-driven architecture

## Decision

Use explicit, versionable typed events and synchronous in-process dispatch for 0.1-A.

## Context

The future closed loop needs auditable hand-offs between market data, portfolio, risk, execution and monitoring. In 0.1-A only market, system and timer contracts are required.

## Alternatives considered

- Direct calls between every component.
- Asynchronous queues or a message broker.
- Synchronous in-process event dispatch.

## Chosen solution

Immutable typed events flow through a deterministic bus. Subscribers execute serially in registration order.

## Reason

This is the smallest design that preserves explicit boundaries, testability and deterministic ordering.

## Consequences

Slow subscribers block dispatch. This is deliberate for correctness in 0.1-A; concurrency can be introduced behind the contract only when ordering semantics are defined.

## Date

2026-08-20

## Related version

WEALTH OS 0.1, iteration 0.1-A
