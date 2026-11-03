# fpg-core agent instructions

`fpg-core` is a reusable Python package for single-storey residential floor-plan generation. This is the only repository-level agent instruction file. Read only the documents relevant to the change; `docs/personal/` is user-owned scratch space, not project authority.

## Non-negotiable boundaries

- Keep imports directed from consuming applications to `fpg_core`, never the reverse. No HTTP, database, worker, deployment, or client-format dependencies in the package.
- Features expose supported APIs from their package `__init__.py` / `api.py`; exchange data via `fpg_core.domain`, not another feature's internal modules.
- Protect exported contracts, room identities, enum values, project units (10 units = 1 m), hard constraints, and deterministic/seeded behavior. Treat public changes as migrations.
- Check current imports, exports, configurations, and execution paths before relying on prose. Code and verified tests take precedence over documentation.

## Read by task

| Work | Focused documentation |
| --- | --- |
| Overall pipeline or feature boundaries | [Pipeline](docs/architecture/pipeline.md), [Contracts](docs/architecture/contracts.md) |
| Buildable/usable geometry | [Land](docs/features/land.md) |
| Room preparation, floor choice, candidate grid | [Preprocessing](docs/features/preprocessing.md) |
| Optuna, routing, candidate evaluation | [Candidates](docs/features/candidates.md) |
| CP-SAT constraints, profiles, hallways | [Solver](docs/features/solver.md) |
| Geometry processors | [Post-processing](docs/features/post-processing.md) |
| Doors, windows, accessibility | [Openings](docs/features/openings.md) |
| Completed-plan quality checks | [Final scoring](docs/features/final-scoring.md) |
| Integration/public contract changes | [Contracts](docs/architecture/contracts.md), [Changelog](docs/history/CHANGELOG.md) |
| Verification or experiment workflow | [Verification](docs/development/verification.md), relevant `experiments/*/README.md` |

## Required change workflow

1. Inspect the active implementation, affected public exports, consumers, and tests if present. Respect feature isolation and avoid unnecessary dependencies/rewrites.
2. **Read [documentation maintenance](docs/development/documentation-maintenance.md) for every code or public-contract change.** Update affected canonical docs in the same change; retire obsolete descriptions and links. Do not defer documentation to a later task.
3. Add or adjust focused tests for changed behavior. Run applicable checks from [verification](docs/development/verification.md); report unavailable checks rather than claiming success.
4. If public exports changed, regenerate `docs/_generated/public_api_manifest.json`. Record breaking changes and migration actions in the changelog.
5. Before finishing, run `python tools/check_docs.py` and the manifest check, then summarize implementation, documentation, verification, and any remaining gaps.

Do not treat generated local context dumps, historical notes, or `docs/personal/` as specifications.
