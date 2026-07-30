# AGENTS.md

## Project purpose

`fpg-core` is the reusable computational package for the FPG residential floor-plan generation system. It contains domain contracts, configuration schemas, validation, geometry logic, search, scoring, constraint solving, post-processing, and opening generation.

It is a Python package, not a server application. Projects such as `fpg-server`, `fpg-lab`, scripts, and future tools install `fpg-core` and call its public APIs.

The required dependency direction is:

```text
consumer application -> fpg-core
```

`fpg-core` must never import or depend on a consumer application.

## Origin

This repository was extracted from the former `app/algorithms` section of `fpg-server`. Server-specific concerns were intentionally left behind, including FastAPI routes, jobs, SSE, execution contexts, persistence, artifacts, application logging, and server-owned configuration files.

Preserve this separation. Do not recreate server infrastructure inside the package.

## Responsibility boundary

`fpg-core` owns:

- stable domain and geometry types,
- algorithm input and output contracts,
- immutable configuration schemas,
- configuration and request validation,
- reusable computational behavior,
- algorithm-specific errors and diagnostics.

Consumer applications own:

- API and transport models,
- configuration storage and loading,
- mapping external data into core types,
- pipeline orchestration, retries, timeouts, and cancellation,
- logging, artifacts, persistence, jobs, and progress streaming.

The core may define a required configuration schema and validate it, but it must not read JSON files, environment variables, databases, or application state.

## Public API stability

Inputs and outputs are the package boundary. Treat changes to exported functions, dataclasses, enums, exceptions, result structures, field meanings, and default behavior as public API changes.

- Prefer extending contracts over replacing them.
- Do not rename, remove, reorder, or reinterpret public fields casually.
- Avoid returning untyped dictionaries when a stable domain type is appropriate.
- Keep algorithm results deterministic for the same inputs where practical.
- Validate invalid input early and raise clear core-owned exceptions.
- When a breaking change is necessary, document it and update the package version appropriately.

Internal modules may evolve, but consumers should depend only on documented public entry points.

## Types and configuration

Use `fpg_core.types` as the organized shared domain-type layer. Keep types focused, explicit, and reusable across features.

- Define a concept once; do not create slightly different duplicates in separate modules.
- Prefer enums and typed dataclasses over magic strings and loosely shaped mappings.
- Prefer frozen, immutable configuration objects.
- Keep request-specific data separate from reusable configuration.
- Pass only the relevant configuration section into a feature when possible.
- Maintain the temporary `fpg_core.types_new` compatibility namespace until an intentional migration removes it.

`FpgCoreConfig` is the top-level configuration contract. Consumer projects provide its values; `fpg-core` owns its structure and validation through `validate_fpg_core_config()`.

## Implementation rules

- Keep production code under `src/fpg_core` independent of `fpg-server` and other host projects.
- Use package-relative imports for internal modules.
- Do not import FastAPI, server Pydantic models, routes, services, pipelines, streaming, application loggers, or artifact storage.
- Do not perform file I/O, network access, or process-wide configuration as a hidden side effect of an algorithm call.
- Keep the root package lightweight; avoid eagerly importing heavy solver dependencies without need.
- Prefer small, responsibility-focused modules and clear execution flow.
- Favor simple, pragmatic code over clever abstractions or premature framework design.
- Preserve current algorithm behavior unless a change is explicitly required and tested.
- Add third-party dependencies only when they provide clear value and belong in the computational core.

## Tests and quality

For meaningful changes:

- add or update focused tests,
- preserve the architecture test that forbids server imports,
- test public input/output behavior rather than private implementation details,
- cover validation and important failure paths,
- run `pytest`, formatting/lint checks, and a package build when relevant.

Do not treat legacy comments, old behavior-mapping notes, or historical tests as automatically authoritative. Confirm behavior from active public APIs, imports, configuration, and tests.

## Documentation

Keep consumer-facing documentation in `docs/` accurate and usable by projects that install this package.

`docs/SERVER_INTEGRATION.md` is the primary integration guide and must be updated when changes affect:

- installation or imports,
- public APIs or result structures,
- configuration construction or validation,
- required consumer responsibilities,
- migration or compatibility behavior.

Also update `README.md`, `CHANGELOG.md`, and relevant feature documentation when appropriate. Documentation should describe how to use the package, not expose unnecessary internal implementation details.

## Change checklist

Before completing a change, confirm:

1. The core still has no dependency on a host application.
2. Public contracts remain stable or the breaking change is explicit.
3. Shared types remain centralized and consistent.
4. Configuration remains externally supplied and core-validated.
5. Consumer documentation reflects observable changes.
6. The solution remains clear, scalable, and no more complex than necessary.
