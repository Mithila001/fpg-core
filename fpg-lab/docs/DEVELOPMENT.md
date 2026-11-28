# Lab development

Work from `fpg-lab/` with its virtual environment active. For a manual environment
install use `python -m pip install -e .. -e ".[dev]"`. Setup scripts are listed
in the [README](../README.md). Use the [Core verification policy](../../docs/development/verification.md)
to choose focused checks and keep CI configured.

## Database commands

Use `python -m scripts.lab_db --database-url <URL>` followed by a command below.
Omitting the global URL uses the value resolved from the Lab environment.
Explicit relative SQLite URLs resolve from the working directory. For isolated
checks, use `sqlite:///./data/phase1-check.db` or an absolute temporary path.
Stop Lab and headless execution before migration or reset. Runtime and maintenance
use a local advisory execution lock. Stop older Lab processes manually before
upgrading from revision 0.

Revision 12 upgrades saved profiles to schema 9. Stop Lab, run `migrate --dry-run
--json`, review the proposed profile changes, then run `migrate --json` and
`profiles validate --all --json`. It enables spatial occupancy, disables spatial
distribution, replaces grid-step scoring preferences with initial project-unit
distances, and removes the obsolete fixed clearance widths. It preserves historical
run snapshots and results. Custom distance settings require review after migration;
old grid steps are not converted to project units.

| Command | Result |
| --- | --- |
| `status --json` | Schema compatibility, revision, profile revisions and table counts. |
| `migrate --dry-run --json` / `migrate --json` | Report or apply reviewed upgrades. An empty target is initialized with the primary profile. |
| `seed --json` | Create missing namespace, primary profile and template records. Existing rows and active selection are retained. |
| `profiles list --json` / `profiles show <id> --json` | Metadata page or one complete profile. |
| `profiles duplicate <id> --name <name>` / `profiles activate <id>` | Copy or select a validated profile. |
| `profiles validate --all --json` | Validate every profile and report errors by ID. |
| `records <table> --limit 25 --offset 0 --json` / `record <table> <id> --json` | Inspect a metadata page or the entire requested record. |
| `export <table> <id> --output <path>` | Write one record to a new JSON file. |
| `reset --scope runs --yes` | Delete E02 runs and P01 experiments, trials and iterations. |
| `reset --scope all --yes` | Rebuild and seed the recognized selected database. |

Collection commands default to 25 items and accept limits up to 500. Metadata
includes IDs and applicable identity, status, parent and timestamp fields. The
`records` command accepts exact `--status` and `--experiment-id` filters on tables
with those columns. Use its help for the allowlist. Exit code 1 reports an
operation, conflict, or validation failure. Exit code 2 reports argument errors.
Status, inspection and dry run can read a reviewed unversioned database. Use a
new SQLite target for unknown schemas, or inspect them separately before deciding
how to recover them.

## Change workflow

Times, room dimensions, rule keys and Core features should be verified using the
affected [public contract](../../docs/feature_documentations/README.md). Keep
profile normalization on saves and migrations. Put meaningful migration logic
in `fpg_lab.database.maintenance`, validated profile edits in
`SystemConfigurationService`, and mappings to supported Core configuration in
`CoreConfigCodec`. Use `python -m scripts.verify_fpg_core` locally. Run the focused
adapter and SQLite checks for data changes, `python ../tools/check_docs.py` for
docs, and update the relevant records and family notes together. Use the
[Phase 1 handoff](IMPLEMENTATION_HANDOFF.md) for exact verification commands.

The P01 headless runner collects at most 100 trials and iterations per result,
and includes total counts. Use `scripts.lab_db records`
with a bounded page and `record` or `export` with a returned ID to inspect one
row. E02 cases are contained in the E02 run record; select the desired case or
fields from its exported JSON.

Revision 2 migration removes the obsolete floor-plan-run table and old P01B/C
runs without a saved preset snapshot. The dry run reports both counts. Profiles,
templates, presets, saved plans and current runs remain. Export observations
that matter before applying the migration. Stop Lab before maintenance.

## Revision 3 scoring profile migration

Stop Lab and headless execution. Run these commands from `fpg-lab/` using
the Lab environment. Include `--database-url <URL>` before the command name
to select a different database.

```powershell
python -m scripts.lab_db migrate --dry-run --json
python -m scripts.lab_db migrate --json
```

Revision 3 updates saved scoring configuration in place. It deletes both
retired evaluator entries from profiles and seeds the four new defaults where
the former kitchen/dining evaluator was configured. It preserves the other
scoring settings, profile IDs, active selection, saved layouts and run snapshots.
Snapshot exports still contain the original measurements. E02B's evaluator views
use the current set of evaluators. New databases seed the current configuration.
The dry run reports profiles and hashes that would change. If a custom profile
would leave an enabled group without an evaluator, the dry run reports a conflict
and the migration stops without writing. Update the profile so its enabled
groups have current evaluators before applying the migration.

## Revision 4 post-processing profile migration

