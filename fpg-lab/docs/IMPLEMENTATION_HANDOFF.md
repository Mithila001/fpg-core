# FPG Lab implementation handoff

## Phase 1

The working tree starts at planning baseline `dcc8de74457fc4202ebb9810031f2c1ab58b3c89`
on `feature-b`. SQLite revision **1** uses `PRAGMA user_version`. The Lab
profile uses schema **6** and Core's aggregate uses schema **2**. Core 0.2.0
validated seed hash `99b3fa87563a01458621f7fdcf5de5c7d0c0a7f2fd64007a9a7ab25a9400c06a`.

- `fpg_lab.database.maintenance` supplies `status`, `migrate`, `seed`, `profiles`,
  `records`, `record`, `export` and `reset`. `scripts.lab_db` exposes these
  operations. Revision 1 adopts the reviewed SQLite schema and evolves the
  profiles in a transaction.
- `fpg_lab.services.common.SystemConfigurationService` supplies `list`, `get`,
  `resolve`, `for_flow`, `create`, `duplicate`, `save`, `save_section`,
  `activate` and `validate`. `CoreConfigCodec.validate_for_flow` maps the
  needed sections and `decode_floor_scoring` maps the E02B snapshot.
- E02A, E02B, E03A, P01A/B/C, quick hint search, setup UI and the headless
  runner use the selected profile or the active profile. E03A's typed section
  lives in `fpg_lab.e03a_config`. Persistent runs capture the profile ID,
  hash, and effective inputs. E01A stays driven by prepared plans.
- Removed the three live experiment config files, automatic schema creation
  and startup profile transforms, the Core refinement fallback, legacy
  cleaned-candidate specification reconstruction, and the old database
  scripts. Startup retains interrupted-job recovery.
- The Lab docs route through the [catalogue](EXPERIMENTS.md),
  [architecture](ARCHITECTURE.md), [development](DEVELOPMENT.md),
  [UI standards](UI_STANDARDS.md), [glossary](../GLOSSARY.md) and family notes.

## Isolated startup and fixtures

From `fpg-lab/` with the Lab environment active, choose an unused file.

```powershell
$db = 'sqlite:///./data/phase1-handoff.db'
python -m scripts.lab_db --database-url $db status --json
python -m scripts.lab_db --database-url $db migrate --dry-run --json
python -m scripts.lab_db --database-url $db migrate --json
python -m scripts.lab_db --database-url $db seed --json
python -m scripts.lab_db --database-url $db profiles validate --all --json
python -m scripts.lab_db --database-url $db profiles list --json
$env:FPG_LAB_DATABASE_URL = $db
$env:FPG_LAB_PORT = '8081'
python run_lab.py
```

Expect empty status before apply, one active `research-default`, five seeded
templates and validation with zero errors. Repeating seed creates zero rows.
Stop this Lab before resetting the fixture.

The [SQLite checks](../tests/test_phase1_database.py) create all success, conflict
and reset fixtures automatically under pytest's temporary directory. To create
persistent copies of the two revision-0 fixtures for manual CLI checks, run
the following from `fpg-lab/`.

```powershell
@'
import sys
from pathlib import Path
from tempfile import mkdtemp
sys.path.insert(0, "tests")
from test_phase1_database import reviewed_database
root = Path(mkdtemp(prefix="phase1-fixtures-", dir="data")).resolve()
for name, conflict in (("upgrade.db", False), ("conflict.db", True)):
    reviewed_database(root / name, conflict=conflict).dispose()
print(root.as_posix())
'@ | python -
```

Use the printed paths to target each database. The upgrade retains primary ID
31 and active custom ID 42, adds missing rules and retains the custom 17-second
refinement limit. The conflict has a weight of 99 and stays at revision 0.
The reset test creates E02 runs and a P01 experiment with a trial, a floor-plan
run and an iteration, plus reusable profile, template, preset and plan records.
Runs reset removes six run rows and retains reusable rows. All reset reseeds
the selected fixture. Rollback checks inject a failure after DDL and profile
flush and before recording the revision.

## Verification

From `fpg-lab/` with the Lab environment active.

```powershell
python -m scripts.verify_fpg_core
$scratch = './data/phase1-pytest-' + [guid]::NewGuid().ToString('N')
python -m pytest -q -p no:cacheprovider --basetemp $scratch tests/test_phase1_database.py tests/test_e02a.py tests/test_e02b.py::test_storage_snapshot_recovery_and_measurements tests/test_e03a.py::test_refresh_and_explicit_save tests/test_p01b_replacement.py tests/test_lab.py::test_flows_and_persistence tests/test_repository_integration.py tests/test_quick_hint.py::test_runtime_quick_search_uses_selected_profile -k 'not real_initial_solver'
python ../tools/check_docs.py
```

