# FPG Core Package Documentation Template for AI

> **Purpose:** Use this file as the mandatory instruction template whenever generating or updating consumer-facing documentation for `fpg-core`.
>
> The finished documentation must let a package consumer use every supported public feature without reading the source code and without guessing input structures, configuration fields, output structures, enum values, defaults, failure behavior, units, or mode-specific behavior.

---

# 1. Documentation Objective

Generate a **complete, source-verified, consumer-facing package reference** for the current `fpg-core` source tree.

The documentation is not a high-level overview. It is the package contract reference.

> **Template notation:** Angle-bracket placeholders and any ellipses shown inside this instruction file are only template notation. The generated consumer documentation must replace them with verified concrete names, values, fields, and structures.

A consumer must be able to answer all of the following from the documentation alone:

1. What can I import?
2. From which public module should I import it?
3. What exact function/class/method should I call?
4. What exact arguments must I provide?
5. What are the exact Python types of those arguments?
6. What fields exist inside every nested input object?
7. Which fields are required and which have defaults?
8. What values are accepted by enums, literals, identifiers, mappings, and collections?
9. What validation rules and cross-field constraints apply?
10. What units and coordinate conventions apply?
11. Which values are configuration and which are per-request/runtime input?
12. What exactly is returned?
13. What fields exist inside every nested returned object?
14. What changes between `PRODUCTION`, `DEBUG`, or any other supported modes?
15. What statuses or exceptions can occur?
16. Which failures raise and which are returned as normal result statuses?
17. Does the operation mutate any supplied object?
18. Is behavior deterministic? If not, what controls randomness?
19. What package defaults or built-in profiles exist?
20. What values are recommended, and why?
21. How do I construct a valid minimal example?
22. How do outputs connect to other public `fpg-core` features when relevant?
23. Which compatibility aliases or legacy surfaces still exist?
24. What changed compared with the previous documented version?

If any of these cannot be answered from the finished document, the documentation is incomplete.

---

# 2. Non-Negotiable Completeness Rules

The following rules are mandatory.

## 2.1 Never truncate public contracts

Do **not** shorten public data structures.

Forbidden examples:

```text
...
etc.
and so on
other fields omitted
remaining enum values omitted
similar fields
standard fields
usual metadata
```

If a public dataclass has 18 fields, document all 18 fields.

If a nested result contains another public dataclass, recursively document that dataclass until the consumer reaches primitive values, enums, public aliases, or already-documented canonical shared contracts.

## 2.2 Never hide nested structure behind a type name

This is insufficient:

```text
request: FloorPlanSolveRequest
```

The documentation must also show the complete `FloorPlanSolveRequest` structure and the structures of every public nested type required to construct it.

The same rule applies to outputs.

## 2.3 Never make the consumer inspect source code

Do not write statements such as:

```text
See config.py for available fields.
See the dataclass definition.
See source for enum values.
Refer to implementation for validation.
```

The documentation itself must contain the relevant public contract.

## 2.4 Never guess

If the source does not verify a fact, do not invent it.

Use one of these explicit forms:

```text
No package-level recommendation is defined.
The package does not currently define a universal value for this setting.
This behavior could not be verified from the supplied current source.
```

If a required public contract cannot be verified because necessary source files are missing, do **not** silently publish a supposedly complete reference. Report the missing source files and mark the documentation incomplete.

## 2.5 Separate source facts from recommendations

Every recommendation must be identifiable as one of:

- **Package default** — directly defined by current source.
- **Built-in profile value** — directly defined by a shipped profile/preset.
- **Implementation constraint** — a minimum/maximum/range enforced by validation.
- **Project recommendation** — suggested for `fpg-core` usage but not enforced.
- **Domain-specific** — no universal value; consumer must supply jurisdiction/product/domain data.

Never present a suggestion as though the package enforces it.

## 2.6 Exact names matter

Preserve exact:

- public import paths,
- class names,
- function names,
- argument names,
- dataclass field names,
- enum member names and serialized values,
- exception names,
- status names and values,
- registry keys,
- profile names,
- constraint IDs,
- evaluator IDs,
- processor IDs,
- feature IDs,
- units.

Do not normalize, rename, or “improve” public names in documentation.

