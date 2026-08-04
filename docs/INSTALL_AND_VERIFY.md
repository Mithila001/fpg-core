# Installation and Verification

## Replace an installed development copy

From the repository root:

```bash
python -m pip uninstall -y fpg-core
python -m pip install -e ".[dev]"
```

For a runtime-only environment:

```bash
python -m pip install .
```

## Verify

```bash
python -c "import fpg_core; print(fpg_core.__version__)"
python -m pytest
python -m ruff check src tests
python -m mypy src/fpg_core
```

Expected package version:

```text
0.2.0
```

## Build a distributable package

```bash
python -m pip install build
python -m build
python -m twine check dist/*
```

## Update a consuming project

After updating its code for the 0.2.0 contracts:

```bash
python -m pip uninstall -y fpg-core
python -m pip install -e /absolute/path/to/fpg-core
python -m pytest
```

For applications that pin versions, change the dependency to the produced 0.2.x wheel or source distribution.
