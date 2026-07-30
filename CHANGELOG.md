# Changelog

## 0.1.0

- Extracted the server-independent algorithm source into the `fpg_core` package.
- Added package metadata and typed-package marker.
- Renamed the primary shared contract namespace from `types_new` to `types`.
- Added a temporary compatibility namespace at `fpg_core.types_new`.
- Added architecture checks preventing server dependencies from entering the package.
