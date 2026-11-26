# Lab glossary

| Term | Meaning |
| --- | --- |
| Profile | A named database record containing a versioned configuration document. An explicit ID selects a record for execution. Omitting the ID selects the one active profile. |
| Primary profile | `research-default`, the baseline identity assigned at initialization. Its ID survives migrations and another profile can be active. |
| Seed | Version-controlled starter assets used to create missing database records. |
| Migration | Explicit forward evolution of the database revision and saved configuration documents. |
| Reset | Explicit removal of run history or rebuilding and reseeding the selected database. |
| Run | One execution or analysis in an experiment. Persisted runs may contain trials, cases or iterations. |
| Fixture | A prepared input or database record for a repeatable research scenario or check. |
| E | Experiment focused on a particular research question, with prepared or mocked inputs where useful. |
| P | Prototype exercising an integrated flow. |

Core terms and supported contracts are defined in the [Core API guide](../docs/API_GUIDE.md).
