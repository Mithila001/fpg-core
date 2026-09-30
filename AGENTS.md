# FPG Core Agent Workflow

This file is the repository-level change router for coding agents. It tells an agent what must be kept in sync. Detailed engineering rules live in normal developer documentation under `docs/development/`.

`AI_CONTEXT.md`, `project_structure.md`, and `project_structure.txt` are local/generated context artifacts when present. They are not authoritative project files and must not be used as the source of repository rules.

## Source of truth order

When sources disagree, use this order:

1. active code and public exports under `src/fpg_core/`;
2. tests that verify current runtime contracts;
3. `docs/PACKAGE_FEATURE_REFERENCE.md` for consumer-facing documentation;
4. feature README/design/history documents for explanation only.

Never preserve stale behavior only because an old Markdown file says it exists.

## Before changing code

1. Identify the affected feature(s), shared domain contracts, and public exports.
2. Read `docs/development/FEATURE_GUIDE.md` for feature/boundary rules.
3. Read `docs/development/TESTING_GUIDE.md` and identify the affected tests/flows.
4. If consumer-visible behavior may change, read `docs/development/PACKAGE_DOCUMENTATION_GUIDE.md` before editing documentation.

## Required synchronization

| Change | General tests | Targeted flow | Consumer reference |
|---|---|---|---|
| Internal refactor with identical behavior | update only if needed | run affected flow | no |
| Algorithm/validation behavior | yes | update/run affected flow | yes when observable |
| Config/default/profile change | yes | update/run affected flow | yes |
| Public signature/type/enum/status/exception change | yes | update/run affected flow | required |
| Shared `fpg_core.domain` contract change | yes | run every affected flow | required |
| New/removed public feature | yes | add/update relevant flow | required |
| Documentation-only correction | documentation checks | no unless example behavior changed | update directly |

When a feature already participates in a flow test, keep that flow test synchronized with the feature change. Do not create a second overlapping flow unless it verifies a genuinely different boundary.

## Before finishing

Run the smallest relevant checks first, then the full normal suite when practical:

```bash
python tools/generate_public_api_manifest.py --check
python -m pytest tests/contracts tests/architecture
python -m pytest tests/flows/<affected-flow>.py
python -m pytest
```

Also run lint/type checks when the development environment provides them:

```bash
python -m ruff check src tests custom_test tools
python -m mypy src/fpg_core
```

If public exports changed, regenerate the manifest before final verification:

```bash
python tools/generate_public_api_manifest.py
```

If consumer-visible behavior changed, update `docs/PACKAGE_FEATURE_REFERENCE.md` using the documentation guide and include migration notes for breaking changes.

Remove temporary implementation notes, generated context files, debug dumps, and one-off artifacts before finishing. Do not add application/server/database/HTTP concerns to `fpg-core`.
