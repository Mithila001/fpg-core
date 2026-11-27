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

## Phase 2 ? in progress

Phase 2 is not complete. Shared `error_payload` and `result_document` moved to
`fpg_lab.core.results`; timestamps reuse `database.models.common.utc_now`.
Mapped row materialization moved to `database.serialization.row_document`,
and hint-map validation to `integrations.fpg_core.hint_map.validate_export`;
P01 trial export remains in `p01b_input`. `workers.executor.BackgroundExecutor`
replaces `workers.p01_jobs.P01JobManager` without changing its queue semantics.
The P01 headless result collection now caps each collection at 100 and reports
total counts; use maintenance record inspection for further rows.

Focused verification used the Lab virtual environment and a unique workspace
`--basetemp`: E02A selected-profile and independent-failure tests, E02B storage
and diagnostics, P01B export and refinement-failure tests, submission failure,
queued termination, shutdown and immediate completion in `test_lab.py`, and
`tests/test_quick_hint.py` (17 passed). `python -m scripts.verify_fpg_core`,
changed UI and runner imports, `python tools/check_docs.py`, and the public API
manifest check passed. The first pytest attempt could not access the system temp
directory; the workspace-local rerun passed.

Still required before Phase 3: trace and catalogue every active experiment;
finish the neutral executor and shared portable-plan ownership as appropriate;
review and remove obsolete preview, export, lifecycle and floor-plan-run paths
after tracing readers and writers; evaluate genuinely common computation stages;
prepare the seven-experiment real smoke catalogue and missing bounded fixtures;
update experiment and skill guidance; run the remaining requested focused checks
and record exact smoke commands and deadlines. No all-experiment smoke, full
suite, browser regression or broad audit was run. Do not treat this record as
a completed Phase 2 or start Phase 3 on its basis.