## 2.7 Public API only

Document supported consumer-facing surfaces.

Do not teach consumers to import private implementation modules unless the package intentionally exposes them as part of the supported contract.

Preferred import surfaces must be determined from active exports such as feature-root `__init__.py`, `__all__`, package-root exports, and public `api.py` modules.

---

# 3. Required Source Verification Order

Do not rely on README files alone.

For every documentation update, inspect the active source in this order.

## 3.1 Packaging and package identity

Inspect:

- `pyproject.toml`
- `MANIFEST.in`
- package root `src/fpg_core/__init__.py`
- `py.typed`
- installation/package metadata that materially affects consumers

Verify:

- package name,
- package version if defined,
- supported Python versions,
- runtime dependencies,
- optional dependencies relevant to consumers,
- typing support,
- packaged documentation/data if relevant.

## 3.2 Public feature inventory

Inspect every feature folder under `src/fpg_core/`.

For each feature inspect at minimum:

- `__init__.py`
- `api.py`
- `__all__` declarations
- public contracts/models/types
- config modules
- exceptions
- validation
- defaults/profiles
- registries or extension APIs
- pipeline/manager/runner behavior when necessary to determine actual return/failure behavior
- tests that verify public behavior

Do not assume similarly named old modules remain public.

## 3.3 Canonical shared domain

Inspect `fpg_core.domain` and every module it publicly exports.

Determine which shared contracts are canonical from active imports and public exports.

Do not duplicate a feature-local replacement for a canonical domain type in the documentation.

## 3.4 Tests and runtime behavior

Use tests to verify:

- real import paths,
- supported constructor forms,
- defaults,
- validation,
- mutation behavior,
- statuses,
- mode differences,
- deterministic behavior,
- compatibility aliases,
- expected cross-feature identity handling.

Tests support the source contract; they do not override an intentionally different public API unless current runtime behavior proves the documentation/source is stale.

## 3.5 README and design documents

Use README/design documents for purpose and explanation only after confirming behavior against active code.

If README text conflicts with active public code, document the active public behavior and explicitly note the documentation mismatch if relevant.

---

# 4. Required Final Document Structure

The generated consumer documentation should follow this structure unless the current package has a strong reason to add another section.

```text
# fpg-core Consumer Package Reference

1. Package Overview
2. Installation and Compatibility
3. Public Import Conventions
4. Global Units and Geometry Conventions
5. Execution Modes and Common Return Envelopes
6. Feature Index
7. <Feature 1>
8. <Feature 2>
9. ... every public feature
10. Shared Domain Contract Reference
11. Cross-Feature Compatibility Reference
12. Extension / Registry APIs
13. Public Exception and Status Reference
14. Built-in Defaults / Profiles Reference
15. Compatibility Aliases and Legacy Surfaces
16. Consumer Integration Checklist
17. Public API Coverage Audit
18. Documentation Verification Record
```

Every public feature must receive its own complete section.

---

# 5. Package Overview Section Template

Document:

- what `fpg-core` is responsible for,
- what it intentionally does not own,
- package/application dependency direction,
- supported scope,
- unsupported scope that consumers could reasonably misinterpret,
- whether the package is synchronous,
- whether it owns persistence, HTTP, database, UI, background jobs, or deployment behavior,
- current Python compatibility,
- runtime dependencies that affect installation.

Do not prescribe a single multi-feature orchestration pipeline unless the package explicitly exposes one as required behavior.

---

# 6. Installation and Compatibility Section Template

Include exact supported installation information that can be verified.

Example format:

```markdown
## Installation

### Python requirement

- Python: `<exact supported range>`

### Runtime dependencies

| Dependency | Version constraint | Why consumer may care |
|---|---:|---|
| `<name>` | `<constraint>` | `<brief explanation>` |

### Typing

- `py.typed`: `<present/not present>`
- Consumer type checkers can treat the package as: `<typed/untyped>`
```

Do not invent a package-index installation command if distribution/publishing details are not supplied.

---

# 7. Global Conventions Section Template

Document package-wide conventions only when they are verified globally.

Potential topics:

