# Development and verification

Core uses the root `.venv`; Lab uses `fpg-lab/.venv`, containing both local packages.
See the [setup tutorial](../../README.md). Commands below use `python` to mean the
appropriate environment's interpreter; activation is optional.

## Select checks by impact

| Change | Verification |
| --- | --- |
| Documentation | Links/placement, affected contract coverage, changed runnable examples |
| Core internal behavior | Focused feature/flow tests and applicable static checks |
| Public behavior used by Lab | Core checks, affected Lab caller review, cheap integration verifier, relevant Lab regression tests |
| Lab code | Relevant Lab tests, lint, and type checks |
| Solver/search quality or pipeline behavior | Bounded representative experiment when the result is needed |

A Core change does not automatically require Lab's full suite or research runs.
Inspect the affected public contract before deciding consumer impact. Lint/import
checks, automated orchestration tests, and real experiments are different checks.

## Core commands

From the repository root:

```bash
python tools/check_docs.py
python tools/generate_public_api_manifest.py --check
python -m pytest
python -m ruff check src tests tools
python -m mypy src/fpg_core
python -m build
python tools/check_distribution.py
```

Root pytest discovery targets `tests/` only. Architecture and contract tests protect
feature boundaries, public exports, documentation coverage, execution contracts,
and metadata. The ten public feature examples execute with their documented
prerequisites as regression checks. They do not require Lab's dependencies. Focused public-API flows are
in `tests/flows/`: land, candidates, and final plan processing. Use fixed seeds,
small trial counts, bounded solver times, and one worker when deterministic checks
matter. A passing inventory test does not prove documentation semantics.

`python -m build` builds a source archive and then a wheel from it. The distribution
checker inspects both archives and dependency metadata. To verify an installed
wheel, create a fresh environment outside package source, install the wheel and
its runtime dependencies, and run a public import/example. Confirm Lab, NiceGUI,
and Plotly are absent. Do not install Core dev extras for this consumer check.

## Lab commands

From `fpg-lab/`, with its interpreter:

```bash
python -m scripts.verify_fpg_core
python -m pytest
python -m ruff check fpg_lab scripts tests
python -m mypy fpg_lab scripts
```

The verifier checks the local Core origin, public imports, seed schema, and all P01
configuration mappings without running solver experiments. The existing suite
checks orchestration with real preprocessing/search and deterministic substitutes
for costly stages; it covers branch failures, debug retention, input validation,
shutdown, recovery, and snapshots. Use targeted test selection for narrow changes.

## Manual experiments

Use [Lab's run instructions](../../fpg-lab/README.md) and the
[P01 family guide](../../fpg-lab/docs/experiments/p01.md). Old root experiment
runners/viewers are retired. Core-only usage examples remain in the public docs;
Core integration tests remain independent of Lab.

Run headless experiments against an isolated database. Use explicit small trial
counts and timeouts for smoke checks. P01C candidate completion does not imply its
floor-plan branches succeeded. Inspect nested run statuses and errors. Actual
research runs are not part of default CI.

Automatic CI runs for pull requests targeting `main`, including updates to an open
pull request; ordinary branch pushes do not trigger it. CI checks Core independently.
The Lab workflow runs cheap verification on relevant
Core/Lab changes, runs Lab's suite for Lab changes, and supports manually requesting
that suite for Core integration changes. Report checks actually run, failures, and
environment limitations; never claim success for unavailable tooling.