From the repository root with the Core environment active.

```powershell
python tools/generate_public_api_manifest.py --check
$scratch = './fpg-lab/data/phase1-docs-' + [guid]::NewGuid().ToString('N')
python -m pytest -q -p no:cacheprovider --basetemp $scratch tests/contracts/test_repository_tools.py
```

The focused Lab suite passed 28 tests, and both repository tool tests passed.
The isolated CLI smoke covered migration and dry run, seed, profile
list/show/duplicate/activate/validate, record list/show/export and both reset
scopes. Isolated NiceGUI startup returned HTTP 200 for the index,
configurations, E02B, E03A and P01A/B/C setup routes. Reload was disabled for
the smoke process. Reviewed the profile selectors, save/reload handlers and
placement of controls. Changed-file Ruff and changed-module mypy passed.
Full Lab pytest, full-tree static checks, a comprehensive CLI matrix, browser
regression and real solver searches are deferred to Phase 4. CI remains configured.

## Configured development database

The configured target is `fpg-lab/data/fpg_lab.db`. Dry run recognized
revision 0 and proposed promoting primary ID 1. The active custom profile
ID 2, `research-profile 2`, contains solver soft weights above the current
maximum of 10 and the retired inward-recess `maximum_length` setting. The
current evaluator has no equivalent absolute depth cap. A Python process was
listening on the configured port 8080. The live database is still at revision
0 with its existing profiles and data. Resolve the custom policy values
deliberately and stop Lab before applying maintenance. Dry run lists the paths.

From `fpg-lab/` with the Lab environment active.

```powershell
python -m scripts.lab_db --database-url sqlite:///./data/fpg_lab.db migrate --dry-run --json
python -m scripts.lab_db --database-url sqlite:///./data/fpg_lab.db migrate --json
python -m scripts.lab_db --database-url sqlite:///./data/fpg_lab.db seed --json
python -m scripts.lab_db --database-url sqlite:///./data/fpg_lab.db profiles validate --all --json
```

Phase 2 can use an isolated revision-1 fixture. Keep evolution in maintenance,
reuse the profile service for submission routes and preserve snapshot provenance
as lifecycle code changes. Update this handoff with verified changes.

## Phase 2 result

Revision 2 removes `fpg_p01_floor_plan_run` and P01B/C runs without preset
snapshots. Migration dry run reports `removed_floor_plan_runs` and
`removed_legacy_experiments`; apply is transactional and retains profiles,
templates, presets, saved plans and current runs. The Phase 1 section above is
a historical record: new databases now initialize directly at revision 2.
Stop Lab before maintenance. The configured development database remains
untouched; its Phase 1 policy conflicts still need deliberate resolution before
migration.

Shared error/result helpers are `core.results`, row materialization is
`database.serialization.row_document`, portable map validation and hint
conversion are `integrations.fpg_core.hint_map`, portable plan decoding is
`integrations.fpg_core.floor_plan`, and refinement preparation is
`integrations.fpg_core.solver`. P01 trial and E02A stage export assembly stay
in their respective owners. Historical floor-plan summary columns remain inert in
the experiment table to avoid rebuilding it; active views no longer use them.
`workers.executor.BackgroundExecutor` accepts work
functions independently of P01, and workers own their sessions. Removed the
unreachable P01B preview, the obsolete E03A result route, old floor-plan branch
route/model/queries, historical
P01C handling and old `e02b_input` module.

E02A and P01B/C resolve the selected profile at submission. Optional initial
time/seed overrides and the effective initial/refinement configurations are
recorded in the snapshot; retries use the saved E02A configuration. P01C scores
the openings result, while E02B stores official results and diagnostics separately.
Failure of an individual case or iteration preserves previously stored stages.
Each E flow remains independent of a mandatory persisted job or pipeline.

### Focused verification completed

From `fpg-lab/` with its environment active, the following passed **29 tests**:

