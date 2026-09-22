# fpg-core documentation

## Consumer documentation

The canonical consumer documentation set is:

- [API_GUIDE.md](API_GUIDE.md) — package-wide installation, imports, units, shared domain contracts, execution modes, compatibility, errors/statuses, and versioning.
- [feature_documentations/](feature_documentations/README.md) — one complete usage document per public feature.

A consumer should be able to use supported public features from those documents without reading `src/fpg_core`.

## Maintainer / AI documentation

- [DOCUMENTATION_STANDARD.md](DOCUMENTATION_STANDARD.md) — mandatory rules for creating and keeping consumer documentation synchronized with public code.
- [`src/fpg_core/FEATURE_TEMPLATE.md`](../src/fpg_core/FEATURE_TEMPLATE.md) — feature architecture and public-boundary conventions.

Internal `src/fpg_core/<feature>/README.md` files are development notes and are not the consumer API contract.
