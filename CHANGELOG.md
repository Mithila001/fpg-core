# Changelog

## Unreleased

- Moved feature documentation from the importable package into `docs/features`.
- Removed generated project inventories and extraction-only migration notes.
- Added consistent local and CI lint, type-check, test, and build commands.
- Added Pyright/Pylance source-root configuration and clarified lazy public exports.

## 0.1.0

- Extracted the server-independent algorithm source into the `fpg_core` package.
- Added package metadata and typed-package marker.
- Renamed the primary shared contract namespace from `types_new` to `types`.
- Added a temporary compatibility namespace at `fpg_core.types_new`.
- Added architecture checks preventing server dependencies from entering the package.
