# fpg-core

Reusable Python domain contracts and computational features for automated residential floor-plan generation.

## Documentation

- [Consumer package reference](docs/PACKAGE_FEATURE_REFERENCE.md) - complete supported public API, contracts, modes, failures, defaults, and integration notes.
- [Developer documentation](docs/README.md) - feature architecture, testing, and documentation-maintenance guides.
- [Contributing and development](CONTRIBUTING.md) - normal local development workflow.
- [Manual full-flow workbench](custom_test/full_flow/README.md) - slower end-to-end R&D/visual verification.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Verify

```bash
python tools/generate_public_api_manifest.py --check
python -m pytest
python -m ruff check src tests custom_test tools
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
