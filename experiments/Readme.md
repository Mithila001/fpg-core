# Experiments

`experiments/` contains focused, manually run experiments for evaluating whether features in the `fpg-core` package work as intended.

## Boundaries

- This directory is for experiments and exploratory evaluation. Automated tests belong under `tests/`.
- Nothing under `experiments/` is included when the package is built or installed for consumers.
- Dependencies point inward: experiments may call the public APIs of `fpg_core`, but application code, package code, and automated tests must not import from `experiments/`. Removing this directory must not affect the package, application, or automated test suite.
- Experiments are independent by default. An experiment may share code with another experiment when that relationship is explicit; separate experiments do not otherwise need to work together.

## Outputs

Place generated output under `experiments/outputs/<experiment-name>/`. Each experiment gets its own folder. For example, the full-flow experiment writes to `experiments/outputs/full_flow/`.
