# ADR-003 — Risk Engine is authoritative

## Decision

An order can be created and executed only with an authorization capability emitted by Global Risk Engine.

## Context

A good signal can still violate position, exposure, loss, drawdown, turnover or order-size constraints.

## Alternatives considered

- Advisory risk warnings.
- Risk checks embedded separately in strategies.
- One mandatory Global Risk Engine gateway.

## Chosen solution

Risk produces PASS, RESIZE, REJECT or HALT. OrderFactory and ExecutionSimulator reject objects without the internal risk capability.

## Reason

One authoritative gateway prevents strategies and models from silently bypassing portfolio-wide limits.

## Consequences

Risk limits and drawdown thresholds are explicit configuration. Defensive states can reduce otherwise valid requests.

## Date

2026-08-21

## Related version

WEALTH OS 0.1, iteration 0.1-B
