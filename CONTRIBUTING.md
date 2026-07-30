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
ruff check .
mypy
pytest
python -m build
```

Run all checks before opening a pull request. Ruff covers formatting-independent
lint rules and import ordering; mypy checks the public typed package.

## Architectural rule

Production code under `src/fpg_core` must not import server packages, FastAPI, Pydantic API models, artifact storage, application logging, routes, services, pipelines, or streaming infrastructure.
