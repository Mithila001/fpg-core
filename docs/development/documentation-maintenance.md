# Mandatory documentation maintenance for coding agents

**Read and apply this file for every implementation change.** Documentation is part of the same change as code; do not wait for the user to request documentation, and do not keep outdated descriptions for historical comfort.

## Ownership and update routing

| Change to code or behavior | Required documentation action |
| --- | --- |
| Stage ordering, data hand-offs, consumer orchestration | Update `docs/architecture/pipeline.md` |
| Public types, exports, enums, units, execution contracts, package boundaries | Update `docs/architecture/contracts.md`; regenerate `docs/_generated/public_api_manifest.json` **when exports change** |
| Land, preprocessing, candidate, solver, geometry, openings, or scoring behavior | Update the relevant `docs/features/*.md`, including constraints/defaults/debug and error semantics where meaningful |
| Test commands, manual experiments, tool usage | Update `docs/development/verification.md` and affected `experiments/*/README.md` |
| User installation, supported capabilities, main usage | Update root `README.md` |
| Breaking public API, removed compatibility, changed default contract | Add an `Unreleased` entry to `docs/history/CHANGELOG.md` with migration instruction |
| Documentation organization or policy | Update `AGENTS.md` routing and `docs/README.md`; remove dead links and replaced files |
| Internal refactor with no externally observable change | Correct only documentation made false by the refactor; do not add redundant prose |

## Required end-of-task procedure

1. Before implementation, read the **affected canonical feature document** and verify each affected claim against current code, config, public exports, and tests (if present). Docs are context, not proof.
2. Implement changes and tests. Keep contract names, default settings, stage responsibilities, and examples in sync. A new feature must have a clear section/document and navigation entry; do not scatter competing explanations across README files.
3. Search the repository for obsolete names, paths, defaults, and old examples. **Update or delete**, rather than leaving contradictory files. Remove temporary plans and generated scratch notes from canonical docs.
4. Run `python tools/check_docs.py` to catch broken relative links, misplaced Markdown, and duplicate repository agent files. Regenerate/check the public API manifest when exports change. Run the relevant checks in `verification.md`.
5. In the completion report state which documentation files were updated, or explicitly say **why no documentation change was required**. Clearly report checks that could not run.

## Writing and information boundaries

- Prefer concise, task-routing Markdown. Document **why/what cannot be inferred cheaply from code**: invariants, ownership, subtle algorithms, exceptions to shared conventions, and migration impact. Link to source paths instead of copying implementation internals or exhaustive export catalogs.
- One authoritative explanation per behavior: `AGENTS.md` is the short router; `docs/architecture/` captures cross-feature contracts; `docs/features/` holds specific invariants; `docs/development/` holds process; root `README.md` serves humans.
- No feature-local README solely to repeat an API manual. Keep experiment READMEs for their unique run/view instructions.
- `docs/history/` keeps significant public change history, not stale technical guidance.
- `docs/personal/` is explicitly informal and optional, not linked as a required dependency or used as a source of implementation rules. Do not move important project contracts there.
- Avoid promises such as "tested" or "compliant" without an actual verification result. Do not invent missing tests or release versions.