```powershell
$scratch = './data/phase2-focused-' + [guid]::NewGuid().ToString('N')
python -m pytest -q -p no:cacheprovider --basetemp $scratch tests/test_phase1_database.py tests/test_e02a.py::test_prepared_maps_and_selected_profile_snapshot tests/test_e02a.py::test_invalid_config_and_independent_failures tests/test_e02b.py::test_portable_stages_accept_architectural_defects tests/test_e02b.py::test_storage_snapshot_recovery_and_measurements tests/test_p01b_replacement.py::test_export_and_independent_iterations tests/test_p01b_replacement.py::test_failed_refinement_keeps_initial_and_continues tests/test_p01b_replacement.py::test_scoring_failure_retains_post_processed_plan tests/test_p01b_replacement.py::test_p01c_scores_the_opening_plan_and_keeps_it_on_score_failure tests/test_p01b_replacement.py::test_p01c_opening_failure_stops_iteration tests/test_lab.py::test_flows_and_persistence tests/test_lab.py::test_submission_failure_and_invalid_input tests/test_lab.py::test_termination_and_queued_job tests/test_lab.py::test_shutdown_terminates_active_and_queued_jobs tests/test_lab.py::test_immediate_completion_no_deadlock tests/test_quick_hint.py
python -m scripts.verify_fpg_core
```

Changed-module imports and changed-file Ruff also passed. An isolated seeded
revision-2 database and a reload-disabled NiceGUI startup returned HTTP 200 for
the index and all seven `/experiments/<id>` setup routes. This is a route smoke,
not a rendered interaction review. The original
larger P01B/C smoke input hit its five-second initial limit; its parent status
was completed but nested iterations failed. It is not the success fixture.

### Prepared smoke catalogue

Run nodes separately with `python -m pytest -q -p no:cacheprovider --basetemp
<new-workspace-path> <node>` from `fpg-lab/`. Use a fresh basetemp for each
invocation. Budget 120 seconds overall, with a 60-second wait deadline per
background run; cancellation is cooperative and may wait for the current Core
stage. Each row below was executed in Phase 2. No external DB IDs are guessed:
pytest creates an isolated database, migrates and seeds it, and captures IDs
returned by services.

| Experiment | Node | Type and expected output |
| --- | --- | --- |
| E01A | `tests/test_e01a.py::test_concave_room_uses_walkable_interior_point` | Real Lab traffic: one valid veranda-to-living route. |
| E02A | `tests/test_lab_smoke.py::test_real_e02a_solver_case` | Real Core solve/post-process/score; input loading alone is substituted; completed case, plan and score. |
| E02B | `tests/test_e02b.py::test_storage_snapshot_recovery_and_measurements` | Real Core official scoring and diagnostic evaluations; official critical gate fails and two skipped-evaluator diagnostics are separate. |
| E03A | `tests/test_e03a.py::test_dimension_gaps_and_axis` | Real exact Lab analysis: compatible dimensions and supported areas. |
| P01A | `tests/test_lab_smoke.py::test_real_p01a_candidate` | Real Core preprocessing, search, circulation and scoring; completed trial with candidate and score. |
| P01B | `tests/test_lab_smoke.py::test_real_p01_generation[p01b]` | Real Core initial solve, refinement, post-processing and score; completed iteration and plan. |
| P01C | `tests/test_lab_smoke.py::test_real_p01_generation[p01c]` | Same real steps plus openings before scoring; completed iteration with openings stage and score. |

The small success fixture is `tests/fixtures/small_hint_map.json`: one 20-by-20
room, 10 units per metre. The isolated smoke profile clears solver hard/soft
rules for that fixture, uses seed 42, one solver worker and two-second initial
and refinement limits. This is a connectivity check, not a representative house
quality result. P01A uses `scripts.run_experiment.sample_request` and one trial.
The E02B test constructs its own flawed but structurally valid plan and profile.
The focused E02A/P01B failure tests above mock expensive stages and test
orchestration; they are not substitutes for the real nodes.

For manual inspection, create a fresh database as in Phase 1, then list IDs with
`python -m scripts.lab_db --database-url <URL> records <table> --limit 25 --json`.
Use `record <table> <id> --json` or `export <table> <id> --output <new-path>`
for one record. E02A cases are in its run's `cases` JSON; select the case or
fields from that single record/export. P01B/C iterations are rows in
`fpg_p01b_iteration`. The headless runner supports P01 only and bounds each
returned trial/iteration collection to 100 while reporting counts.

Full Lab pytest, all-page browser regression, full-tree lint/type checks, broad
documentation audit and research sweeps remain deferred to Phase 4. Phase 3 may
now proceed using the current services and the isolated fixtures above.

## Phase 3 result

