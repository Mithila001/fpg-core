# FPG Lab

Local experiments for this repository's `fpg-core`, with NiceGUI, Plotly, and SQLite.
One Python process owns the UI, experiment queue, and database. The same runtime
runs headlessly. Lab consumes public Core APIs; Core contains no Lab dependencies.

## Setup and start

Python 3.11+ is required. From `fpg-lab/` on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
.\.venv\Scripts\python.exe run_lab.py
```
or if already in the environment
```
python run_lab.py
```

On Ubuntu with Python and venv support installed:

```bash
bash scripts/setup_ubuntu.sh
.venv/bin/python run_lab.py
```

Open **http://127.0.0.1:8080**. Setup creates `fpg-lab/.venv`, installs this Lab and
the parent Core in editable mode, creates `.env` if absent, validates Core imports
and the starter profile, and seeds an active configuration and five request templates.
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
rejected. Current-schema saved profiles are upgraded at startup for 10-unit hallways
and the new door default; stored experiment snapshots are not modified.

Normal setup preserves `.env` and experiment history, but upserts the named starter
profile and five shipped templates, and activates the starter profile. To rebuild local tables deliberately,
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
- E01A explores walking paths and traffic coverage on four preset plans. See the
  [E01 guide](docs/experiments/e01.md).
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
- P01B imports a P01A cleaned candidate preset, then runs independent initial solves,
  repeated refinements, post-processing and final scoring without openings.
- P01C repeats the P01B flow, then generates openings and scores the final plan.
  Copy a final plan from the run page and paste it into E01A.

P01 run pages show live status, counters, scores, stored stages, provenance and errors.
Plotly supports zoom/pan/hover, legend toggles and image export; geometry uses equal
axes and project units. History is paged rather than loading all trial geometry.
The [P01 guide](docs/experiments/p01.md) explains shared behavior and retention.
"Store debug data" controls detailed recording: P01A skips individual trial records
when disabled. P01B and P01C retain their iteration stages. Termination is cooperative at
stage boundaries. Interrupted runs are not automatically resumed.

## Research request templates

Setup installs these five templates. Full Template (Default) is selected when
opening an experiment if the template is present. Each includes a living room,
kitchen and shared bathroom; attached bathrooms are additional rooms paired by
Core preprocessing policy.

| Template | Bedrooms | Attached bathrooms | Other rooms | Maximum floor limits |
| --- | --- | --- | --- | --- |
| Full Template (Default) | 3 | 1 | Dining room, veranda, garage | 240 ? 180 |
| Minimal | 1 | 0 | Veranda | 180 ? 135 |
| Super Minimal | 1 | 0 | ? | 160 ? 120 |
| Average | 2 | 0 | Dining room, veranda, garage | 220 ? 165 |
| Big Plan | 4 | 2 | Dining room, veranda, garage | 280 ? 210 |

Limits use project units (examples use 10 units per metre); all request a 4:3
aspect ratio. Preprocessing chooses the actual floor within those limits. Saved
runs keep their original request snapshots. Setup upserts these names and does not
remove older templates from an existing database.

## Headless experiments

From `fpg-lab/`, use a separate database when the UI is running:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_experiment --flow p01a --trial-count 1 --database-url sqlite:///./data/smoke.db --timeout 60 --output data/p01a.json
.\.venv\Scripts\python.exe -m scripts.run_experiment --flow p01b --preset-id 1 --database-url sqlite:///./data/smoke.db --timeout 120 --output data/p01b.json
.\.venv\Scripts\python.exe -m scripts.run_experiment --flow p01c --preset-id 1 --iterations 1 --database-url sqlite:///./data/smoke.db --timeout 120 --output data/p01c.json
```

Ubuntu uses `.venv/bin/python`. Create a P01B preset in the UI before using its ID
in the headless runner. P01A accepts `--request request.json`; all flows
accept `--configuration-id` for a saved profile. Explicit input/output
paths and a relative database override are relative to the invoking directory;
use the documented Lab working directory. Run `--help` for other options.

Inspect both experiment status and `floor_plan_runs[*].status` / `error_data`
or `iterations[*].status` / `error` for P01B and P01C.
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
