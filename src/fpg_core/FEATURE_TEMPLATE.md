# FPG Core Feature Template

This template keeps features recognizable without forcing every algorithm into the same internal design.

## Architecture Rules

1. Every feature must live in its own folder under `src/fpg_core/`.
2. A feature owns its implementation and may organize internal files as needed.
3. Public operations must be exposed through the feature's `api.py`.
4. A feature must not import another feature's internal modules.
5. Cross-feature communication is allowed only through:
   - another feature's public `api.py`, when invoking that feature; or
   - canonical shared contracts from `fpg_core.domain`.
6. Shared types belong in `fpg_core.domain`. Do not duplicate shared domain models inside features.
7. Feature-specific input contracts, configuration, context objects, results, and R&D detail types stay inside that feature. Processing input and configuration must remain clearly distinguishable in the public contract.
8. `fpg_core.__init__` is for package metadata and carefully selected package-wide conveniences. Do not create a giant root `api.py`.
9. `fpg_core.config` is only for package-wide configuration aggregation and validation. Feature-only settings stay in the feature's `config.py`.
10. Preserve public APIs and serialized enum values unless a breaking change is intentional and documented.

## Required Files

```text
feature_name/
├── README.md
├── __init__.py
├── api.py
└── exceptions.py
```

`exceptions.py` may contain only a base exception when the feature has no specialized errors yet.

## Optional Files

Add only what the feature actually needs:

```text
config.py
contracts.py
context.py
domain.py
validation.py
pipeline.py
manager.py
runner.py
registry.py
profiles.py
geometry.py
processors/
evaluators/
constraints/
features/
```

Names such as `pipeline.py`, `manager.py`, and `runner.py` are not mandatory. Use the name that best describes the responsibility.

## Public API Rules

- `api.py` should contain or re-export the supported feature operations.
- `__init__.py` may provide convenient public re-exports, but must not expose private implementation helpers.
- Callers should not import modules such as `pipeline`, `manager`, `optimizer`, `model`, or processor implementations directly.
- Extension registries and profiles may be public when customization is an intended contract.

## Input and Output Contract

Every feature API should support normal production use and optional debug/R&D execution without separate APIs.

```python
FeatureExecution[TResult, TDetails]
├── result: TResult
├── details: TDetails | None
└── metadata: ExecutionMetadata
```

### Inputs

- Accept the required domain input.
- Accept typed feature configuration when customization is needed.
- Accept a shared `ExecutionMode` instead of feature-specific debug booleans:
  - `PRODUCTION`: return the final result with minimal overhead.
  - `DEBUG`: collect feature-specific analysis, visualization, and diagnostic data for debugging and R&D.
- Optional inputs such as seeds, profiles, limits, and callbacks should be explicit and typed.
- Do not force every feature to accept inputs it does not need.

#### Input vs Configuration Separation

Feature APIs must clearly distinguish **processing input** from **configuration**.

- **Processing input** is data describing the specific operation being processed, such as a candidate map, floor plan, land geometry, room requirements, prepared grid, or other request-specific domain data.
- **Configuration** controls how the feature performs that operation, such as thresholds, weights, costs, limits, profiles, routing policies, search settings, tolerances, and algorithm options.
- Do not place processing data and configuration fields together inside a generically named `Settings`, `Options`, or similar object.
- When a feature has substantial configuration, prefer an explicit structure such as:

```python
FeatureInput(
    request=...,   # operation-specific processing data
    config=...,    # reusable feature configuration
)
```

Equivalent typed structures are allowed when more appropriate to the feature.

- Profiles, seeds, execution limits, and algorithm parameters are configuration unless their value is inherently part of the domain request.
- A caller should be able to inspect the public API and determine which values describe **what is being processed** and which values control **how it is processed**, without reading the feature implementation.


### Outputs

- `result` is always the normal usable feature result.
- `details` is optional and completely feature-specific. Do not enforce common fields inside it.
- `metadata` contains only small execution-wide information such as the selected mode and duration.
- Shared `FeatureExecution`, `ExecutionMode`, and `ExecutionMetadata` types belong in `fpg_core.domain`.
- Feature-specific result and details types remain inside the feature.
- In `PRODUCTION`, avoid collecting expensive R&D details.
- Consumer-visible `DEBUG` behavior must be documented in `docs/feature_documentations/<feature>.md`.
- Do not silently break an existing public API only to make an older feature match this template. Treat legacy inconsistencies as migration work that requires an intentional compatibility/versioning decision.

## Internal Feature README

`src/fpg_core/<feature>/README.md` is an **internal development document**, not consumer documentation. It exists to preserve implementation context for maintainers and AI agents working inside `fpg-core`.

Use it for information such as:

- feature responsibility and internal boundaries,
- algorithm/model design,
- important invariants,
- implementation stages,
- non-obvious numerical/geometry behavior,
- internal extension design,
- maintenance/R&D notes,
- known implementation limitations or technical debt.

Its structure may follow the needs of the feature. Do not duplicate the complete consumer API contract into the internal README.

## Consumer Documentation Obligation

Every public feature must have one canonical consumer document at:

```text
docs/feature_documentations/<feature>.md
```

Package-wide consumer conventions and shared domain contracts belong in:

```text
docs/API_GUIDE.md
```

The mandatory maintenance rules are defined in:

```text
docs/DOCUMENTATION_STANDARD.md
```

When a public feature changes, updating the corresponding consumer document is part of the implementation. A change is incomplete if active public code and consumer documentation disagree.

At minimum, the consumer feature document must keep synchronized:

- purpose and supported use,
- preferred public imports and operation signatures,
- exact input/configuration contracts, defaults, units, and validation,
- exact output/status variants and `PRODUCTION`/`DEBUG` behavior,
- consumer-observable errors, warnings, findings, and diagnostics,
- realistic public-API examples,
- feature-root public export inventory,
- compatibility/deprecation/migration notes.

Do not treat the internal feature README as a substitute for this document.

### AI workflow

When AI modifies or creates a public feature:

1. Read this feature template.
2. Read `docs/DOCUMENTATION_STANDARD.md`.
3. Inspect the feature's current public exports, API, contracts, config, exceptions, and relevant tests.
4. Preserve public compatibility unless a breaking change is deliberate.
5. Update the feature consumer document when observable public behavior changes.
6. Update `docs/API_GUIDE.md` when shared/package-wide behavior changes.
7. Update `CHANGELOG.md` and version/migration information when compatibility is affected.

## Testing Rules

```text
tests/
└── feature_name/
    └── test_end_to_end.py
```

- Keep tests outside `src/fpg_core`.
- Use one dedicated folder per feature.
- Default to one end-to-end flow test covering the public API.
- The end-to-end test should cover normal production execution and, when supported, `DEBUG` execution.
- Add focused regression or unit tests only when explicitly requested or when needed to protect a known defect, invariant, or numerical edge case.
- Tests must call the public API rather than internal implementation modules.
