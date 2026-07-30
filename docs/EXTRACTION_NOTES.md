# Extraction notes

This repository was assembled from the isolated `algorithms` source supplied from `fpg-server`.

## Preserved

- production algorithm implementations,
- algorithm-specific contracts, profiles, registries, exceptions, and diagnostics,
- shared geometry and floor-plan domain types,
- the central immutable `FpgCoreConfig` contract and validation entry point,
- feature-level README and legacy-behavior notes.

## Intentionally omitted

- server-coupled historical tests,
- debug renderers and visualization integration,
- algorithm event logging and artifact persistence,
- generated `__pycache__` directories and `.pyc` files,
- the source-less `fp_boundary_finder` bytecode directory from the supplied archive.

`fp_boundary_finder` was not referenced by production Python source in the archive. It should only be restored if its original `.py` source is recovered and an active runtime import is confirmed.

## Package adjustments

- moved the source under `src/fpg_core`,
- changed internal imports to the package-relative `fpg_core` layout,
- renamed the main `types_new` namespace to `fpg_core.types`,
- retained `fpg_core.types_new` as a temporary compatibility namespace,
- added lazy public imports to prevent unrelated features from eagerly initializing OR-Tools,
- added packaging metadata, CI, architecture checks, and migration documentation.

## Validation performed

- all source files compiled successfully,
- package-level tests passed,
- a wheel was built successfully,
- the built wheel passed a clean import smoke test,
- all package modules were import-wired successfully using an import-only OR-Tools stub,
- the complete `FpgCoreConfig` validation path passed with a representative configuration fixture.

The last check verifies package wiring only. Actual CP-SAT solving still needs to be exercised in the target project environment with the declared OR-Tools dependency installed.
