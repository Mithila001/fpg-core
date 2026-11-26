# FPG Lab instructions

Follow the [root instructions](../AGENTS.md). Lab owns orchestration, UI and
research data. Import only supported Core APIs. Keep Core independently usable.
Use the Lab environment and isolated SQLite targets for checks. Stop Lab before
migration or reset. Persist configuration through the profile service and keep
run inputs and drafts separate from saved profiles.

- Setup and entry points live in the [README](README.md).
- Before changing data or lifecycle behavior, read [architecture](docs/ARCHITECTURE.md)
  and [development](docs/DEVELOPMENT.md).
- For an experiment, use the [catalogue](docs/EXPERIMENTS.md) and the relevant family
  note. For UI work, apply the [UI standards](docs/UI_STANDARDS.md).
- Use the [Lab experiment skill](../.agents/skills/fpg-lab-experiments/SKILL.md)
  and the affected [Core contract](../docs/feature_documentations/README.md).

Run focused tests and the Core verifier for integration changes. Keep the
affected documentation current and report outstanding verification.