E02B setup uses a dominant plan preview and a context panel with the selected
profile, Run, saved plans and secondary import, scoring-settings and history
dialogs. Findings and measurements use bounded visible radio lists. Official
scores and critical gates remain separate from independent diagnostics.
Configuration and template pages use a visible record navigator and a larger
editor. E01A and P01B/C use the shared setup proportions; E02A exposes hint
choices and case selection. E03A embeds the shared workspace without nesting
top-level headers, retaining its direct analytical editor. Shared result panes
size to the available page height, scroll independently and resize plots when
views change. Room categories use `visualization.figures.ROOM_COLORS` across
candidate, plan and replay views; labels distinguish instances.

### Reproduce the UI review

From `fpg-lab/`, choose a new isolated database and initialize it:

```powershell
$db = 'sqlite:///./data/phase3-review-new.db'
python -m scripts.lab_db --database-url $db migrate --json
python -m scripts.lab_db --database-url $db seed --json
python -m scripts.lab_db --database-url $db profiles list --json
$env:FPG_LAB_DATABASE_URL = $db
@'
import sys
sys.path.insert(0, "tests")
from test_e02b import portable_plan
from fpg_lab.database.session import Database
from fpg_lab.flows.e02b import save_layout
from fpg_lab.core.settings import get_settings
db = Database(get_settings().database_url)
with db.session_factory() as session:
    print("Saved plan ID:", save_layout(session, "Ring and notch", portable_plan()))
db.dispose()
'@ | python -
$env:FPG_LAB_PORT = '8081'
python run_lab.py
```

Use the printed plan ID; do not assume it. Stop Lab before resetting this
fixture. Open `/experiments/e02b`, select that plan and the active profile,
then Run. The resulting run page should show the official failed critical gate
and independent diagnostics in the Overview. Select Geometry integrity and a
finding to highlight the overlap; select Room size consistency to see official
`skipped` alongside diagnostic `completed`. On `/configurations`, duplicate a
profile, Save and Activate; edits left unsaved disappear after switching records
and must not change a prior run snapshot. On `/experiments/e03a`, load that
profile, edit Bedroom count, apply and save; the Rooms table and compatible
analysis update, and stale saves are rejected by the profile hash.

The review used a separate seeded revision-2 database and a reload-disabled
server on localhost port 18932. It exercised the E02B sequence above, including
scoring-settings validation, profile duplicate/save/activate and unsaved draft
reload, and E03A edit/analyze/save. It also opened E01A and inspected a completed
small-fixture E02A case with visible stage choices. The previously submitted E02B run retained
its original profile ID. Result layout was checked at 1280 x 650 as well as the
ordinary desktop viewport; its main area and sidebar remained within the page.
Captured review screenshots: `.playwright-mcp/page-2026-11-27T12-28-35-434Z.png`
(E02B finding) and `.playwright-mcp/page-2026-11-27T12-30-54-207Z.png` (E03A,
short viewport). Screenshots are local review artifacts. The focused replay,
E03A save/conflict, E02B scoring and serialization checks passed (9 tests).

Deferred to Phase 4: full Lab suite, complete browser/viewport and keyboard
matrix, long-list behavior, all replay/export/termination paths and full-tree
static checks. No research sweeps were run.

## Phase 4 verification result

Reviewed HEAD `6a4e7647e00dd753aab9505c9390b56a03c85c0f` with the Phase 1–3
worktree changes already present. Environment: Lab `.venv`, Python 3.13.2,
Lab 1.0.0, Core 0.2.0 and NiceGUI 3.17.1. Automated CLI and browser databases
were isolated under
`C:\Users\user\AppData\Local\Temp\fpg-phase4-42e82247a66b481fa5bbcab93abc04ea`;
the browser server used port 18933 and one background worker. The research DB
and `.env` were not read or modified.

From `fpg-lab/`, these explicit-URL commands returned exit code 0:

```powershell
.\.venv\Scripts\python.exe -m scripts.lab_db --database-url sqlite:///C:/Users/user/AppData/Local/Temp/fpg-phase4-42e82247a66b481fa5bbcab93abc04ea/lab-cli.db migrate --json
.\.venv\Scripts\python.exe -m scripts.lab_db --database-url sqlite:///C:/Users/user/AppData/Local/Temp/fpg-phase4-42e82247a66b481fa5bbcab93abc04ea/lab-cli.db seed --json
.\.venv\Scripts\python.exe -m scripts.lab_db --database-url sqlite:///C:/Users/user/AppData/Local/Temp/fpg-phase4-42e82247a66b481fa5bbcab93abc04ea/lab-cli.db status --json
.\.venv\Scripts\python.exe -m scripts.lab_db --database-url sqlite:///C:/Users/user/AppData/Local/Temp/fpg-phase4-42e82247a66b481fa5bbcab93abc04ea/lab-cli.db profiles validate --all --json
.\.venv\Scripts\python.exe -m scripts.verify_fpg_core
```

