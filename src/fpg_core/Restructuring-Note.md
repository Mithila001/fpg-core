# Restructuring Note

The standard `FeatureExecution[result, details]` contract from `FEATURE_TEMPLATE.md` has currently been applied to these completed feature operations:

- Candidate Search
- Candidate Circulation

## Candidate Search

- `search_candidates()` returns `FeatureExecution[CandidateSearchResult, None]`.
- `CandidateSearchSession` keeps its direct incremental trial contracts.
- Candidate Search does not yet collect feature-specific DEBUG details.

## Candidate Circulation

- `refine_candidate_circulation()` returns cleaned candidate points and production hallway classifications as its normal result.
- PRODUCTION omits feature details.
- DEBUG includes route paths, costs, path/circulation efficiency scores, routing passes, hallway traffic roles, and removed hallway hints.
- Hallway classification and unused-hallway removal belong here. Relationship Quality performs its own single scoring pass without importing this feature.

## Not Yet Fully Restructured

Other feature folders should not be assumed to return `FeatureExecution` until migrated explicitly.

## Important Candidate Invariant

Candidate Search should generate hint points without overlapping coordinates.