Stop Lab and headless execution, then use `python -m scripts.lab_db migrate
--dry-run --json` followed by `python -m scripts.lab_db migrate --json`. The dry
run reports proposed profile changes and conflicts. Revision 4 replaces obsolete
wall-extension selections with the new defaults while preserving configured room
types and maximum distances, removes placeholder-based veranda adjustment, and
orders cleanup and repair stages. Review the new architectural thresholds before
using the upgraded profile. Profile IDs and historical run snapshots are retained;
snapshots are not rewritten. No database reset is required.

## Revision 5 front wall setback profile migration

Revision 5 keeps the existing database schema and adds the new
`front_wall_setback` hard constraint to the saved initial, refinement A,
refinement B, and optional P01B refinement profiles that do not already
contain it. Existing custom setback settings, profile IDs and historical
run snapshots are preserved. The baseline uses garage 10, veranda 5, and
living room 10 (only when no veranda exists) in project units.

Stop Lab and headless execution, back up the selected database, and run from
`fpg-lab/` with the Lab interpreter:

```bash
python -m scripts.lab_db migrate --dry-run --json
python -m scripts.lab_db migrate --json
python -m scripts.lab_db profiles validate --all --json
```

Review the dry run before applying it. No reset is necessary. To opt out of
a room policy, remove its rule from the saved solver profile after migration.
See the [Core contract](../../docs/feature_documentations/floor_plan_solver.md#front-wall-setback).

## Revision 6 room quality scoring profile migration

Revision 6 enables `living_room_balance` and `bedroom_quality` for saved profiles
as functional evaluators. Missing rules use the starter profile settings;
existing settings, weights and order are retained. If needed the functional
group is created or enabled. The two rules are non-critical. Profile IDs,
active selection, other settings and historical snapshots are retained; no
database reset or DDL change is required. The previous revision's setback
migration does not rerun on revision 5 databases.

Stop Lab, back up the selected SQLite file, and run the existing
`migrate --dry-run --json`, `migrate --json` and `profiles validate --all --json`
commands. Resolve any profile validation conflicts before applying the migration.
Older custom solver room-size rules using the removed legacy settings must
already conform to the current solver contract.


## Revision 7 opening generation migration

Revision 7 adds E02C run storage and changes saved profiles with zero corner
clearance to 0.5 metres expressed in each profile?s project units. Nonzero
clearances, saved plans, other profile settings and historical snapshots are
preserved. The dry run reports affected profile hashes and conflicts. Stop Lab,
back up the selected database and use `migrate --dry-run --json` before applying
`migrate --json`; then run `profiles validate --all --json`. No reset is needed.
Run-only reset includes E02C runs.


## Revision 8 interior door policies

Revision 8 changes saved opening profiles without a SQL schema change. The standard
interior policy copies each profile's existing door width, minimum shared wall and
corner clearance as preferred clearance. Its hard minimum is zero. Bathroom and
attached-bathroom overrides use 0.8 m width and minimum wall, 0.2 m preferred
clearance and centered placement, scaled to the profile's units. Existing exterior
and window settings, saved plans, run history and snapshots remain unchanged.

Stop Lab and headless execution, back up the database, then run from `fpg-lab/`:

```powershell
python -m scripts.lab_db migrate --dry-run --json
python -m scripts.lab_db migrate --json
python -m scripts.lab_db profiles validate --all --json
```

Review the dry-run conflicts and proposed hashes before applying. No reset is needed.

## Revision 9 opening quality policies

Revision 9 adds room-specific window policies, bathroom windows, normal connection
limits, kitchen-dining connectivity and duplicate prevention. It enables exterior
doors, windows and room door limits for these policies. Existing standard window
dimensions and preferred clearance are carried into each profile; bathroom widths
and preferred clearances are 0.5 m and 0.2 m in profile units. Existing interior
door dimensions, profile identities, saved plans and historical snapshots remain.
Secondary entrances are required at the existing configured exterior door width.
No tables change and no reset is needed. Stop Lab and headless execution, back up
the database and use the revision 8 commands above, reviewing the dry run first.

## Revision 10 candidate scoring migration

Stop Lab and back up the database. Run `python -m scripts.lab_db migrate --dry-run
--json`, review conflicts, then run `python -m scripts.lab_db migrate --json` and
`python -m scripts.lab_db profiles validate --all --json`. Revision 10 updates saved
profiles to schema 7, removes candidate relationship quality and the old error and
N/A flags, adds circulation quality and functional group purity, and sets candidate
weights to 1.0. Other settings and historical experiment snapshots are preserved.

## Revision 11 candidate circulation migration

Stop Lab and headless execution, back up the database, and run `python -m
scripts.lab_db migrate --dry-run --json` before applying `migrate --json` and
`profiles validate --all --json`. Revision 11 upgrades profiles to schema 8 and
changes rule 5 to the prepared attached-bathroom assignment with a two-step,
0.25 distance policy. Other rules, route costs, unrelated settings and historical
experiment snapshots are retained. A customized rule 5 that is not the reviewed
old bedroom-to-bathroom rule causes a migration conflict for manual review. No
database reset is required.
