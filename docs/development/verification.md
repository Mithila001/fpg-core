# Development and verification

## Setup

From the repository root, with Python 3.11 or newer:

```bash
python -m pip install -e ".[dev]"
```

## Checks

```bash
python tools/check_docs.py
python tools/generate_public_api_manifest.py --check
python -m pytest
python -m ruff check src tests experiments tools
python -m mypy src/fpg_core
```

The manifest check parses public `__all__` declarations without importing heavy solver dependencies. If exports change, run `python tools/generate_public_api_manifest.py` and include the generated JSON. Check docs after every documentation move or API rename.

**Checkout caveat:** some distributed source snapshots do not include a `tests/` directory, even though `pyproject.toml` defines dev test dependencies. Do not report `pytest` passing unless tests are present and run; absent tests normally yield pytest exit code 5. Add appropriate focused tests when implementing new behavior. If a tool or optional dependency is unavailable, report that instead of treating it as a passed check.

For algorithm changes, verify public contracts/validation, geometry invariants, feasibility and infeasibility, seeded behavior, configuration, and stage compatibility as appropriate. Run focused checks before any broader suite.

## Manual package-only flows

- `python experiments/phase-1/run_flow.py`: preprocessing through candidate scoring, target/limit controlled; see [phase-1 README](../../experiments/phase-1/README.md).
- `python experiments/full_flow/run_full_flow.py`: buildable land through final scoring and custom checks; see [full-flow README](../../experiments/full_flow/README.md).

These are **manual experiments**, not automated tests. They write outputs under `experiments/outputs/` (ignored by Git). They require installed runtime dependencies, including OR-Tools for the complete pipeline, and may be expensive. The experiment scripts are not part of the installed package and must not become runtime imports of `fpg_core`.