The fresh database migrated to revision 2, seeded five templates and one
active `research-default` profile, and validated with zero profile errors.
Repeated migration reported no work; repeated seed inserted or changed
nothing. Read-only inspection confirmed `fully_shared_wall` exactly once in
`initial`, `refinement_a` and `refinement_b`. `verify_fpg_core` confirmed the
checkout's public imports and configuration mappings. Reset and migration
failure behavior were covered by the Phase 1 tests in the full suite; the
user's existing revision-0 development database was deliberately left
untouched, so this run does not claim it was migrated.

The deferred Lab gates then completed: `.venv\Scripts\python.exe -m pytest`
reported **72 passed** (17.36 s); `ruff check fpg_lab scripts tests` passed;
`mypy fpg_lab scripts` passed across 71 source files; `python
../tools/check_docs.py` and `python ../tools/generate_public_api_manifest.py
--check` passed. The root repository-tool tests were not rerun because Phase 4
changed no root tools. After the browser-discovered E01A toggle correction,
`ruff check fpg_lab/ui/e01a.py`, `mypy fpg_lab/ui/e01a.py` and the E01A browser
flow passed. No Core algorithm suite or research sweep was run.

Real smoke outcomes from the temporary browser database:

| Flow | Observed result |
| --- | --- |
| E01A | The selected prepared plan returned 8 routes and 0 unreachable destinations; temporary results exposed floor-plan, path and heatmap controls. |
| E02A | `phase4-small`, one case and one refinement stage validated and completed. Initial, refinement and post-process stages were selectable; Retry created a second completed run (score 100). |
| E02B | The imported five-room plan completed evaluation. Official score was 0 with the critical gate failed; Geometry integrity exposed a Kitchen/Bathroom overlap of 195 square units. Room-size official status was skipped while independent diagnostics completed at 75. Scoring-settings validation and history dialog close worked. |
| E03A | Bedroom edits, explicit save, stale-save rejection, temporary lock removal, profile refresh preview and cancel worked; the saved room table updated. |
| P01A | The one-trial baseline completed and copied a cleaned current-format hint map. A single bounded two-trial run enabled replay verification: playback advanced, Pause was observable and stopped it, Home scrubbed to Trial 1, and room/path filters updated the canvas. |
| P01B | One iteration completed at score 100; Initial/Post-process stage selection and running/finished terminate states were visible. |
| P01C | One iteration completed at score 100; Initial/Post-process/Openings stages were visible and copying the final plan produced “Floor plan and openings copied.” |

Configuration duplication, save, validation, activation and unsaved-draft
discard were checked. Deleting a saved profile with run references was
rejected by the database; an unreferenced disposable duplicate was deleted
successfully. The selected active profile was restored to `research-default`.
Existing run results continued to display their captured profile hash after
the active profile changed.

All seven active experiment routes, the index, configuration editor and
template editor rendered. Principal E02B canvas, E03A analytical workspace and
configuration editor were checked at 1280×720, 1440×900 and 1920×1080; the
other experiment result/setup screens were checked at the most affected short
and ordinary desktop sizes. Empty, loading, disabled, selected, success and
error states, keyboard focus, accessible control names, independent scrolling
and the main/sidebar balance were inspected. Representative screenshots are
in `.playwright-mcp/phase4-e01a-result-fixed.png`,
`.playwright-mcp/phase4-e02b-geometry-1440.png`,
`.playwright-mcp/phase4-e03a-1280.png`,
`.playwright-mcp/phase4-config-edit.png` and
`.playwright-mcp/phase4-p01a-replay-1280.png`.

The browser pass found one concrete UI defect: NiceGUI's toggle rejected the
tuple supplied by E01A and raised `AttributeError` on the result page. Passing
the same three options as a list fixed it; the rerun displayed and exercised
the controls. Profile deletion remains protected when a run references that
profile; its UI currently reports a generic database-rejection message. This
preserves run provenance, and no profile or run data from the research DB was
involved. The temporary databases and unretained Playwright snapshots were
removed after the server stopped. Phase 4 acceptance passed for this checkout;
the existing local revision-0 database state remains a separate, unmodified
environment item.
