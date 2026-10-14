# Phase 1: candidate flow

Runs preprocessing, candidate search, candidate circulation, and candidate scoring. It stops as soon as a candidate reaches the target score, or after the trial limit.

```bash
python experiments/phase-1/run_flow.py
python experiments/phase-1/run_flow.py --target-score 95 --max-trials 1200
```

The default target is `100` (candidate scoring's maximum), with a 500-trial ceiling. Results go to `experiments/outputs/phase-1/`. The scenario settings are reused from `experiments/full_flow/scenario.py`.

Open `viewer.html` and choose or drop a result JSON. The left panel lists all trials; the large canvas shows the selected trial. Use play/pause, previous/next, the slider, or the trial number to move through the run. Playback speed and the Candidate search / Candidate circulation evaluation selector sit above the canvas. Scroll to zoom, drag to pan, and use Reset view to fit the floor again.

New runs save the original search hints plus DEBUG circulation paths, hallway classifications, and removed hallway hints for every trial. Existing JSON files still work: when those snapshots are absent, the viewer labels its fallback to the saved post-circulation hints and scoring routes. Details opens the selected trial's score breakdown and raw JSON.