- units,
- area units,
- coordinate system,
- polygon conventions,
- integer/floating-point expectations,
- ID semantics,
- enum serialization behavior,
- mutability,
- execution modes,
- generic `FeatureExecution` behavior,
- debug details behavior,
- random seeds,
- tolerance conventions.

If conventions differ by feature, document them per feature instead of pretending they are global.

---

# 8. Feature Section — Mandatory Template

Repeat this entire section for **every public feature**.

---

## `<FEATURE DISPLAY NAME>`

### 8.1 Purpose

Explain exactly what the feature does in consumer terms.

Also state what the feature **does not** do when that boundary matters.

### 8.2 When a consumer should use it

Give a short practical description.

### 8.3 Preferred public imports

List every public symbol a normal consumer may need.

```python
from fpg_core.<feature> import (
    <every relevant public operation>,
    <input contracts>,
    <config contracts>,
    <result contracts>,
    <public enums/statuses>,
    <public exceptions>,
)
```

If canonical shared contracts must come from `fpg_core.domain`, show them separately.

Do not import from private modules merely because the implementation stores a type there.

### 8.4 Public API inventory

Provide an exhaustive table.

| Public symbol | Kind | Preferred import path | Purpose | Compatibility/alias notes |
|---|---|---|---|---|
| `<name>` | function/class/dataclass/enum/exception/constant | `<path>` | `<purpose>` | `<notes>` |

Every supported feature-root export should be accounted for either here or in an explicitly linked shared-domain/extension subsection.

### 8.5 Public operations

For every public function/method/class entry point, show the **exact current signature**.

```python
<function_name>(
    <arg>: <type>,
    *,
    <keyword_arg>: <type> = <default>,
) -> <return_type>
```

Then document:

- sync/async,
- positional vs keyword-only arguments,
- default values,
- side effects,
- mutation behavior,
- deterministic/stochastic behavior,
- randomness controls,
- registry/customization arguments,
- whether exceptions propagate.

### 8.6 Processing input vs reusable configuration

Explicitly separate them.

```markdown
**Per-call processing/request data**
- ...

**Reusable configuration/policy**
- ...
```

If the feature intentionally combines them in one object, show the exact nesting while still identifying which fields belong to which category.

### 8.7 Complete input contract

Start with the top-level input object.

```python
<TopLevelInput>(
    field_a: TypeA,
    field_b: TypeB,
    config: FeatureConfig,
)
```

Then expand **every field recursively**.

For every field provide:

| Field | Exact type | Required? | Default | Accepted values / range | Units | Meaning | Validation / cross-field rules |
|---|---|---|---|---|---|---|---|

Rules:

1. Show `tuple[...]`, `list[...]`, `Mapping[...]`, unions, optionals, typed IDs, and generic parameters exactly enough for consumer construction.
2. State collection uniqueness requirements.
3. State ordering requirements.
4. State minimum/maximum collection sizes.
5. State whether `None` has special meaning.
6. State whether zero is valid and what zero means.
7. State finite-number requirements.
8. State coordinate/grid alignment requirements.
9. State references to other IDs and whether referenced objects must exist.
10. State cross-field constraints.
11. State whether extra/unrecognized values are rejected when relevant.

### 8.8 Complete nested input type reference

For every non-trivial public nested input/config type, include a dedicated definition.

Example structure:

#### `FeatureConfig`

```python
FeatureConfig(
    alpha: float = 1.0,
    limits: Limits = Limits(...),
)
```

| Field | Type | Default | Rules | Consumer meaning |
|---|---|---:|---|---|
| `alpha` | `float` | `1.0` | finite, positive | `<explain effect>` |
| `limits` | `Limits` | `<exact default>` | `<exact rules>` | `<explain effect>` |

#### `Limits`

Continue with the complete `Limits` constructor and every field.

Continue recursively until no hidden public construction details remain.

### 8.9 Enum / literal / key values

List **every current accepted value**.

Example:

| Type | Member | Serialized/value form | Meaning |
|---|---|---|---|
| `ExecutionMode` | `PRODUCTION` | `"production"` | ... |
| `ExecutionMode` | `DEBUG` | `"debug"` | ... |

For registry keys, processor IDs, evaluator keys, feature IDs, constraint IDs, or profile IDs, list all shipped built-ins that consumers can reference.

