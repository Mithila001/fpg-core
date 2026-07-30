# Contributing

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Checks

```bash
pytest
python -m build
```

## Architectural rule

Production code under `src/fpg_core` must not import server packages, FastAPI, Pydantic API models, artifact storage, application logging, routes, services, pipelines, or streaming infrastructure.
