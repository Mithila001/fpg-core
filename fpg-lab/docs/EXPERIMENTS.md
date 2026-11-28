# Active experiments

| Experiment | Question or workflow | Reference |
| --- | --- | --- |
| E01A | Explore walking routes and traffic on prepared plans. | [E01](experiments/e01.md) |
| E02A | Inspect solve, optional refinement, post-processing and scoring on prepared hint maps. | [E02](experiments/e02.md) |
| E02C | Generate and inspect openings on a portable floor plan. | [E02](experiments/e02.md#e02c-floor-plan-opening-generation) |
| E02B | Compare official scoring and independent evaluator diagnostics on a supplied plan. | [E02](experiments/e02.md#e02b-final-floor-plan-evaluation-inspector) |
| E03A | Explore feasible integer room dimensions under analytical area rules. | [E03](experiments/e03.md) |
| P01A | Run the candidate search through circulation and candidate scoring. | [P01](experiments/p01.md) |
| P01B | Generate, refine, post-process and score floor plans from manual or exported hints. | [P01](experiments/p01.md) |
| P01C | Exercise the P01B-style flow with openings before scoring. | [P01](experiments/p01.md) |

Open `/experiments/<id>` through the Lab index. The headless
`python -m scripts.run_experiment --flow <id>` entry point supports P01A/B/C.
Use E02A for prepared inputs and recorded stage results, E02B for a portable
input and detailed measurements, E03A for tab-local analysis, or P01 for a
queued integrated workflow. Each pattern serves its own research workflow.
Use [architecture](ARCHITECTURE.md) for the shared configuration and snapshot policy.

## Reference patterns

- **Transient analysis - E01A.** `/experiments/e01a` selects a prepared plan
  and runs `flows.e01a.simulate`; its result is tab-local. Use this pattern for
  input-driven analyses that do not need profiles or recorded runs. Its routing,
  traffic model and plan preparation are specific to E01A.
- **Profile-based solver cases - E02A.** The setup loads portable hint maps,
  resolves a selected or active profile and snapshots effective settings; the
  background flow stores each case and stage in an E02 run. Use it for comparing
  independent prepared inputs, retaining failed case details and successful
  earlier geometry. Its case selection and refinement policy are local to E02A.
- **Scoring inspection - E02B.** The setup accepts a portable plan or saved
  layout and snapshots scoring settings. The worker stores official scoring and
  skipped-evaluator diagnostics separately; the result page displays both. Use
  this when investigating scoring, including structurally valid poor plans.
- **Live analytical editing - E03A.** The editor loads typed profile settings
  into a tab-local draft and runs `flows.e03a.analyze`; explicit save writes the
  profile section. Use for direct analysis with draft and temporary lock state,
  adapting its sizing rules and stale-result handling to the problem.
- **Candidate flow - P01A.** A profile and request drive preprocessing, candidate
  search, circulation and scoring in a worker; saved trials feed result and replay
  views. Use for candidate investigation, adapting its search and rejection policy.
- **Iterative generation - P01B/C.** A portable preset and profile snapshot
  drive independent iterations through initial solve, optional refinement,
  post-processing and scoring; P01C inserts openings before scoring. Their
  iteration, cancellation, stage recording and failure policies remain local.

These examples are starting points to adapt, not mandatory experiment lifecycles.
