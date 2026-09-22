# fpg-core

Reusable Python domain contracts and algorithms for automated residential floor-plan generation.

## Documentation

Consumer documentation is intentionally separate from feature implementation notes:

- [Consumer API guide](docs/API_GUIDE.md) covers package-wide conventions, shared contracts, execution modes, compatibility, and versioning.
- [Feature documentation](docs/feature_documentations/README.md) contains one consumer usage document per public feature.
- [Documentation standard](docs/DOCUMENTATION_STANDARD.md) defines the mandatory synchronization/versioning rules for maintainers and AI agents.
- [`FEATURE_TEMPLATE.md`](src/fpg_core/FEATURE_TEMPLATE.md) defines the feature architecture conventions used inside the package.

Internal `src/fpg_core/<feature>/README.md` files are development notes, not consumer API documentation.

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
from fpg_core.buildable_land import calculate_buildable_land
from fpg_core.usable_land import find_usable_land
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
