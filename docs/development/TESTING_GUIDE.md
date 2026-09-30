# Testing Guide

The test strategy has two levels: small predictable verification and targeted public-API flows. Keep both simple enough that normal feature changes can maintain them without redesigning the test system.

## Level 1 - contract and architecture tests

`tests/contracts/` and `tests/architecture/` protect repository-wide rules that should be boring and deterministic:

- public export inventory remains synchronized;
- canonical documentation mentions every public export;
- documentation coverage rows include current public dataclass fields, function arguments, and enum members;
- package version metadata and the consumer reference stay synchronized;
- shared execution-mode contracts remain stable;
- feature folders keep the expected public boundary;
- a feature does not import another feature's private implementation.

These tests should avoid expensive solving and stochastic search.

Add focused regression tests when a real bug, numerical edge case, or important invariant needs protection. Do not add unit tests only to mirror internal implementation details.

## Level 2 - targeted flow tests

`tests/flows/` verifies that public features still connect correctly.

| Flow | Features covered | Run when these areas change |
|---|---|---|
| `test_land_flow.py` | Buildable Land -> Usable Land | buildable/usable land, shared land geometry/contracts |
| `test_candidate_flow.py` | Preprocessing -> Candidate Search -> Candidate Circulation -> Candidate Scoring | preprocessing, candidate/grid/search/circulation/scoring contracts |
| `test_plan_flow.py` | Floor Plan Solver -> Post-Processing -> Openings -> Floor Plan Scoring | solver, floor-plan geometry, post-processing, openings, final scoring |

If a changed feature already appears in one of these flows, update that flow when its integration contract changes. Add a new flow only when a new compatibility edge cannot be represented clearly in an existing one.

Use fixed seeds and a single solver worker where deterministic verification matters. Keep trial counts and solver time limits small in automated flows.

## Manual/R&D full flow

`custom_test/full_flow/` remains the deeper package-local workbench. It is intentionally not the default automated test suite because it is slower and produces visual/debug output.

Use it when:

- several pipeline stages changed together;
- solver/search quality needs visual inspection;
- DEBUG payloads/viewer output changed;
- a regression only appears in a realistic end-to-end scenario.

Generated JSON belongs under `custom_test/outputs/` and is ignored by Git.

## Normal commands

```bash
python -m pytest tests/contracts tests/architecture
python -m pytest tests/flows/test_land_flow.py
python -m pytest tests/flows/test_candidate_flow.py
python -m pytest tests/flows/test_plan_flow.py
python -m pytest
```

The solver/openings flow requires the normal runtime dependency `ortools`. A complete development/CI environment must install normal runtime dependencies and run this flow. If a deliberately partial environment cannot run it, report that limitation rather than treating the package as fully verified.
