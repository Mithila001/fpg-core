# Contributing and Development

`fpg-core` is a reusable Python package. Keep application concerns outside the package and preserve the dependency direction `consumer application -> fpg-core`.

## Setup

```bash
python -m pip install -e ".[dev]"
```

## Change workflow

1. Change the smallest relevant feature or shared domain contract.
2. Follow `docs/development/FEATURE_GUIDE.md` for public boundaries and feature structure.
3. Update predictable contract/regression tests and the affected targeted flow described in `docs/development/TESTING_GUIDE.md`.
4. Run the relevant tests, then the full suite when practical.
5. When consumer-visible behavior changes, update `docs/PACKAGE_FEATURE_REFERENCE.md` using `docs/development/PACKAGE_DOCUMENTATION_GUIDE.md`.
6. Regenerate `docs/_generated/public_api_manifest.json` whenever public exports change.
7. Remove temporary notes and generated local context before committing.

## Verification

```bash
python tools/generate_public_api_manifest.py --check
python -m pytest
python -m ruff check src tests custom_test tools
python -m mypy src/fpg_core
```

The manual `custom_test/full_flow/` workbench is intentionally separate from the normal pytest suite. Use it for end-to-end R&D, visual inspection, and deeper scenario debugging.
