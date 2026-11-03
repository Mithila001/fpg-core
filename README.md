# fpg-core

A reusable Python package for constraint-based, single-storey residential floor-plan generation. It prepares a buildable area, explores candidate room layouts with Optuna, uses OR-Tools CP-SAT to place rooms, and refines and evaluates the resulting plan.

The package provides algorithms and typed domain contracts, **not** an HTTP service, database, or application-specific orchestration layer. It currently targets 2D layouts on convex parcels; it does not produce construction drawings or multi-storey designs.

## Install

Python 3.11 or later:

```bash
python -m pip install -e ".[dev]"
```

## Use

Supported operations are imported from their feature packages:

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

`fpg_core.domain` provides shared models. Each stage accepts typed inputs/configuration; the consumer composes the pipeline. See the [pipeline](docs/architecture/pipeline.md) and [contract guide](docs/architecture/contracts.md) for the important hand-offs. A runnable package-only example is in [`experiments/full_flow/`](experiments/full_flow/README.md).

## Documentation and development

- [Documentation index](docs/README.md) - architecture, focused feature guides, and maintenance rules.
- [Local verification](docs/development/verification.md) - tests, static checks, and manual experiments.
- [Changelog](docs/history/CHANGELOG.md) - contract and migration history.
- [Agent instructions](AGENTS.md) - coding-agent entry point.

```bash
python tools/check_docs.py
python tools/generate_public_api_manifest.py --check
python -m pytest
```

Run the available checks for the current checkout; the supplied repository snapshot may not contain a `tests/` directory.
