# fpg-core

`fpg-core` contains the reusable computational core of the FPG floor-plan generation system.

The package is intentionally independent from FastAPI, server jobs, SSE, persistence, artifact storage, application logging, and server-owned configuration files.

## Responsibilities

The package provides:

- shared geometry and floor-plan domain contracts,
- buildable-land and usable-land calculation,
- floor-plan request preprocessing,
- Optuna-based candidate search,
- candidate scoring,
- OR-Tools CP-SAT floor-plan solving,
- floor-plan post-processing,
- door and window generation,
- final floor-plan scoring,
- immutable configuration schemas and core-side validation.

The host application remains responsible for:

- loading configuration values from JSON, a database, or another source,
- constructing `FpgCoreConfig`,
- calling `validate_fpg_core_config`,
- pipeline orchestration, time limits, retries, and cancellation,
- API models and transport concerns,
- progress events, logging, artifacts, and persistence.

## Installation

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
pytest
```

## Basic imports

```python
from fpg_core.config import FpgCoreConfig, validate_fpg_core_config
from fpg_core.types import FloorPlan, FloorPlanGenerationSpec, Polygon, RoomType
```

Feature APIs remain grouped by responsibility:

```python
from fpg_core.floor_plan_preprocessing import prepare_generation_input
from fpg_core.candidate_search import search_candidates
from fpg_core.floor_plan_solver import generate_floor_plan
```

Use the exact exported function names documented by each feature package. The root `fpg_core` package is deliberately lightweight and does not eagerly import the solver stack.

## Configuration boundary

`fpg-core` defines and validates configuration schemas, but it does not read files.

Typical server flow:

```python
raw_data = server_configuration_loader.load()
core_config = server_configuration_mapper.to_fpg_core_config(raw_data)
validate_fpg_core_config(core_config)
```

The server then passes the relevant configuration section into each core operation.

See [docs/SERVER_INTEGRATION.md](docs/SERVER_INTEGRATION.md) for the intended boundary and [docs/MIGRATION.md](docs/MIGRATION.md) for import changes.

## Current status

This repository starts at version `0.1.0` and should be treated as an alpha extraction of the existing FPG algorithms. The computational source has been moved without intentionally redesigning algorithm behavior.
