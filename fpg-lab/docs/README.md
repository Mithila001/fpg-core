# Lab documentation

Lab runs experiments against the public API of the parent Core checkout. It owns
its environment, data, orchestration and presentation; Core stays independent.

- [Setup and use](../README.md).
- [Development and architecture](DEVELOPMENT.md).
- [P01 experiment family](experiments/p01.md): P01A, P01B and P01C.
- [Agent instructions](../AGENTS.md).
- [Core public API](../../docs/API_GUIDE.md).
- [Verification policy](../../docs/development/verification.md).

Add one document under `experiments/` for a real new family. Document its distinctive
purpose, shared behavior, constraints, and checks; do not duplicate Lab-wide rules.
