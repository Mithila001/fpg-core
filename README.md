# fpg-core

`fpg-core` is the reusable computational package for the FPG residential
floor-plan generation system. It contains typed domain contracts, geometry
operations, candidate search and scoring, constraint solving, post-processing,
and opening generation.

The package is deliberately independent of web frameworks and host
applications. API transport, configuration loading, orchestration, persistence,
logging, and progress reporting belong to consumers such as `fpg-server`.

## Requirements

- Python 3.11 or 3.12
- A supported platform for OR-Tools and Shapely

## Installation

Install the package from the repository:

```bash
python -m pip install -e .
```

For development, include the quality and packaging tools:

```bash
python -m pip install -e ".[dev]"
```

## Public API

Shared contracts live in `fpg_core.types`:

```python
from fpg_core.config import FpgCoreConfig, validate_fpg_core_config
from fpg_core.types import FloorPlan, FloorPlanGenerationSpec, Polygon, RoomType
```

Algorithms are grouped by pipeline responsibility:

```python
from fpg_core.candidate_search import search_candidates
from fpg_core.floor_plan_preprocessing import prepare_generation_input
from fpg_core.floor_plan_solver import generate_floor_plan
```

The root package and solver-heavy feature packages use lazy exports, so importing
configuration or domain contracts does not initialize OR-Tools unnecessarily.
New code should import only documented package exports, not internal modules.

## Configuration boundary

`fpg-core` defines immutable configuration schemas and validates them, but never
loads configuration from files, environment variables, databases, or application
state. A host application should:

1. load its own configuration,
2. map the values to `FpgCoreConfig`,
3. call `validate_fpg_core_config`, and
4. pass the relevant configuration section to each algorithm.

## Project layout

```text
src/fpg_core/
├── types/                       Shared domain contracts
├── buildable_land/              Setback and buildable-space geometry
├── usable_land/                 Usable-area search and transforms
├── floor_plan_preprocessing/    Request normalization and validation
├── candidate_search/            Optuna-based candidate exploration
├── candidate_scoring/           Candidate evaluator framework
├── floor_plan_solver/           OR-Tools CP-SAT generation
├── floor_plan_post_processing/  Geometry cleanup pipeline
├── floor_plan_openings/         Door and window generation
└── floor_plan_scoring/          Final-plan evaluator framework
```

`fpg_core.types_new` is a temporary compatibility namespace. Use
`fpg_core.types` in all new code.

## Documentation

- [Server integration](docs/SERVER_INTEGRATION.md)
- [Migration from `app.algorithms`](docs/MIGRATION.md)
- [Candidate search](docs/features/candidate-search.md)
- [Candidate scoring](docs/features/candidate-scoring.md)
- [Floor-plan preprocessing](docs/features/floor-plan-preprocessing.md)
- [Floor-plan solver](docs/features/floor-plan-solver.md)
- [Door and window generation](docs/features/floor-plan-openings.md)

## Development checks

```bash
ruff check .
mypy
pytest
python -m build
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup and architectural
constraints.
