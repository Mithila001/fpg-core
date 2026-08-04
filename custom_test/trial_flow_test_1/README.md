# Trial Flow Test 1

Manual realistic flow test for the current `fpg-core` feature contracts:

```text
Floor Plan Preprocessing
    -> Candidate Search
    -> Candidate Circulation
    -> Candidate Scoring
```

## Run

From the repository root:

```bash
python custom_test/trial_flow_test_1/run_trial_flow.py
```

The script reads `input.json` and overwrites `result.json`.

## Current contract behavior

- Preprocessing owns `candidate_search_grid_spacing` and `max_hallway_room_count`.
- Preprocessing returns the resolved Candidate Search space and hallway range.
- Candidate Search consumes those prepared values directly.
- One hallway point represents one distinct hallway room.
- Each trial selects between `1` and the prepared maximum hallway-room count.
- Candidate Circulation and Candidate Scoring run inside every search trial in `PRODUCTION` mode.
- The winning candidate is rerun through Circulation and Scoring in `DEBUG` mode for detailed output.

The candidate-specific generation specification is created immediately after Candidate Search, before Candidate Circulation. This is intentional because Circulation may remove every hallway point, while `generation_spec_for_candidate()` requires the preprocessing minimum of one hallway.

## Files

- `input.json`: realistic request, feature configuration, route rules, and scoring weights.
- `run_trial_flow.py`: standalone orchestration script using only public feature APIs.
- `result.json`: latest generated DEBUG result.

`custom_test` is not included by the current package manifest, so this setup remains outside the distributed Python package.
