# Migration from `app.algorithms`

## Import mapping

| Previous server-local import | Package import |
|---|---|
| `app.algorithms` | `fpg_core` |
| `app.algorithms.config` | `fpg_core.config` |
| `app.algorithms.types_new` | `fpg_core.types` |
| `app.algorithms.buildable_land` | `fpg_core.buildable_land` |
| `app.algorithms.usable_land` | `fpg_core.usable_land` |
| `app.algorithms.floor_plan_preprocessing` | `fpg_core.floor_plan_preprocessing` |
| `app.algorithms.candidate_search` | `fpg_core.candidate_search` |
| `app.algorithms.candidate_scoring` | `fpg_core.candidate_scoring` |
| `app.algorithms.floor_plan_solver` | `fpg_core.floor_plan_solver` |
| `app.algorithms.floor_plan_post_processing` | `fpg_core.floor_plan_post_processing` |
| `app.algorithms.floor_plan_openings` | `fpg_core.floor_plan_openings` |
| `app.algorithms.floor_plan_scoring` | `fpg_core.floor_plan_scoring` |

A temporary `fpg_core.types_new` compatibility namespace is included, but new server code should use `fpg_core.types`.

## Suggested server migration order

1. Add `fpg-core` as a local editable dependency.
2. Replace shared type imports first.
3. Replace feature imports one feature at a time.
4. Keep server pipeline orchestration unchanged while changing only call targets.
5. Delete the old `app/algorithms` folder after no active import points to it.
6. Remove the temporary `fpg_core.types_new` compatibility namespace after all consumers migrate.

## Editable local dependency

During development, the server can install the sibling repository:

```bash
pip install -e ../fpg-core
```

A requirements entry can also reference the local path during the transition:

```text
-e ../fpg-core
```