### 8.10 Configuration reference

Document each configuration field with:

- exact type,
- exact default,
- enforced range,
- semantic effect,
- interaction with related fields,
- runtime/performance effect when material,
- whether changing it affects determinism,
- whether it is expected to be stable reusable policy or per-request data.

### 8.11 Built-in defaults and profiles

For each shipped default/profile/preset:

- exact public constant/factory name,
- what it configures,
- exact important values,
- all enabled components,
- all disabled components that consumers may reasonably expect,
- solver/search limits,
- weights,
- thresholds,
- tolerances,
- seeds,
- ordering,
- prerequisites,
- mutation policy,
- compatibility aliases.

Do not say only “use the default profile.” Show what the default actually contains when the structure is public and useful to consumers.

### 8.12 Recommended values

Use this format:

| Parameter | Package default | Enforced range | Recommended starting value/range | Basis |
|---|---:|---|---|---|
| `<name>` | `<value or none>` | `<validation>` | `<recommendation>` | Package default / built-in profile / project recommendation / domain-specific |

When there is no universal recommendation, say so explicitly.

### 8.13 Complete return contract

Show the exact top-level return type.

```python
<ReturnType>(...)
```

If wrapped:

```python
FeatureExecution[ResultType, DetailsType](
    result: ResultType,
    details: DetailsType | None,
    metadata: ExecutionMetadata,
)
```

Then recursively expand **every public output field** exactly as required for inputs.

For every output field state:

| Field | Exact type | Always present? | Possible `None`? | Units | Meaning | Mode/status conditions |
|---|---|---|---|---|---|---|

The consumer must know exactly what is received without inspecting source.

### 8.14 Result variants by mode

Provide an explicit matrix.

| Mode | Result type | `details` | Metadata | Other differences |
|---|---|---|---|---|
| `PRODUCTION` | ... | ... | ... | ... |
| `DEBUG` | ... | ... | ... | ... |

If the feature does **not** return `FeatureExecution`, state that clearly.

If DEBUG data can change shape by evaluator/processor/constraint, document those typed/structured variants or their documented mapping schema completely.

### 8.15 Result variants by status

If the feature returns statuses instead of raising for expected failures, provide a matrix.

| Status | Is success? | Result object present? | Main payload present? | Message/failure present? | Does it raise? |
|---|---|---|---|---|---|

State exactly which fields are safe to access for each status.

### 8.16 Exceptions and failure conditions

Provide an exhaustive consumer-relevant table.

| Exception / failure | Raised or returned? | Trigger | Useful fields | Consumer action |
|---|---|---|---|---|

For structured exceptions document fields such as:

- `.code`
- `.message`
- `.details`
- `.stage`
- `.processor_id`
- any other public attributes

Do not collapse distinct returned statuses and raised exceptions into a generic “may fail.”

### 8.17 Mutation and ownership behavior

State explicitly:

- whether inputs are mutated,
- whether results share mutable objects with inputs,
- whether lists/dicts/sets are copied,
- whether successful processing modifies an input object in place,
- whether rollback can restore prior state,
- whether returned objects should be treated as consumer-owned.

### 8.18 Determinism and reproducibility

State:

- deterministic or stochastic,
- seed field if present,
- worker-count effect if relevant,
- dependency/solver behavior that can affect reproducibility,
- recommended deterministic test configuration when source supports one.

### 8.19 Performance and safety limits

Document enforced limits such as:

- maximum node counts,
- maximum sweep lines,
- solver time limits,
- search trial counts,
- maximum passes,
- coordinate scaling,
- recursion/iteration caps,
- geometry complexity caps.

State which limits return a normal failure and which raise.

### 8.20 Complete minimal usage example

Provide a runnable or near-runnable example using only supported public imports.

The example must not contain unexplained placeholders for required values.

Bad:

```python
config = make_config_somehow()
result = feature(input, config)
```

Good:

```python
config = FeatureConfig(
    ... all required fields ...
)
request = FeatureRequest(
    ... all required fields ...
)
result = public_operation(
    FeatureInput(request=request, config=config)
)
```

If a required object is intentionally large reference data, either construct a complete small valid example or point to a fully documented built-in factory/profile that actually supplies it.

