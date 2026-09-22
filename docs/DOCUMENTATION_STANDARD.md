# fpg-core Consumer Documentation Standard

This file is the mandatory maintenance contract for AI agents and developers who add, remove, rename, or change a public `fpg-core` feature.

The goal is simple: **a consumer must be able to use every supported public feature from the consumer documentation without reading `src/fpg_core`.**

## 1. Canonical documentation layout

Consumer documentation has two layers:

```text
docs/
├── API_GUIDE.md
└── feature_documentations/
    ├── README.md
    └── <feature>.md
```

- `docs/API_GUIDE.md` owns package-wide behavior: installation, import conventions, units, shared domain contracts, `ExecutionMode`, `FeatureExecution`, cross-feature compatibility, common status/error concepts, extension APIs, and API versioning.
- `docs/feature_documentations/<feature>.md` owns the complete consumer contract for one public feature.
- `src/fpg_core/<feature>/README.md` is **internal development documentation**. It may describe algorithms, design decisions, constraints, R&D notes, implementation structure, or maintenance guidance. It is not the consumer contract.

Do not maintain a second monolithic consumer reference containing copies of all feature documentation. Duplicate consumer references drift and are not canonical.

## 2. Documentation is part of the public API change

A public code change is incomplete until its consumer documentation is synchronized.

The same change must update documentation when it changes any of the following:

| Code/API change | Required documentation update |
|---|---|
| New public feature | Add `docs/feature_documentations/<feature>.md` and add it to both documentation indexes |
| New/removed/renamed public operation | Update Public API, imports, examples, export inventory, compatibility notes |
| Input field/type/default/validation change | Update Inputs, configuration if relevant, examples, errors |
| Output field/type/status change | Update Outputs and all output variants/examples |
| New exception or changed failure behavior | Update Errors / failure conditions |
| New warning/finding/diagnostic | Update Warnings/diagnostics or DEBUG behavior |
| `PRODUCTION`/`DEBUG` behavior change | Update execution-mode behavior and details contract |
| Configuration/default/profile change | Update Configuration, defaults, recommendations, examples |
| Unit/geometry/ID/enum change | Update feature docs and `API_GUIDE.md` if package-wide |
| Compatibility alias/deprecation | Document replacement, compatibility behavior, and removal policy |
| Breaking public API change | Update docs, `CHANGELOG.md`, migration guidance, and package version classification |
| Internal-only implementation change | No consumer-doc update unless observable behavior changes |

Do not merge a public API change while the consumer documentation still describes the old contract.

## 3. Source verification order

Never generate consumer documentation from an old README or previous documentation alone. Verify the active source.

For a feature change, inspect at minimum:

1. `pyproject.toml` and `src/fpg_core/__init__.py` when package/version compatibility is relevant.
2. `src/fpg_core/<feature>/__init__.py` and its `__all__` export surface.
3. `src/fpg_core/<feature>/api.py`.
4. Feature contracts/types/models used by the public API.
5. Feature configuration, defaults/profiles, validation, exceptions, registries, and status enums that affect consumers.
6. `fpg_core.domain` for canonical shared types.
7. Public-API tests and runtime behavior where needed to confirm semantics.
8. Internal feature README/design notes only for explanation after the public contract has been verified from active code.

If documentation and active source disagree, the active supported public source is authoritative. Fix the documentation in the same change.

## 4. Required feature document structure

Every `docs/feature_documentations/<feature>.md` must contain the following sections unless a section is provably not applicable:

```text
# <Feature Name>

## Purpose
## Public API
## Inputs
## Configuration
## Recommended values
## Outputs
## Warnings / diagnostics
## Errors / failure conditions
## Usage example
## Important behavioral notes
## Public Export Inventory
## API Compatibility
```

Add dedicated subsections when a feature has complex profiles, policies, statuses, warnings, extension registries, output variants, or DEBUG details.

### 4.1 Purpose

State:

- what the feature does,
- when a consumer uses it,
- what it deliberately does not do when that boundary matters.

Do not explain private implementation unless it changes consumer behavior.

### 4.2 Public API

Document the preferred feature-root import and exact supported entry-point signatures.

```python
from fpg_core.<feature> import ...
```

Do not teach consumers to import private implementation modules such as `pipeline`, `manager`, `optimizer`, `model`, individual processor/evaluator implementations, or solver internals unless that module is intentionally part of the supported public contract.

### 4.3 Inputs

Document enough information to construct every required input without source inspection:

- exact type name,
- every required field,
- every optional field and default,
- nested public types,
- accepted enum/literal values when relevant,
- units,
- validation constraints,
- cross-field constraints,
- processing input versus reusable configuration.

Never hide required structure behind wording such as “see source”, “standard fields”, “etc.”, or `...`.

Shared canonical contracts may be referenced to the exact section in `API_GUIDE.md` instead of copied into every feature document.

### 4.4 Configuration

For every consumer-visible setting, state:

- type/default,
- observable effect,
- enforced range/constraint,
- whether the value is a package default, built-in profile value, implementation limit, project recommendation, or domain-specific value.

Do not invent recommended values when the package defines none.

### 4.5 Outputs

Document:

- exact return type,
- all main result fields,
- normal statuses/variants,
- failure statuses returned as data,
- `PRODUCTION` versus `DEBUG` differences,
- details/diagnostics structure that consumers may inspect,
- metadata behavior,
- mutation/identity behavior when relevant.

Returned failure statuses and raised exceptions must not be described as the same mechanism.

