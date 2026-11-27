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
