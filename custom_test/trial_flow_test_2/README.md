# Trial Flow Test 2

This manual integration trial exercises these installed-package features with a
realistic typed floor-plan request:

```text
Floor Plan Solver (initial, refinement A, refinement B profiles)
    -> Floor Plan Post-Processing
    -> Floor Plan Openings
    -> Floor Plan Scoring
```

This orchestration exists only as a consumer example. Each package feature can be
used independently.

## Run from a source checkout

From the repository root, with the project environment activated:

```powershell
python custom_test/trial_flow_test_2/run_trial_flow.py
```

Or invoke the checked-in Windows virtual environment directly:

```powershell
.\.venv\Scripts\python.exe custom_test\trial_flow_test_2\run_trial_flow.py
```

The runner adds `src` to `sys.path`, reads `input.json`, prints progress, and
overwrites `result.json` only after every stage finishes successfully.

## Run against an installed package

Install the package into the active Python 3.11+ environment, then run the same
command. The script prefers the checkout's `src` directory when it exists; to test
only an installed wheel, copy this folder outside the repository before running it.

## Files

- `input.json` contains the floor specification, placement hints, and deterministic
  solver runtime settings.
- `run_trial_flow.py` constructs public domain contracts and calls only public
  feature APIs.
- `result.json` is generated output containing DEBUG executions and a summary.

The fixture uses one search worker and a fixed random seed for repeatability. Exact
solver geometry and timing can still vary when OR-Tools or platform versions change;
the assertions concern supported statuses and contracts, not a byte-identical plan.
