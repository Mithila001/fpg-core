# FPG Lab instructions

Lab is an experimental consumer of **this repository's Core**. Root
[instructions](../AGENTS.md) apply. Use only supported Core feature/package/API
exports and `fpg_core.domain`, as an external package consumer would. Production generation algorithms
belong to Core; early E-family ideas may be explored in Lab before promotion. Orchestration, UI, persistence, JSON profiles, and research policy
belong here. Never add Lab imports or dependencies to Core.

## Read only relevant context

- Setup or execution: [README](README.md).
- Runtime, workers, UI, data ownership, or adding an experiment:
  [development guide](docs/DEVELOPMENT.md).
- E01A changes: [E01 family](docs/experiments/e01.md).
- P01A/B/C changes: [P01 family](docs/experiments/p01.md).
- Core usage: affected [consumer feature contract](../docs/feature_documentations/README.md)
  and [shared API guide](../docs/API_GUIDE.md). Inspect Core internals when needed
  to resolve uncertainty, not as a default prerequisite for every Lab task.

Use the repository-local `fpg-lab-experiments` skill when creating or changing
experiments; its [instructions](../.agents/skills/fpg-lab-experiments/SKILL.md)
are available without skill tooling. Prefer configuration reuse when execution
behavior is unchanged. Add families and their documentation when needed; avoid a
generic plugin framework.

## Environment and checks

Use `fpg-lab/.venv`; setup installs Core from the parent checkout. Lab's `.env`,
SQLite database and outputs belong here and are ignored. Setup preserves `.env`;
fresh reset is explicit. Do not reset research data merely to test a change.
Saved profiles are upgraded for the 10-unit hallway rule; old hint-map presets
with narrow hallways must be regenerated. Preserve configuration snapshots and error/provenance recording.

Run the cheap `python -m scripts.verify_fpg_core` check and focused tests when
integration changes. See [verification](../docs/development/verification.md) for
static checks and impact-based selection. Heavy experiments are selected research
checks, not a routine requirement. Use isolated databases for checks beside a UI.

Update affected Lab/family documentation in the same change. Shared Core facts
remain in Core's public docs; link rather than copy. Repair outdated instructions
when discovered and report verification or remaining gaps accurately.
