# FPG Core and Lab

`fpg-core` is a reusable Python library for single-storey residential floor-plan
generation: land preparation, candidate search, constraint solving, geometry
refinement, openings, and scoring. It targets 2D residential layouts on convex
parcels; it does not produce construction drawings or regulatory approval.

**FPG Lab** is the experimental application in this repository. It uses this
checkout's public Core APIs to run, save, and inspect experiments through NiceGUI
or Python scripts. Core works independently of Lab. Installing or distributing
Core does not include Lab or its UI/database dependencies.

```text
src/fpg_core/    Core library
tests/          Core checks and small integration flows
docs/           Public Core documentation and development guidance
tools/          Documentation and API checks
fpg-lab/        Experimental application, tests, seeds, and documentation
.agents/skills/ Repository-local coding workflows
```

## Develop Core

Use Python 3.11+. From the repository root on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests tools
.\.venv\Scripts\python.exe -m mypy src/fpg_core
```

On Ubuntu, install Python and its venv support, then:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python -m ruff check src tests tools
.venv/bin/python -m mypy src/fpg_core
```

Core is a library; call its supported feature functions from your application:

```python
from fpg_core.floor_plan_solver import build_default_profiles

profiles = build_default_profiles()
print(profiles.initial)
```

For installation in a consumer environment, omit the development extras:
`python -m pip install .` from a checkout, or install a built wheel. Start with the
[consumer API guide](docs/API_GUIDE.md) and [feature documentation](docs/feature_documentations/README.md)
for complete inputs, outputs, configuration, and examples.

## Develop and run Lab

Lab uses its own environment. You do not need to activate Core's environment.
From the repository root on Windows:

```powershell
cd fpg-lab
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
.\.venv\Scripts\python.exe -m fpg_lab
```

On Ubuntu:

```bash
cd fpg-lab
bash scripts/setup_ubuntu.sh
.venv/bin/python -m fpg_lab
```

Open **http://127.0.0.1:8080**. Setup installs Lab and local Core into
`fpg-lab/.venv`, creates Lab's `.env` if absent, and initializes its starter records.
Core edits are visible immediately through the editable installation.

With the UI stopped, run a small headless experiment from `fpg-lab/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_experiment --flow p01a --trial-count 1 --database-url sqlite:///./data/smoke.db --output data/p01a.json
.\.venv\Scripts\python.exe -m scripts.verify_fpg_core
.\.venv\Scripts\python.exe -m pytest
```

Ubuntu uses `.venv/bin/python` for the same commands. Lab owns its `.env` and local
`data/` directory. See [Lab's README](fpg-lab/README.md) for setup, resets, other
experiments, and static checks.

## Maintain the repository

From the root, using the Core interpreter:

```bash
python tools/check_docs.py
python tools/generate_public_api_manifest.py --check
```

Use the explicit `.venv` interpreter above if `python` is not your Core environment.
Read the [documentation map](docs/README.md), [verification guide](docs/development/verification.md),
[changelog](docs/history/CHANGELOG.md), or [agent instructions](AGENTS.md) as needed.
