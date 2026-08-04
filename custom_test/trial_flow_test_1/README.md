# Trial Flow Test 1

Manual realistic flow test:

```text
Preprocessing -> Candidate Search -> Candidate Circulation -> Candidate Scoring
```

Run from the repository root:

```bash
python custom_test/trial_flow_test_1/run_trial_flow.py
```

The script reads `input.json` and overwrites `result.json` with DEBUG-level results for every final stage. Candidate Search evaluates each trial through production-mode Candidate Circulation and Candidate Scoring.
