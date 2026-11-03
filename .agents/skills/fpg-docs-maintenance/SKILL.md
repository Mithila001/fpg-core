---
name: fpg-docs-maintenance
description: Synchronize FPG Core and Lab documentation with an implementation change, or audit documentation against current code when explicitly requested.
---

# Maintain FPG documentation

Start with the requested change and its affected contracts; a small edit does not
require a repository-wide audit. For a requested audit, compare all supported
exports and consumer behavior against canonical docs.

Read the [maintenance policy](../../../docs/development/documentation-maintenance.md)
and only the affected documents in the [Core map](../../../docs/README.md) or
[Lab map](../../../fpg-lab/docs/README.md). Verify claims against current exports,
inputs/configuration, validation, execution paths and relevant tests.

Update the authoritative home of each changed fact: shared Core contracts in the
API guide, feature contracts in consumer feature docs, rationale in internal notes,
Lab behavior in Lab docs, family behavior in its experiment document. Link rather
than copy. Public guidance must let a consumer construct valid inputs and handle
results/failures without reading implementation code. Preserve usable examples,
units, identities, defaults, debug behavior and migration actions where applicable.

Search for obsolete paths and competing descriptions after a rename or removal.
Update navigation and the public export/contract tables; regenerate the manifest
only when its inputs change. Repair outdated agent/skill routing when affected.

Run the documentation checker, manifest check and relevant coverage/example checks
from [verification](../../../docs/development/verification.md). Explain semantic
review and checks performed; inventories and link checks cannot prove accuracy.
Report remaining gaps honestly. For an internal change that leaves docs accurate,
a short no-update explanation is sufficient.