### 8.21 Consumer integration notes

Document important identity/compatibility rules, for example:

- room IDs must match a specification,
- hallway removals must be reflected in later specification use,
- candidate grids must remain identical between stages,
- normalized land must correspond to buildable land,
- post-processing should run before opening generation if openings are not preserved,
- outputs are immutable/mutable as applicable.

Only document relationships verified by current source.

### 8.22 Common consumer mistakes

List the few most likely integration mistakes that are directly supported by validation/runtime behavior.

### 8.23 Feature compatibility aliases

List every supported alias/deprecated compatibility name and its canonical replacement.

Do not omit an alias that remains publicly exported.

---

# 9. Shared Domain Contract Reference — Mandatory Template

The shared domain section must be a **complete construction/reference guide**, not merely a list of class names.

For every public shared domain type used by consumer-facing features, include:

1. exact public import,
2. constructor/signature,
3. all fields,
4. exact types,
5. defaults,
6. enum values,
7. units,
8. mutability,
9. validation expectations,
10. derived/convenience properties consumers may rely on,
11. identity semantics,
12. serialization/value semantics when explicitly supported.

Group them by domain, for example:

```text
Execution contracts
Geometry contracts
Land contracts
Candidate/grid contracts
Circulation contracts
Generation specification contracts
Floor-plan contracts
Opening contracts
Shared IDs/enums
```

## 9.1 No duplicate partial definitions

If a shared domain type is fully documented here, feature sections may link to this section, but the feature section must still state exactly where and why that type is used.

## 9.2 Exact enum inventory

Every public enum used by the package must have all relevant members and values listed.

## 9.3 Typed aliases

Document aliases such as typed string IDs sufficiently for consumer construction:

```python
RoomId("living")
```

State whether they are runtime classes, `NewType`, `TypeAlias`, enum-like values, or normal strings if that distinction matters to consumers.

---

# 10. Cross-Feature Compatibility Reference

Do not force a single orchestration pipeline.

Instead document verified compatibility edges.

Use a table like:

| Producer | Output | Consumer | Input | Compatibility requirement |
|---|---|---|---|---|
| `<feature>` | `<type>` | `<feature>` | `<type>` | `<identity/grid/spec/mutation requirement>` |

Examples of facts that may belong here when verified:

- exact shared grid requirements,
- exact room-ID/specification identity requirements,
- selected hallway subset behavior,
- normalized-land/buildable-land pairing,
- floor-plan mutation/copy behavior between post-processing/openings/scoring,
- profile compatibility,
- which feature outputs are not automatically converted and require consumer action.

If no direct compatibility exists, say so.

---

# 11. Extension and Registry APIs

If a feature supports custom evaluators, processors, constraints, features, registries, context factories, or similar extensions, document them as first-class public APIs.

For each extension point include:

- base protocol/ABC/interface,
- exact method signature,
- required return type,
- registration operation,
- uniqueness rules,
- configuration type requirements,
- production/debug contract rules,
- exceptions raised for invalid extensions,
- lifecycle/state assumptions,
- one complete custom extension example.

Do not document only built-ins if consumers are explicitly allowed to extend the feature.

---

# 12. Public Exception and Status Reference

Create a consolidated reference after feature sections.

## 12.1 Exceptions

| Feature | Exception | Base class | Public fields | Raised when |
|---|---|---|---|---|

## 12.2 Returned statuses

| Feature | Status enum | Member/value | Meaning | Payload availability |
|---|---|---|---|---|

This section does not replace feature-specific failure documentation; it provides a quick package-wide lookup.

---

# 13. Built-in Defaults and Profiles Reference

Create a consolidated package-wide table for shipped public presets.

| Feature | Public name | Type | Main purpose | Important exact values | Recommended use |
|---|---|---|---|---|---|

Do not hide profile internals that materially affect consumer behavior.

---

# 14. Compatibility / Legacy Surface Reference

List every active public compatibility alias or legacy type that still exists.

| Legacy/public compatibility name | Canonical name | Status | Behavioral differences | Migration note |
|---|---|---|---|---|

Do not label something deprecated unless the source/documentation actually marks it deprecated.

---

# 15. Consumer Integration Checklist

