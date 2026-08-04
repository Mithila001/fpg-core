# fpg-core

Reusable Python domain contracts and algorithms for automated residential floor-plan generation.

## Version 0.2.0 grid model

Candidate Search now creates an adaptive, whole-project-unit grid that covers the exact preprocessed floor boundary. The resulting `CandidateMap` carries both the selected hint points and the `ResolvedCandidateGrid` used by Candidate Search, Candidate Circulation, and Relationship Quality.

Key rules:

- `10` project units = `1` metre; `1` project unit = `10` centimetres.
- Preprocessing floors maximum floor limits to whole project units.
- Candidate Search is configured by `long_axis_node_count`, not a physical `grid_resolution`.
- Candidate points are always selected from the resolved grid.
- Overlapping points are rejected inside Candidate Search before downstream features run.
- Candidate Circulation and Relationship Quality consume the same grid from `CandidateMap`.
- Zone Suitability and Spatial Distribution remain independent analysis overlays.

See:

- `docs/INSTALL_AND_VERIFY.md`
- `docs/ADAPTIVE_CANDIDATE_GRID.md`
- `docs/MIGRATION_0.1_TO_0.2.md`

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
from fpg_core.floor_plan_preprocessing.api import prepare_generation_input
from fpg_core.candidate_search.api import search_candidates
from fpg_core.candidate_circulation.api import refine_candidate_circulation
from fpg_core.candidate_scoring.api import evaluate_candidate
```

Shared contracts are available from `fpg_core.domain`.
