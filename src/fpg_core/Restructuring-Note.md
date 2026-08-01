# Restructuring Note

The input/output contract restructuring from `FEATURE_TEMPLATE.md` has currently been applied only to `fpg_core.candidate_search`.

## Completed

- Added shared `ExecutionMode`, `ExecutionMetadata`, and `FeatureExecution` contracts under `fpg_core.domain`.
- Updated the one-shot `search_candidates()` operation to:
  - accept an optional keyword-only `ExecutionMode`;
  - return `FeatureExecution[CandidateSearchResult, None]`;
  - place the existing usable result under `execution.result`;
  - return `details=None` because candidate-search-specific R&D/debug data has not been designed yet;
  - report the selected mode and execution duration through `execution.metadata`.
- Kept `CandidateSearchSession` trial lifecycle methods unchanged. Their suggestion, trial, and best-result values are incremental session contracts rather than completed feature execution envelopes.

## Not Yet Restructured

All other feature folders still use their existing input and output contracts. They should not be assumed to return `FeatureExecution` until migrated separately.
