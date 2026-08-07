# fpg-core

Reusable Python domain contracts and algorithms for automated residential floor-plan generation.

## Documentation

- [Consumer feature reference](docs/PACKAGE_FEATURE_REFERENCE.md) documents every
  feature independently, including public APIs, contracts, configuration, outputs,
  errors, and examples.
- [Install and verify](docs/INSTALL_AND_VERIFY.md) covers local installation and
  package checks.
- [Trial flow test 2](custom_test/trial_flow_test_2/README.md) demonstrates the
  solver profiles, post-processing, openings, and final scoring with realistic JSON.

## Install

```bash
python -m pip install -e ".[dev]"
```

Run verification:

```bash
python -m pytest
python -m ruff check src tests
python -m mypy src/fpg_core
```

## Public feature APIs

Use feature-level public modules:

```python
from fpg_core.floor_plan_preprocessing import prepare_generation_input
from fpg_core.candidate_search import search_candidates
from fpg_core.candidate_circulation import refine_candidate_circulation
from fpg_core.candidate_scoring import evaluate_candidate
from fpg_core.floor_plan_solver import generate_floor_plan
from fpg_core.floor_plan_post_processing import post_process_floor_plan
from fpg_core.floor_plan_openings import generate_openings
from fpg_core.floor_plan_scoring import score_floor_plan
```

Shared contracts are available from `fpg_core.domain`.
