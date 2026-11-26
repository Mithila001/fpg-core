# Active experiments

| Experiment | Question or workflow | Reference |
| --- | --- | --- |
| E01A | Explore walking routes and traffic on prepared plans. | [E01](experiments/e01.md) |
| E02A | Inspect solve, optional refinement, post-processing and scoring on prepared hint maps. | [E02](experiments/e02.md) |
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
