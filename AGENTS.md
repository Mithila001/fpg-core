# FPG repository instructions

Core is the reusable library in `src/fpg_core/`; `fpg-lab/` is its experimental
consumer. Imports flow **Lab -> public Core APIs**, never Core -> Lab. Core must
install, test, and build without Lab, its dependencies, data, or environment.

## Start with the affected area

- Core task: inspect the feature's public exports, callers, and focused docs below.
  Review Lab only when the changed contract or observable behavior may affect it.
- Lab task: follow [Lab instructions](fpg-lab/AGENTS.md). Consult Core's consumer
  documentation and exports first; inspect internals when evidence requires it.
- Search narrowly and expand as needed. Do not load every document or scan both
  projects by default. Code and verified behavior take precedence over prose;
  correct stale guidance in the same change.

## Boundaries and project conventions

- Features expose supported operations through `__init__.py` / `api.py`.
  Cross-feature data belongs in `fpg_core.domain`; avoid private sibling imports.
- HTTP, UI, persistence, workers, file formats, and application orchestration belong
  to consumers. Do not move them into Core for Lab's convenience.
- Preserve room identities, enum semantics, hard constraints, and seeded behavior.
  Examples use 10 units per metre; consumers own consistent unit conversion.
- Public contract changes are deliberate migrations with updated docs and tests.
  Avoid speculative abstractions, dependencies, and compatibility layers.
- Root `.venv` is for Core; `fpg-lab/.venv` installs Lab and this checkout's Core.

## Read by task

| Task | Relevant documentation |
| --- | --- |
| Use or change a public feature | [Consumer guide](docs/API_GUIDE.md), affected [feature contract](docs/feature_documentations/README.md) |
| Ownership and hand-offs | [Pipeline](docs/architecture/pipeline.md), [contracts](docs/architecture/contracts.md) |
| Algorithm invariants and rationale | Relevant [internal feature note](docs/README.md#internal-architecture-and-feature-notes) |
| Create or reshape a feature | [Feature development](docs/development/FEATURE_GUIDE.md) |
| Choose checks | [Verification](docs/development/verification.md) |
| Update documentation | [Maintenance](docs/development/documentation-maintenance.md) |

## Change completion

Assess documentation for every implementation change; update affected canonical
docs alongside code, or explain why no update is needed. Use the repository-local
`fpg-docs-maintenance` skill for synchronization or an explicitly requested audit.
Its [instructions](.agents/skills/fpg-docs-maintenance/SKILL.md) are readable by any
agent; skill tooling is optional.

Run focused checks proportional to impact. A Core change does not require running
Lab experiments automatically. Public consumer changes warrant affected caller
review, the cheap Lab verifier, and relevant regression checks. Long experiments
are research tools, selected when their results matter.

Before finishing, run `python tools/check_docs.py` and
`python tools/generate_public_api_manifest.py --check`. Regenerate the manifest
when exports or package metadata change. Record breaking changes in the
[changelog](docs/history/CHANGELOG.md). Report checks and remaining gaps accurately.

`docs/personal/` is user-owned scratch space, never project authority.
