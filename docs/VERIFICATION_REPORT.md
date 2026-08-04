# Verification Report

Verified on 2026-08-04 with Python 3.13.

## Passed

```text
python -m compileall -q src/fpg_core
pytest -q
6 passed
```

A wheel was built with:

```bash
python -m pip wheel . --no-deps --no-build-isolation -w dist
```

The produced `fpg_core-0.2.0-py3-none-any.whl` was installed, and the same six tests passed from outside the source tree.

The tests cover:

- exact-boundary adaptive grid construction;
- balanced whole-unit axis gaps;
- Candidate Search overlap prevention;
- Candidate Circulation over the adaptive grid;
- Relationship Quality using the same grid;
- preprocessing floor-limit normalization and aspect residual;
- end-to-end Search -> Circulation -> Relationship scoring.

## Environment limitation

OR-Tools was unavailable from the execution environment's package index. Solver-specific runtime tests were therefore not executed. The changed modules compile, and the migration does not directly modify the floor-plan solver.

Run the repository's complete checks in the normal development environment:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
python -m mypy src/fpg_core
```
