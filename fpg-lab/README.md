# FPG Lab

Local experiments for this repository's `fpg-core`, with NiceGUI, Plotly, and SQLite.
One Python process owns the UI, experiment queue, and database. The same runtime
runs headlessly. Lab consumes public Core APIs; Core contains no Lab dependencies.

## Setup and start

Python 3.11+ is required. From `fpg-lab/` on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
.\.venv\Scripts\python.exe -m fpg_lab
```
or if already in the environment
```
python -m fpg_lab
```

On Ubuntu with Python and venv support installed:

```bash
bash scripts/setup_ubuntu.sh
.venv/bin/python -m fpg_lab
```

Open **http://127.0.0.1:8080**. Setup creates `fpg-lab/.venv`, installs this Lab and
the parent Core in editable mode, creates `.env` if absent, validates Core imports
and the starter profile, and seeds an active configuration and four request templates.
There is no separate Core checkout option. The root Core development environment
is independent; no environment activation is required for these commands.

After setup, only the start command is needed. Stop with Ctrl+C; shutdown waits for
an active Core stage to finish. Do not run two Lab processes against one database:
startup recovery assumes a single owner and marks abandoned runs interrupted.

For VS Code, follow the [interpreter setup](../README.md#vs-code-interpreters)
to give Pylance Lab's environment separately from Core.

## Configuration and data

`.env` and configured relative SQLite paths resolve from `fpg-lab/`, independent of
working directory. Defaults in the tracked [.env.example](.env.example) are:

```dotenv
FPG_LAB_DATABASE_URL=sqlite:///./data/fpg_lab.db
FPG_LAB_AUTO_CREATE_SCHEMA=true
FPG_LAB_MAX_BACKGROUND_WORKERS=1
FPG_LAB_HOST=127.0.0.1
FPG_LAB_PORT=8080
```

The environment file, local databases, exports, caches, and environments are ignored.
`seed/` holds tracked research policy and example requests. Lab profile schema 6
maps to Core aggregate schema 2; they are distinct formats. Old Lab schemas are
rejected. There is no automatic migration of prior databases/profiles.

Normal setup preserves `.env` and experiment history, but upserts the named starter
profile and four shipped templates, and activates the starter profile. To rebuild local tables deliberately,
stop Lab and use `-Fresh Yes` on Windows or `--fresh Yes` on Ubuntu. This destroys
Lab records in the configured database. Review `.env` before resetting.

The current seed is the single starter source for setup, new drafts and headless
defaults. To validate and normalize it after an edit, from `fpg-lab/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.export_default_core_config
.\.venv\Scripts\python.exe -m scripts.verify_fpg_core
```

This export does not automatically adopt every new Core default. Review public
Core changes and update Lab policy consciously. Example setbacks are research
inputs, not regulatory guidance. Resave/reseed a changed profile when you want it
used; stored experiment snapshots remain unchanged.

## Research workflow

- Configurations: create a starter draft, duplicate, edit JSON, validate through
  Python, save, activate or delete profiles. Reset restores the loaded draft.
- Templates: save requests and load them into experiments; Core preprocessing
  checks them against the selected profile.
- P01A searches and scores candidate maps.
- After a P01A run stops, replay saved hints with play/pause, speed, scrubbing,
  adjustable onion skins, room filtering, an animated single-room placement heatmap,
  and all-trials or improvements-only views. Trial IDs seek the same canvas;
  evaluator progression charts follow its playhead. Keep
  **Store debug data** enabled. Start with 100 trials, then try 500; raw/cleaned
  hints and evaluator contributions help inspect guidance before tuning settings.
  Rooms appear in an aligned checkbox grid. **Select one** makes room choices
  exclusive; **Select all / Deselect all** toggles the complete set and selecting
  all turns off exclusive selection. Playback/settings and room controls share
  a compact row above the canvas on wide screens and stack on narrow screens.
- P01B accepts manual room/hallway hints, then runs initial solving, refinements,
  post-processing, openings and final scoring.
- P01C branches into floor-plan generation when candidate score is strictly greater
  than its configured threshold; branch failure does not stop candidate search.

Run pages show live status, counters, scores, stored stages, provenance and errors.
Plotly supports zoom/pan/hover, legend toggles and image export; geometry uses equal
axes and project units. History is paged rather than loading all trial geometry.
The [P01 guide](docs/experiments/p01.md) explains shared behavior and retention.
"Store debug data" controls detailed recording: P01A skips individual trial records
when disabled; P01C retains score/status metadata. Termination is cooperative at
stage boundaries. Interrupted runs are not automatically resumed.

## Research request templates

Setup installs these four templates. Each includes a living room, kitchen, dining
room and shared bathroom. Attached bathrooms are additional rooms paired by Core
preprocessing policy; these are request templates, not separate system profiles.

| Template | Bedrooms | Attached bathrooms | Other rooms | Maximum floor limits |
| --- | --- | --- | --- | --- |
| `two-bedroom-research-template` | 2 | 0 | — | 180 × 140 |
| `two-bedroom-garage-veranda` | 2 | 0 | Garage, veranda | 200 × 160 |
| `two-bedroom-garage-ensuite` | 2 | 1 | Garage | 200 × 160 |
| `three-bedroom-garage-two-ensuites` | 3 | 2 | Garage | 220 × 180 |

Limits use project units (examples use 10 units per metre). Preprocessing chooses
the actual floor within those limits using the selected profile and room sizes;
the limits do not force that footprint. Select a template from **Load a template**
when creating an experiment; saved runs keep their original request snapshots.

To add the three new presets to an existing installation without reseeding its
configuration, run from `fpg-lab/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_db --floor-plan-template seed/floor_plan_template.garage_veranda.json --floor-plan-template seed/floor_plan_template.two_bedroom_ensuite.json --floor-plan-template seed/floor_plan_template.three_bedroom_ensuites.json
```

## Headless experiments

From `fpg-lab/`, use a separate database when the UI is running:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_experiment --flow p01a --trial-count 1 --database-url sqlite:///./data/smoke.db --timeout 60 --output data/p01a.json
.\.venv\Scripts\python.exe -m scripts.run_experiment --flow p01b --database-url sqlite:///./data/smoke.db --timeout 120 --output data/p01b.json
.\.venv\Scripts\python.exe -m scripts.run_experiment --flow p01c --trial-count 1 --threshold 0 --database-url sqlite:///./data/smoke.db --timeout 120 --output data/p01c.json
```

Ubuntu uses `.venv/bin/python`. The runner supplies a small request and matching
P01B hints. Use `--request request.json`, `--hints hints.json` for a custom P01B
request, and `--configuration-id` for a saved profile. `--threshold` creates a
separate scenario profile without changing an existing one. Explicit input/output
paths and a relative database override are relative to the invoking directory;
use the documented Lab working directory. Run `--help` for other options.

Inspect both experiment status and `floor_plan_runs[*].status` / `error_data`.
Candidate completion alone does not establish floor-plan success. These are real
experiments and may be infeasible; they are separate from automated checks.

## Checks and development

From `fpg-lab/`, with its interpreter:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_fpg_core
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check fpg_lab scripts tests
.\.venv\Scripts\python.exe -m mypy fpg_lab scripts
```

The verifier checks the local Core origin and public configuration/import contracts
without running an experiment. Choose focused tests and use real experiments only
when relevant. See [development](docs/DEVELOPMENT.md), the [documentation map](docs/README.md),
[agent instructions](AGENTS.md), and [repository verification policy](../docs/development/verification.md).
