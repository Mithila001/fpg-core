# Package feature documentation template

Use this template whenever an `fpg_core` feature is added or its public behavior
changes. Read the current package `__init__.py`, `api.py`, contracts/types,
configuration, validation, exceptions, and defaults before updating the document in
`/docs`. Do not infer behavior from an old document when source behavior differs.

Document one feature independently. Do not prescribe a multi-feature pipeline.

## Feature name

### Purpose

What the feature accomplishes and when a package consumer uses it.

### Public API

Supported import paths, functions/classes, exact signatures, and entry points.

### Inputs

Every required and optional input, including type, meaning, units, constraints, and
default.

### Configuration

Every supported setting and the observable effect of changing it.

### Recommended values

Only implementation-backed defaults or ranges. Say when project calibration is
required instead of inventing a value.

### Outputs

Exact return type and consumer-relevant fields, statuses, units, and interpretation.

### Errors / failure conditions

Raised exceptions, returned failure statuses, invalid inputs, infeasibility, and
edge cases callers must handle.

### Usage example

A realistic, self-contained example using only supported public imports.

### Important behavioral notes

Mutation, determinism, DEBUG/PRODUCTION differences, compatibility aliases, and
other observable behavior needed for correct use.

## Verification checklist

- Compare documented names with feature-root `__all__` and `api.py.__all__`.
- Confirm constructor signatures and dataclass defaults from source.
- Confirm validation constraints and exception/status behavior.
- Confirm built-in profiles and recommended values from current defaults.
- Run documentation examples or an equivalent contract test where practical.
- Keep implementation algorithms, private helpers, and orchestration out of the
  consumer reference.
