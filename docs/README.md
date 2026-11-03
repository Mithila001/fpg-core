# Documentation map

## Public Core documentation

- [Consumer API guide](API_GUIDE.md): installation, units, shared contracts,
  execution conventions, reusable examples, compatibility, and package exports.
- [Feature contracts](feature_documentations/README.md): complete feature-specific
  APIs, inputs, configuration, outputs, failure handling, diagnostics, and examples.
- [Changelog](history/CHANGELOG.md): significant changes and migration guidance.

These Markdown files target consumers as well as developers. No Lab installation
or implementation-source reading is required to use the documented public APIs.

## Internal architecture and feature notes

Read only the documents relevant to your task:

- [Pipeline](architecture/pipeline.md) and [contracts](architecture/contracts.md).
- [Land](features/land.md), [preprocessing](features/preprocessing.md),
  [candidates](features/candidates.md), [solver](features/solver.md),
  [post-processing](features/post-processing.md), [openings](features/openings.md),
  [final scoring](features/final-scoring.md).

These notes capture implementation rationale and invariants; the public guides own
consumer contracts.

## Development

- [Feature development](development/FEATURE_GUIDE.md).
- [Verification](development/verification.md): check selection and exact commands.
- [Documentation maintenance](development/documentation-maintenance.md).
- [Root agent instructions](../AGENTS.md) and [Lab documentation](../fpg-lab/docs/README.md).

[Personal notes](personal/README.md) are informal, user-owned, and not authoritative.
