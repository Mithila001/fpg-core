# Feature Development Guide

This guide defines the stable shape of an `fpg-core` feature without forcing unrelated algorithms into the same internal design.

## Core rule

Be strict at feature boundaries and flexible inside the feature.

A CP-SAT solver, an Optuna search, a geometry processor, and a scoring engine do not need the same internal class hierarchy. Do not add a common `BaseFeature` only for visual consistency.

## Package boundaries

1. Each major capability lives in its own folder under `src/fpg_core/`.
2. Feature implementation is owned by that folder.
3. Cross-feature data should use canonical contracts from `fpg_core.domain`.
4. A feature must not import another feature's private implementation modules.
5. If one feature intentionally invokes another, use the other feature's public root/API only and keep that dependency explicit.
6. `fpg-core` must not import server, HTTP, persistence, database, worker, UI, artifact-path, or deployment code.
7. Shared domain types belong in `fpg_core.domain`; do not redefine equivalent feature-local models.

The architecture test enforces the private cross-feature import rule.

## Expected feature surface

A normal feature should expose a recognizable public boundary:

```text
feature_name/
|-- README.md
|-- __init__.py
|-- api.py
|-- exceptions.py
`-- implementation files as needed
```

Only add files such as `config.py`, `contracts.py`, `validation.py`, `pipeline.py`, `manager.py`, `runner.py`, `registry.py`, `profiles.py`, `evaluators/`, `processors/`, or `constraints/` when the feature actually needs them.

### Public imports

- Normal consumers import from `fpg_core.<feature>`.
- `api.py` owns/re-exports public operations.
- `__init__.py` defines the intentional supported surface through `__all__`.
- Internal helpers, solver models, pipelines, optimizers, processor implementations, and similar details are private unless deliberately exported.

## Inputs and configuration

Keep **what is being processed** separate from **how it is processed**.

Typical shape:

```python
FeatureInput(
    request=...,  # request/operation-specific data
    config=...,   # reusable algorithm policy
)
```

Equivalent typed forms are fine when they fit the feature better. Do not create generic `Settings`/`Options` bags mixing domain data and algorithm policy.

## Results and execution modes

`FeatureExecution[TResult, TDetails]` is the preferred completed-operation envelope when it fits the feature:

```text
FeatureExecution
|-- result: TResult
|-- details: TDetails | None
`-- metadata: ExecutionMetadata
```

- `PRODUCTION`: normal usable result, minimal diagnostic overhead, normally `details=None`.
- `DEBUG`: same primary result contract plus feature-specific diagnostics/R&D details.
- Do not force an existing feature into this envelope if its direct return is a deliberate public contract; document the exception instead.
- Debug structures may evolve faster than production result contracts, but they should remain typed when practical.

## Public-contract stability

Treat exported functions, classes, dataclasses, enums, exceptions, aliases, registry keys, profile names, and serialized enum values as package contracts.

Before intentionally changing one:

1. inspect callers and shared types;
2. update tests and affected flow tests;
3. update the consumer reference;
4. add a concise migration note when compatibility changes.

Prefer compatibility aliases only when they have a real migration purpose. Do not keep dead aliases indefinitely without reason.

## Extension points

Use `Protocol`, `ABC`, registries, or strategy interfaces only when implementations are genuinely interchangeable or consumers are intentionally allowed to extend the feature. Existing examples include evaluators, constraints, and processors.

Do not create speculative interfaces, factories, or base classes for a single implementation.

## Feature README

A feature README is a focused explanation, not the canonical complete package contract. Keep it useful for maintainers and local feature understanding. Consumer-visible exact contracts belong in `docs/PACKAGE_FEATURE_REFERENCE.md`.