The final documentation must include a short practical checklist such as:

```markdown
Before integrating a feature:

- [ ] Use the preferred public import path.
- [ ] Construct the exact documented input/config types.
- [ ] Respect documented units and coordinate/grid conventions.
- [ ] Preserve required IDs between related contracts.
- [ ] Handle every documented returned status.
- [ ] Catch documented raised exceptions where appropriate.
- [ ] Do not assume DEBUG details exist in PRODUCTION.
- [ ] Respect documented mutation/copy behavior.
- [ ] Configure deterministic seeds/workers where reproducibility is required.
```

Add feature-specific checklist items only when verified.

---

# 16. Mandatory Public API Coverage Audit

Before finishing the documentation, perform an explicit coverage audit.

## 16.1 Feature-root exports

For each `fpg_core.<feature>` public export, classify it:

| Export | Documented section | Consumer-facing? | If omitted, exact reason |
|---|---|---|---|

No public export may disappear silently from the reference.

## 16.2 Package-root exports

Repeat for `fpg_core` and `fpg_core.domain` public exports that consumers are expected to use.

## 16.3 API operation audit

For every public callable verify:

- exact signature documented,
- every argument documented,
- every default documented,
- return documented,
- exceptions/status behavior documented.

## 16.4 Contract field audit

For every public input/output/config/result/details dataclass or equivalent contract verify:

- every field documented,
- every default documented,
- every nested public type expanded or linked to a complete canonical definition,
- every enum fully listed,
- every optional/`None` condition explained.

## 16.5 Mode audit

For every feature supporting execution modes verify:

- production shape,
- debug shape,
- whether `details` becomes `None`,
- whether result contract changes,
- whether metadata changes,
- whether production forbids debug-only payloads.

## 16.6 Error audit

Verify:

- every public base exception,
- relevant subclasses,
- structured error fields,
- normal failure statuses,
- validation exceptions,
- extension/registry failures.

---

# 17. AI Documentation Update Workflow

When this template is supplied together with a new `fpg-core` source tree, follow this workflow.

## Step 1 — Inventory the current package

Create a machine/source-backed list of:

- feature folders,
- feature-root exports,
- package-root exports,
- domain exports,
- public functions/classes/constants,
- configs/contracts/results/details,
- enums,
- exceptions,
- profiles/defaults,
- extension registries.

## Step 2 — Compare with existing documentation

Identify:

- added public symbols,
- removed public symbols,
- renamed symbols,
- changed signatures,
- changed fields/defaults,
- changed enum values,
- changed validation,
- changed return shapes,
- changed mutation behavior,
- changed statuses/exceptions,
- changed defaults/profiles,
- changed compatibility aliases.

Do not update only the obvious feature section. A shared type change may affect multiple feature sections.

## Step 3 — Trace every public operation end-to-end

For each operation inspect enough implementation to determine:

```text
public entry point
-> input validation
-> config validation
-> processing behavior relevant to consumers
-> result construction
-> execution envelope/mode behavior
-> returned statuses
-> raised exceptions
```

Do not document internal algorithm detail unless it helps consumers understand a parameter, output, determinism, performance, or failure.

## Step 4 — Expand all data structures

Recursively expand all consumer-visible inputs and outputs.

Stop expanding only when reaching:

- primitive Python values,
- completely documented enums,
- completely documented typed aliases,
- completely documented canonical shared contracts.

## Step 5 — Verify examples

Examples must use current public imports and current field names.

If code execution is available, import-check or run representative examples where practical.

## Step 6 — Run the coverage audit

Do not finalize until the audit in Section 16 has no unexplained gaps.

## Step 7 — Update change/migration notes

If the new package version changes a public contract, add a concise consumer migration note.

---

# 18. Required Style Rules for the Generated Consumer Documentation

The final reference should be detailed but easy to scan.

Use:

- short explanatory paragraphs,
- precise tables,
- exact Python signatures,
- exact constructor examples,
- clear headings,
- compact warnings for non-obvious behavior.

Avoid:

- marketing language,
- vague prose,
- repeated architecture discussion,
- long internal algorithm explanations,
- internal implementation names that consumers cannot import,
- speculative recommendations,
- duplicated shared contracts with conflicting descriptions.

