# Lab documentation

Lab runs Core-based prototypes and standalone early experiments. It owns
its environment, data, orchestration and presentation; Core stays independent.

- [Setup and use](../README.md).
- [Development and architecture](DEVELOPMENT.md).
- [E01 experiment family](experiments/e01.md): E01A floor traffic.
- [P01 experiment family](experiments/p01.md): P01A, P01B and P01C.
- [Agent instructions](../AGENTS.md).
- [Core public API](../../docs/API_GUIDE.md).
- [Verification policy](../../docs/development/verification.md).

Add one document under `experiments/` for a real new family. Document its distinctive
purpose, shared behavior, constraints, and checks; do not duplicate Lab-wide rules.

## Experiment names

Names use `<category><family number><variant>`, such as P01A or E01A. **P** means
Prototype: usually a specific pipeline using Core features directly. **E** means
Experiment: usually an early idea explored independently before main development.
P01 and E01 are families; the final letter distinguishes variants. New category
letters can be introduced when needed.
