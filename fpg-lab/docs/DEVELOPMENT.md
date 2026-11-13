# Lab development

## Ownership and execution

Lab is one Python application: NiceGUI UI or headless scripts -> `LabRuntime` ->
services and background flows -> public Core APIs -> stored results -> plots/UI.
`runtime.py` imports without NiceGUI and is a context manager for scripts. Core
owns generation algorithms; Lab owns policy, orchestration, persistence, and input
translation. No server API or Node build is required.

Run one process per database. Startup marks abandoned active experiments interrupted;
it cannot distinguish another process's active jobs. Workers default to one and
UI reload is enabled through `run_lab.py`; NiceGUI reload does not support
`python -m fpg_lab`. File changes restart the server; active work may be
interrupted during shutdown. Each operation owns its session. Shutdown requests
cooperative termination, waits for an active Core stage to return, then disposes
the database. Saved snapshots and hashes describe submitted inputs, not later edits.

Keep pipeline behavior in `flows/`, persistence operations in `services/`, and
resource ownership in the runtime. UI callbacks submit work and inspect materialized
snapshots. Workers never access page elements. Use `db_call` for short session work
and `run.io_bound` for potentially expensive preprocessing/submission; keep page
drafts and selections local to their page and stop timers at terminal states.

## UI page ownership and result layout

Follow the [Lab UI standards](UI_STANDARDS.md) for every new or updated experiment.
The main listing is `ui/pages.py`; setup and result route registration is in
`ui/experiments.py`; E01A and P01B/C have their own page modules and P01A's
interactive replay is in `ui/replay.py`. The global header/theme and CSS belong
in `ui/components.py`. The shared desktop result workspace is
`ui/result_layout.py::ResultWorkspace`.

Create distinct setup and run-result routes. Results should target a single run,
using a persistent run ID only when that experiment saves its history. Populate
`ResultWorkspace`'s main-view and contextual-sidebar containers per view; do not
force a universal control schema on experiments. Use a large resizable canvas as
default when present, and move alternative charts/tables/diagnostics into primary
views rather than stacking them below the canvas. Independently scroll both
workspace columns. Keep result-page state local and preserve zoom/selection
through polling; avoid rebuilding plots when snapshots have not changed.

E01A is intentionally ephemeral: a one-time per-tab NiceGUI memory handoff
transfers the result from setup to its dedicated result page. The result page
consumes that handoff, so leaving/reloading loses it. There is no database run
or history; other P01 experiments keep saved-run behavior.

## Extend an experiment

Read the relevant [family document](experiments/p01.md) and inspect current callers.
Reuse an existing flow for different configurations; create a new flow when its
execution behavior differs. A new family gets one focused document and navigation
entry, without a generic registry framework.

Validate Lab-controlled IDs, ranges, finite coordinates, and relationships at the
input boundary. Use Core's shared types for Core-owned values. E-family fixtures may mirror their serialized shape
without invoking Core features. Map saved Lab JSON
through `integrations/fpg_core/`; never import private Core modules or duplicate
algorithms. Reuse applicable worker, session, snapshot, error, and serialization
patterns. `to_jsonable` retains new Core output fields without a second response
DTO schema. Register the input/service in the runtime, add UI and optional headless
dispatch, and keep plots independent of NiceGUI with equal geometry axes, explicit
project units, and consistent room colors.

A different pipeline can have its own runner. P01-specific stage ordering and
shared records are described in the family guide, not universal requirements.
Leave a small runnable regression check for changed nontrivial behavior. Choose
checks from [verification](../../docs/development/verification.md), including real
experiments only when needed. Keep mock signatures compatible with production
keyword arguments and validate Pydantic models explicitly at their boundaries.

## Configuration and local files

The editable repository is the supported Lab installation. `seed/` contains the
single current starter profile. New drafts, setup and headless defaults use it.
The codec validates Lab schema 6 and maps it to Core aggregate schema 2; those
versions describe different models. Old Lab schemas fail validation. Existing schema 6
profiles are migrated at startup to the 10-unit hallway rule and 10-unit default doors;
stored experiment snapshots are preserved. Narrow hallway presets must be regenerated.
Core defaults and Lab policy may differ intentionally. Review changed public Core
settings before updating a research profile; the seed-export script validates and
normalizes the starter, it does not discover new Core defaults automatically.

`.env` and configured relative SQLite paths resolve from the Lab directory,
independent of working directory. Explicit CLI paths and `--database-url` overrides
are interpreted by their command; run documented commands from `fpg-lab/`.
Use a separate database for checks while the UI runs. CLI exports are written
atomically after collecting records through the same runtime used by the UI.

Keep data, caches, environments and generated outputs out of Git. Keep
`.env.example`, seeds, docs and repository skills tracked. Update the relevant
family guide and Lab docs alongside code; shared Core contracts remain in Core docs.
