# Full Flow Custom Test

Package-local manual integration test for `fpg-core`. It calls the package's public APIs directly; there is no HTTP server, job queue, SSE layer, database, or application schema involved.

## Run

From the repository root, with the normal project virtual environment active:

```bash
python custom_test/full_flow/run_full_flow.py
```

The runner automatically writes the next output as:

```text
custom_test/outputs/full_flow_1.json
custom_test/outputs/full_flow_2.json
...
```

An explicit round can be requested without overwriting an existing file:

```bash
python custom_test/full_flow/run_full_flow.py --round 12
```

The runner exits with `0` only when the full flow completes and all final validations pass. A failed stage still produces a JSON file containing the successful earlier stages and the traceback.

## Flow

```text
buildable land
  -> usable land
  -> preprocessing
  -> candidate search
       -> candidate circulation + candidate scoring per trial
  -> selected candidate circulation (DEBUG)
  -> selected candidate scoring (DEBUG)
  -> initial CP-SAT generation
  -> refinement A
  -> refinement B
  -> post-processing
  -> opening generation
  -> final floor-plan scoring
  -> custom geometry/opening validations
```

All feature calls use public package APIs. The output also contains visualization snapshots for the selected candidate and each floor-plan stage.

The scenario explicitly adds `kitchen <-> dining_room` to the opening policy because the same scenario declares that relationship as hard during preprocessing. Opening room-pair policy is consumer-owned, so the test must keep these two configurations compatible.

## View

Open `viewer.html` directly in a browser and choose one of the generated `custom_test/outputs/full_flow_*.json` files.

The viewer provides:

- selected candidate hint/grid visualization;
- initial, refinement A, refinement B, post-processing, openings, and final floor-plan snapshots;
- doors and windows;
- room labels and dimensions;
- stage status/timing;
- validation results;
- candidate trial scores;
- raw JSON for deeper inspection.

`custom_test/outputs/.gitignore` keeps generated JSON results out of Git while retaining the directory itself.
