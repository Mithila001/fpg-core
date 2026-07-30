# Server integration boundary

## Dependency direction

The allowed dependency direction is:

```text
fpg-server -> fpg-core
```

`fpg-core` must never import the server.

## Configuration ownership

The core owns:

- configuration dataclasses and enums,
- configuration invariants,
- `validate_fpg_core_config`,
- pure helpers that consume configuration.

The server owns:

- JSON files and file paths,
- environment-specific values,
- database-backed configuration,
- configuration reload behavior,
- mapping untyped external data into core dataclasses.

The server must construct one validated `FpgCoreConfig` before running generation work. The object and its feature subsections should be passed explicitly to core APIs.

## Runtime ownership

The server should retain:

- flow IDs, trial IDs, and execution context,
- asynchronous job management,
- SSE and cancellation,
- pipeline retry and timeout policies,
- event logging and artifact persistence,
- API request and response translation.

The core should return algorithm results and diagnostics only. It should not save files, emit application events, or access server state.

## Recommended server adapter shape

```python
class FpgCoreAdapter:
    def __init__(self, config: FpgCoreConfig) -> None:
        validate_fpg_core_config(config)
        self._config = config

    def preprocess(self, request):
        return prepare_generation_input(
            request=request,
            config=self._config.preprocessing,
        )
```

The adapter is optional, but it keeps package-specific calls in one server-owned location.
