# Candidate scoring Phase 2

This local workspace compares the previous spatial-distribution objective with
the redesigned spatial-occupancy objective on the same synthetic five-room spec.
Run from the Core root with `.venv/Scripts/python.exe experiments/phase2/run.py`
and `.venv/Scripts/python.exe experiments/phase2/components.py`.
The runner uses grid spacing 10, fixed seeds, 100 and 500 trials per objective,
and writes compact JSON results beside this file. It does not change application
configuration or Optuna's sampling behavior.

See [NOTES.txt](NOTES.txt) for the current run, outcomes, and limitations.
The component runner exercises attached-bathroom proximity, clearance obstruction,
bedroom compactness, assigned-bathroom intrusion handling, and circulation on
hand-authored maps.

The synthetic setup isolates candidate search/scoring. It does not replace the
required solver generation comparisons, which depend on representative prepared
floor-plan requests and successful circulation routes.