Completeness takes priority over brevity for public data structures.

---

# 19. Forbidden Documentation Patterns

Do not produce any of the following.

## 19.1 Partial constructor

```python
FeatureConfig(
    required_field=...,
    # other options omitted
)
```

## 19.2 Partial result

```text
Returns a result containing the candidate, score, and other metadata.
```

Instead, enumerate every consumer-visible field.

## 19.3 Partial enum

```text
RoomType includes bedroom, kitchen, etc.
```

Instead, list every current relevant member and value.

## 19.4 Vague validation

```text
The package validates the geometry.
```

Instead, state the verified rules: convexity, rectilinearity, uniqueness, bounds, overlap, positive area, alignment, or whatever the actual feature enforces.

## 19.5 Hidden defaults

```text
Uses sensible defaults.
```

Instead, list exact defaults.

## 19.6 Fake universality

```text
Recommended hallway width is 10.
```

Do not write this unless source or project policy actually establishes that recommendation. Distinguish built-in defaults from domain standards.

## 19.7 Source-code dependency

```text
Consumers can inspect `config.py` for more options.
```

Never require that.

---

# 20. Documentation Verification Record — Required Final Section

Finish the generated package reference with a verification record.

Use this form:

```markdown
## Documentation Verification Record

Verified against the current supplied source:

- [ ] `pyproject.toml`
- [ ] `MANIFEST.in`
- [ ] package-root exports
- [ ] every feature-root `__init__.py` / `__all__`
- [ ] every public `api.py`
- [ ] public input/output/config contracts
- [ ] `fpg_core.domain` exports
- [ ] enums and typed IDs
- [ ] validation rules
- [ ] exceptions and returned statuses
- [ ] defaults/profiles
- [ ] extension registries/interfaces
- [ ] relevant tests
- [ ] mutation/copy behavior
- [ ] execution-mode differences
- [ ] examples/import paths
- [ ] compatibility aliases
- [ ] public API coverage audit

Known unverified areas:

- None.
```

If there are unverified areas, list them explicitly instead of writing `None`.

Do not claim the document is complete when required source was not available.

---

# 21. Final Acceptance Criteria

The generated consumer reference is acceptable only if all statements below are true.

- [ ] Every current public feature is documented.
- [ ] Every supported public operation has its exact signature.
- [ ] Every input object is fully expanded.
- [ ] Every configuration object is fully expanded.
- [ ] Every public nested input type is fully expanded or linked to a complete canonical shared definition.
- [ ] Every enum used by consumers has all current values listed.
- [ ] Every relevant built-in key/profile/preset is documented.
- [ ] Every output/result object is fully expanded.
- [ ] Every nested output type is fully expanded or linked to a complete canonical shared definition.
- [ ] PRODUCTION/DEBUG differences are explicit.
- [ ] Returned statuses are separated from raised exceptions.
- [ ] Validation and cross-field rules are documented.
- [ ] Units are documented wherever numeric values require interpretation.
- [ ] Mutation/copy behavior is explicit.
- [ ] Determinism/randomness behavior is explicit.
- [ ] Recommended values are distinguished from package defaults and hard validation rules.
- [ ] Examples use supported public imports.
- [ ] No required constructor contains unexplained placeholders.
- [ ] No public structure uses `...`, `etc.`, or intentionally omitted fields.
- [ ] No consumer must inspect source code to understand a public contract.
- [ ] Public export coverage has been audited.
- [ ] Any breaking or migration-relevant changes are documented.
- [ ] Any unverified area is explicitly disclosed.

If any checkbox fails, continue documenting before presenting the reference as complete.

---

# 22. Instruction to the AI Using This Template

When the user says something similar to:

> “Generate/update the full `fpg-core` package documentation for consumer projects using `Package_Documentation_Template.md`.”

You must treat this template as a completeness contract.

Do not optimize the consumer documentation by removing fields or collapsing structures.

The desired result is **transparent rather than short**:

- concise explanations,
- exhaustive contracts,
- exact inputs,
- exact outputs,
- exact defaults,
- exact accepted values,
- exact failure behavior,
- no guessing.

The package consumer should be able to integrate `fpg-core` from the finished documentation without opening the package source.
