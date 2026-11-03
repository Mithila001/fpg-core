# Documentation maintenance

Assess documentation alongside every implementation change. Update affected facts
in the same change, or explain why the existing documentation remains accurate.
Use the [documentation skill](../../.agents/skills/fpg-docs-maintenance/SKILL.md)
for focused synchronization or a requested audit; its workflow does not require
special tooling.

## Ownership and update routing

| Changed behavior | Canonical documentation |
| --- | --- |
| Core package conventions, units, shared domain types, root exports | [Consumer API guide](../API_GUIDE.md) |
| Core feature API, settings, defaults, inputs, outputs, errors, diagnostics | Affected [consumer feature document](../feature_documentations/README.md) |
| Core ownership, hand-offs, algorithm rationale/invariants | Affected architecture or internal feature note linked in the [map](../README.md) |
| Lab setup, environment, data, application architecture | [Lab README](../../fpg-lab/README.md) and [development guide](../../fpg-lab/docs/DEVELOPMENT.md) |
| Experiment-family behavior | Relevant document under `fpg-lab/docs/experiments/` |
| Check selection and commands | [Verification](verification.md) |
| Public breaking change or removed development workflow | [Changelog](../history/CHANGELOG.md), with migration action |
| Navigation or instruction changes | Affected README, scoped AGENTS.md, or skill links |

## Maintain facts, not copies

Verify affected claims against current public exports, contracts, configuration,
validation, execution paths, and relevant tests. Existing prose is context, not
proof. Keep one authoritative explanation for a behavior and link to it elsewhere.
Internal notes explain rationale; public documents must supply enough information
to use supported APIs without reading implementation code.

For consumer-facing changes cover the applicable signatures, required and optional
fields, defaults, nested types, units, validation and cross-field rules, result
variants, exceptions versus returned failure statuses, warnings, production/debug
behavior, mutability, identities, and extension points. Distinguish built-in
defaults, application-owned policy, and recommendations. Supply complete examples
or explicit links to their prerequisites; do not hide required values behind `...`.
Do not invent recommendations or claim infeasible results are exceptions.

Preserve exact public names. Keep per-module export/contract tables current;
regenerate `docs/_generated/public_api_manifest.json` when exports or package
metadata change. These inventories detect coverage gaps but cannot prove that an
explanation or example is correct. Review behavior as well as inventory.

Public documentation describes current source, including Unreleased changes.
Package version metadata is not proof that those changes were published. Before
release synchronize metadata, consumer guides, examples, and changelog. Core has
one package version, no independent feature API versions. Follow the versioning
policy in the consumer guide; record deliberate breaking changes and migration.

## Finish the change

Search for obsolete names, paths, defaults, and copied claims. Update or delete
contradictory guidance. Update navigation when adding or retiring a document.
For new public features provide a consumer document and current contract inventory;
for a new Lab family add a focused family document when that family exists.

Run `python tools/check_docs.py`,
`python tools/generate_public_api_manifest.py --check`, and relevant checks from
[verification](verification.md). Run examples affected by changes. Explain any
unavailable checks. Report documentation changes or why no change was necessary.

Keep instructions short and focused on stable decisions. Skills route to these
documents rather than copying them. Do not turn every implementation detail into
a rule. Personal notes under `docs/personal/` remain user-owned and informal.
