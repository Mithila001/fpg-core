---
name: fpg-lab-experiments
description: Create, extend, or reorganize FPG Lab experiments using the local Core public API, existing Lab lifecycle patterns, and family documentation.
---

# Develop Lab experiments

For experiment UI creation or updates, follow the canonical [UI standards](../../../fpg-lab/docs/UI_STANDARDS.md): experiment listing, setup and run-specific results, plus visualization-first desktop layout with documented exceptions.

Read [Lab instructions](../../../fpg-lab/AGENTS.md), its
[development guide](../../../fpg-lab/docs/DEVELOPMENT.md), and the relevant family
in the [Lab map](../../../fpg-lab/docs/README.md). Inspect the actual flow and its
callers; do not load unrelated Core implementation or every family document.

Identify the research question, inputs, stages and observations needed. Reuse an
existing experiment for a profile variation. Extend its family when execution
belongs there; introduce a new family and document only when behavior warrants it.
Avoid a generic framework or new shared layer for hypothetical future experiments.

Use this checkout's Core through supported exports, consulting its public docs.
Generation algorithms stay in Core; Lab owns experiment policy and orchestration.
Reuse applicable input validation, session ownership, queue, snapshot/provenance,
error recording, serialization and visualization patterns. Keep workers independent
of UI elements and configuration drafts separate from immutable saved run snapshots.
Apply the family's stage/failure rules; do not impose P01-specific design on every
new experiment. Register the actual runtime/UI/headless entry points needed.

Update the family document for distinctive purpose, shared flow, boundaries,
configuration, recording and verification; update the map for a new family. Shared
Core contracts belong in Core docs. Leave a focused runnable check for nontrivial
changes and choose bounded verification from the
[policy](../../../docs/development/verification.md). Use isolated databases, inspect
nested branch failures, and reserve costly real experiments for relevant changes.
Report the experiment behavior, documentation changes and actual verification.
