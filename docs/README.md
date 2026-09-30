# fpg-core documentation

## Consumer documentation

The canonical consumer contract is [PACKAGE_FEATURE_REFERENCE.md](PACKAGE_FEATURE_REFERENCE.md). It is source-verified and is intended to let a consuming application integrate supported public features without reading implementation modules.

When consumer-visible behavior changes, update that reference using [development/PACKAGE_DOCUMENTATION_GUIDE.md](development/PACKAGE_DOCUMENTATION_GUIDE.md).

`_generated/public_api_manifest.json` is a machine-generated export inventory used to detect public-surface drift. Regenerate it with `python tools/generate_public_api_manifest.py`; do not edit it manually.

## Developer documentation

- [Feature development guide](development/FEATURE_GUIDE.md) - package boundaries, feature shape, public contracts, and extension rules.
- [Testing guide](development/TESTING_GUIDE.md) - contract tests, targeted flows, and the manual full-flow workbench.
- [Package documentation guide](development/PACKAGE_DOCUMENTATION_GUIDE.md) - completeness rules and AI/human workflow for maintaining the consumer reference.

Historical or migration-specific notes are supporting information only. Active code, exports, tests, and the canonical consumer reference take precedence.
