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
7. Feature-specific contracts, context objects, settings, results, and R&D detail types stay inside that feature.
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

### Outputs

- `result` is always the normal usable feature result.
- `details` is optional and completely feature-specific. Do not enforce common fields inside it.
- `metadata` contains only small execution-wide information such as the selected mode and duration.
- Shared `FeatureExecution`, `ExecutionMode`, and `ExecutionMetadata` types belong in `fpg_core.domain`.
- Feature-specific result and details types remain inside the feature.
- In `PRODUCTION`, avoid collecting expensive R&D details.
- Each feature README must document what its `DEBUG` mode captures.

## Feature README Structure

Every feature README should use this structure:

```md
# <Feature Name>

<Brief explanation of the feature and its responsibility.>

## Guide

### Public API
<Supported operations and import paths.>

### Inputs
<Required structures, optional configuration, execution modes, important fields, and units.>

### Outputs
<Result, R&D details, metadata, statuses, and important fields.>

### Errors and Expected Behaviour
<Exceptions, failure results, mutation, determinism, and side effects.>

### Extension Points
<Optional registries, profiles, evaluators, processors, or constraints.>

## AI Instructions
- Keep this README synchronized with public behaviour.
- Update examples when APIs or contracts change.
- Document changes to inputs, outputs, and execution-mode details.
- Do not document private implementation as a supported API.
- Do not import another feature's internal modules.
```

Sections that do not apply may be omitted.

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