### 4.6 Warnings / diagnostics

Document warning/finding channels separately from hard failures. State whether warnings exist in production results, DEBUG details, structured findings/issues, status messages, or not at all. Document the exact severity/status values and important fields when a structured warning/diagnostic contract exists.

### 4.7 Errors / failure conditions

Document consumer-observable exceptions, error codes, statuses, and hard failure behavior.

For each important failure mechanism explain whether the consumer should:

- fix invalid input/configuration,
- handle an expected infeasible/failed result,
- retry with different limits/seed/configuration,
- treat the failure as an unexpected processing error.

### 4.8 Usage example

Provide a realistic example using supported public imports only.

Examples must stay synchronized with the active constructor fields and function signatures. If a feature example uses the reusable `example_*` fixtures, explicitly point to `API_GUIDE.md#reusable-example-fixtures`.

### 4.9 Public Export Inventory

List the exact current feature-root `__all__` surface. This makes accidental export/documentation drift visible during review.

### 4.10 API Compatibility

State the documentation target and point to the package-wide versioning policy. Feature documents do not define independent API versions.

## 5. API_GUIDE.md responsibilities

`docs/API_GUIDE.md` must remain sufficient for all shared behavior and shared contracts. Keep it synchronized when changing:

- package/Python compatibility,
- distribution/runtime dependencies,
- package-root exports,
- `FpgCoreConfig`,
- project units or geometry conventions,
- `ExecutionMode`, `FeatureExecution`, or execution metadata,
- canonical `fpg_core.domain` contracts,
- cross-feature identity/compatibility rules,
- common extension/registry behavior,
- package-wide exception/status guidance,
- compatibility aliases,
- API versioning rules.

Feature-specific behavior belongs in the feature document instead of being duplicated in `API_GUIDE.md`.

## 6. API versioning policy

`fpg-core` has one package version. Do not invent independent feature API versions such as `SolverApiV2` or documentation-only feature versions.

### Before 1.0

- PATCH (`0.x.y`): must not intentionally break a documented public API.
- MINOR (`0.x.0`): may contain a deliberate breaking public API change.
- Every breaking change requires:
  1. updated consumer documentation,
  2. a `CHANGELOG.md` entry,
  3. migration guidance,
  4. synchronized package version metadata before release.

### From 1.0 onward

Follow Semantic Versioning:

- MAJOR: breaking public API change,
- MINOR: backward-compatible capability,
- PATCH: backward-compatible fix.

### Deprecation

A deprecation must document:

- the deprecated public symbol/field/value,
- the supported replacement,
- the release that introduced the deprecation,
- the earliest intended removal release when known.

Do not silently remove a documented public contract.

## 7. Changelog and release synchronization

Before publishing a release, verify all of the following describe the same release state:

```text
pyproject.toml version
src/fpg_core/__version__ behavior
CHANGELOG.md
API_GUIDE.md compatibility/version notes
all affected feature documents
```

If source contains `Unreleased` public API changes, consumer docs may document the current source tree, but they must say that they target current source rather than falsely presenting those contracts as an already-published older distribution version.

## 8. AI change workflow

When an AI agent creates or modifies a feature, it must perform this workflow before considering the task complete:

1. Read `src/fpg_core/FEATURE_TEMPLATE.md`.
2. Read this `docs/DOCUMENTATION_STANDARD.md`.
3. Read the affected feature's internal README for design context.
4. Inspect the active public exports/API/contracts/config/errors/tests.
5. Make the smallest architecture-consistent code change.
6. Update `docs/feature_documentations/<feature>.md` when public behavior changed.
7. Update `docs/API_GUIDE.md` when a package-wide/shared contract changed.
8. Update `CHANGELOG.md` when the change is consumer-visible or compatibility-relevant.
9. Classify the change as internal, patch-compatible, backward-compatible minor, deprecation, or breaking.
10. Verify examples/imports/types against active source.
11. Run relevant tests/lint/type checks available in the repository.
12. Review changed docs for stale names, missing fields, omitted variants, and contradictory version claims.

Documentation synchronization is part of the implementation, not a later cleanup task.

## 9. Writing rules

Consumer documentation must be explicit and source-verifiable.

Do:

- preserve exact public names and enum/status values,
- distinguish package defaults from recommendations,
- explain non-obvious units and identity rules,
- show exact failure behavior,
- keep examples copyable,
- use tables when they improve contract readability.

Do not:

- use `...`, “etc.”, or “similar fields” to omit public contract data,
- claim behavior that is only an implementation guess,
- document private internals as supported API,
- copy the same feature contract into multiple canonical documents,
- rename public concepts in prose in a way that makes code names ambiguous,
- leave documentation updates for a later change.

## 10. Completion checklist

For every changed public feature, verify:

- [ ] Feature-root exports match `Public Export Inventory`.
- [ ] Public operation signatures are current.
- [ ] Required/optional inputs, defaults, units, and validation are documented.
- [ ] Configuration is separated from request/processing data.
- [ ] Result fields and all normal output/failure variants are documented.
- [ ] `PRODUCTION`/`DEBUG` behavior is correct.
- [ ] Exceptions, warnings/findings, and failure statuses are documented.
- [ ] Examples use only supported public imports and current constructors.
- [ ] Shared contracts point to the correct `API_GUIDE.md` reference.
- [ ] Compatibility/deprecation/migration notes are current.
- [ ] `CHANGELOG.md` and package version classification are appropriate.
- [ ] No consumer must inspect package source to use the documented feature.
