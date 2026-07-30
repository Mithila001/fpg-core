# Candidate Search

Candidate Search is an Optuna-based spatial candidate exploration component.

Its responsibility is limited to generating candidate `(x, y)` positions,
evaluating those positions through a caller-provided scoring function, and
returning the highest-scoring candidate arrangement.

Candidate Search does not generate floor plans or run CP-SAT.

---

## Public Contract

Candidate Search exposes one operation with one input and one output:

```text
CandidateSearchInput
        ↓
search_candidates()
        ↓
CandidateSearchResult
```
