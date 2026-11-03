# Documentation map

`AGENTS.md` at the repository root is the coding-agent entry point. The root `README.md` is the human-facing overview. This directory holds canonical technical documentation; read the relevant section rather than loading everything.

## Architecture

- [Pipeline](architecture/pipeline.md): stage boundaries, Optuna evaluator loop, and data flow.
- [Contracts](architecture/contracts.md): canonical domain types, public APIs, units, results, and package isolation.

## Feature behavior

- [Land](features/land.md): buildable and usable land.
- [Preprocessing](features/preprocessing.md): room rules, floor selection, grid, hallway identities.
- [Candidates](features/candidates.md): search, circulation, and scoring.
- [Solver](features/solver.md): CP-SAT hard/soft constraints and generation profiles.
- [Post-processing](features/post-processing.md): ordered processors, mutation, rollback.
- [Openings](features/openings.md): doors, windows, and required room access.
- [Final scoring](features/final-scoring.md): post-generation evaluation.

## Maintenance

- [Documentation maintenance](development/documentation-maintenance.md): mandatory update and deletion rules for agents.
- [Verification](development/verification.md): checks and experiment runners.
- [Changelog](history/CHANGELOG.md): historical migrations and unreleased changes.

[`personal/`](personal/README.md) is an intentionally informal user-owned workspace. Its contents are never authoritative and need not follow the core documentation update policy.
