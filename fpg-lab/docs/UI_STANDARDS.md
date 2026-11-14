# FPG-Lab UI Practices

**Status:** Canonical Lab UI guideline for implemented pages and future experiments.  
**Scope:** FPG-Lab's research application UI only. Not a contract for `fpg-core`.

## Purpose and priority

FPG-Lab is a desktop-oriented research tool. Optimize for efficient use of the entire available screen, particularly visual analysis, rather than mobile responsiveness or decorative presentation.

Order of priorities:

1. Correct experiment workflow and result interpretation.
2. Large, readable working/visualization space; use available viewport width **and height**.
3. Clear information hierarchy and convenient controls.
4. Consistency across experiments, while preserving experiment-specific functionality.
5. Appropriate visual polish and keyboard/accessibility basics.
6. Mobile layout is intentionally low priority. Avoid unnecessary mobile-specific rewrites.

Preserve the existing FPG-Lab dark-theme identity unless an actual usability problem justifies a change. Avoid narrow centered page wrappers, oversized headings, excessive card nesting and redundant instructions.

## Shared page structure (required)

Each existing and future experiment has:

- **Experiment listing:** the FPG-Lab main page lists experiments as cards.
- **Experiment setup page:** choose inputs, configure the run, inspect or validate setup, start it, and discover prior runs when applicable.
- **Experiment result page(s):** inspect **one specific run**. Separate result/detail/drill-down pages are allowed when useful.

This is a **workflow contract**, not a requirement to share identical forms, plots, persistence, or algorithms. Research experiments may vary greatly in what a run means and what can be inspected. Every existing experiment is brought into this structure where necessary.

### Naming

Use meaningful existing names such as *Experiment*, *Setup*, *Run*, *Results*, and experiment identifiers (e.g., E01A, P01A). Shorthand such as **EE**, **EM**, and **ER** is only conversational convenience; **do not** introduce it into product text, public API names, directory names, documentation headings, or component names.

## Action-button semantics (required)

Buttons express **intent**, not just visual priority; choose a role based on what the action does. The label and disabled/feedback states must still explain the action without relying on color alone.

| Role | Appearance | Use |
| --- | --- | --- |
| `main` | **Green filled** | The principal workflow trigger: start/run/simulate, save, apply, or activate. |
| `danger` | **Red** (filled or outlined/flat when secondary) | Destructive or interruptive operations: delete, discard/reset edits, terminate a running experiment. |
| `general` | **Blue** (filled or outline) | Regular non-dangerous actions: open, validate, preview, import, navigate, playback. |
| `subtle` | **Neutral transparent / ghost** | Low-priority or repetitive actions: refresh, cancel/close, clear selection, copy, and auxiliary shortcuts. |

Implementation: use `fpg_lab.ui.components.action_button(label, role=..., ...)` for Lab action buttons, retaining ordinary NiceGUI `.props('dense')` / `.props('outline')` where needed. **Do not duplicate per-page hex colors or use the green role for every button merely because it appears first.** Keep one unmistakable main action per decision area when practical. Red means deletion, disruption, or loss of work, not a generic "negative" response. Icon-only buttons need an accessible description. Do not apply these semantics to tabs, view selectors, checkboxes, statuses, graph colors, or navigation links as if they were action buttons.

## Experiment listing groups and identifier display

- Group experiment cards by their **leading category letter** and separate groups with a horizontal divider; do not render category heading labels. Add new categories as required without changing existing family codes.
- Show the experiment identifier prominently in a legible **monospace, semibold/bold** style: `P01A` appears as **`P-01-A`** and `E01A` as **`E-01-A`**. Use the same display formatting in experiment page headings when appropriate.
- This is **presentation-only formatting**. Python flow names (`p01a`), persisted identifiers, route paths (`/experiments/p01a`), export schemas and family documentation names remain unchanged. Do not rename internal identifiers to include hyphens.

## Run result page: non-prescriptive reference layout

```text
+--------------------------------------------------------------+
| Existing application navigation                              |
+--------------------------------------------------------------+
| Compact result title / status            [Main-view choices] |
+------------------------------------------+-------------------+
|                                          | Main controls     |
|                                          | actions, playback |
|           PRIMARY VIEW                   | stage, selectors  |
|                                          +-------------------+
|  Canvas by default when one exists.      | Contextual info   |
|  Otherwise a chart, diagram, table,      | legend, labels,   |
|  or another experiment-specific view.    | metrics, details  |
|                                          |                   |
|    Independent vertical scroll           | Independent       |
|                                          | vertical scroll   |
+------------------------------------------+-------------------+
```

**Mandatory intent, flexible implementation:**

- Keep global navigation. Below it, use a **short title/toolbar row**, not a tall hero/header.
- The main view occupies **all remaining practical height** and the large majority of horizontal space. Do not bury the primary canvas beneath multiple cards, charts or verbose status sections.
- A narrower right sidebar occupies the remainder. Its width is bounded enough that the primary view remains dominant on ordinary desktop displays; avoid an unnecessarily large sidebar.
- The **main-view region and right sidebar scroll independently**. Define a bounded viewport/workspace height and the correct grid/flex `min-width: 0` / `min-height: 0` constraints; avoid the entire document growing because of sidebar data.
- Split the sidebar conceptually into **(1) primary controls/actions** and **(2) contextual information**. The second section changes with the selected main view. Exactly how those sections are grouped, divided, or scrolled is experiment-dependent.
- Prefer the existing view component, plotter, and controls, not a framework-wide abstraction that every experiment must awkwardly fit.
- Use single-selection controls (radio/segmented/toggle group) in the compact toolbar for the available **primary views**. If there is only one meaningful primary view, no redundant selector is necessary.
- Default to **Canvas** when the experiment has one; otherwise choose the most important supported view.
- Selecting a different primary view (e.g., Charts, Diagram, Trials, Table) replaces the **primary display**; contextual sidebar information follows the active view. Do not display every major chart below the canvas by default.
- Experiment-specific overlays (e.g., floor-plan, paths, heatmap, circulation), iterations, frames, and pipeline stages can be **secondary controls within the Canvas view** rather than universal toolbar modes. Avoid duplicate selectors for the same state.
- Retain essential status, warnings, errors, selected run/frame, key metrics, legends and unit information without forcing users to open raw JSON. Put low-frequency diagnostics/provenance behind contextual or alternate views.
- Preserve viewport/zoom, selected stage, frame and filters across normal state updates or polling when practical. Recompute expensive plots only when necessary.
- An experiment with no canvas should still use the same **visualization-first principles**; do not create a blank canvas just to conform to the reference.

## Other page practices

**Experiment listing:** full-width, compact, consistent experiment cards grouped by category prefix, with visible dividers and clearly formatted identifiers. Group peers in a fluid grid and avoid unnecessarily narrow center wrappers or tall, empty cards.

**Setup pages:** prioritize configuration and validation workflow, keep run-start action identifiable, and keep history accessible where the experiment retains it. Preview space may be substantial and may use a different layout than the result reference. Do not force result-page sidebar conventions onto setup forms.

**Secondary run pages:** trial inspection, pipeline-stage detail, and floor-plan branch pages retain clear parent-run navigation and use the result layout where a primary visualization exists. Preserve useful deep links.

## Visual, interaction and engineering guardrails

- Use established NiceGUI/Quasar elements, Plotly and existing FPG-Lab components/styles. Reuse before adding new components or dependencies.
- Centralize reusable layout CSS/classes and semantic colors; experiment-specific needs can use small, documented variants.
- Use a compact spacing rhythm and consistent edge alignment. Avoid duplicated titles, status panels and nested cards.
- Preserve visible hover/focus/selected/disabled/loading/error/empty states. Use labels, not color alone, for important meaning.
- Preserve geometry aspect ratios, project units, plot interaction and readable legends when resizing or switching views.
- Optimize visually for normal and wide desktop viewports, including shorter laptop screens. Do not spend significant effort on phone layouts. Under constrained widths, prefer predictable min-width/overflow rather than collapsing the research workspace into an unusable mobile UI.
- Keep page-local UI state in the UI. UI callbacks may read experiment snapshots or invoke the runtime, but workers and Core must never depend on NiceGUI elements.
- Preserve snapshot integrity, run IDs, progress, termination, export/copy, history, error recording and all experiment-specific analysis behavior.
- No Core algorithm changes, UI framework migration or persistence redesign solely to achieve matching layouts.

## Extending with future experiments

For each new experiment, decide:

1. Its setup inputs and run-start action.
2. Whether and how a run/result is retained; links must identify a specific run.
3. Its primary result view and default selection.
4. Available alternate primary views and when each appears.
5. Common actions/controls and contextual information for each view.
6. Which experiment-specific views, overlays or data need an explicit layout exception.
7. How to verify the workflow and desktop viewport/scroll behavior.

Follow the shared structure, then document intentional deviations. **This layout is a reference, not a rigid template.** Experiment-specific scientific/technical needs take precedence over pixel-identical screens.

## Documentation ownership after implementation

This is the canonical file. Keep it linked from `fpg-lab/docs/README.md`, `fpg-lab/AGENTS.md`, and `.agents/skills/fpg-lab-experiments/SKILL.md`. Update family docs for changed workflows without duplicating these global rules.

## Current implementation (NiceGUI)

- `fpg_lab/ui/result_layout.py::ResultWorkspace` provides the compact title/view row, full-height main region, scrollable sidebar, per-view main containers and per-view context containers. It is a layout primitive, not a fixed experiment schema.
- `fpg_lab/ui/components.py::shell` owns the shared theme/header and workspace CSS, while `action_button` defines semantic action colors and `format_experiment_code` formats user-visible identifiers. Ordinary setup and editor pages retain normal document flow; only result pages add the `lab-result-root` class.
- Create a `ResultWorkspace` with an explicit parent setup link and meaningful view labels, then populate `workspace.main('...')`, `workspace.controls` and `workspace.context('...')`. Keep view-specific state and callbacks inside the owning experiment page.
- The result workspace has a sidebar sized at approximately 26.5vw (bounded to 290–390px) and a fluid, larger main region. Both have independent vertical overflow. Narrow browser windows may use horizontal overflow: mobile adaptation is deliberately out of scope.
- Canvas views must actually **fill the available main-pane height**, not merely set `min-height`. When embedding Plotly inside additional containers (as P01A replay does), give each intermediary flex/container a definite height; otherwise the plot can stop at its minimum size and leave unused vertical space.
- **E01A exception:** the setup passes each result once through NiceGUI `app.storage.tab`, and the result page consumes it. Its URL identifies the temporary execution but is not saved, shareable across tabs, or recorded in history. Reloading, leaving the result, or restarting the server loses it, matching E01A's original session-only behavior.

## Required UI verification for result-page changes

From a running Lab app, check at **1280×720**, **1440×900**, and **1920×1080**:

- Global navigation and the compact title/view row stay visible; the main view
  grows in both dimensions and remains substantially wider than the sidebar.
- Scrolling a long sidebar does not scroll the main view, and scrolling lengthy
  Charts/Diagnostics does not scroll the sidebar. Canvas geometry remains square
  in project units, with usable Plotly pan/zoom after view switching.
- E01A: start from a preset, switch path overlays, select/clear routes, open Room
  statistics, and reload to verify the temporary result becomes unavailable.
- P01A: inspect queued/completed runs; replay, scrub, filter rooms/paths, open
  Charts and Trials, seek a trial, open its detail URL, and check no-debug fallback.
- P01B/C: switch iterations and stages, inspect missing stages, toggle hints only
  when enabled, inspect Scores/Diagnostics, terminate where permitted, and copy a
  P01C final plan into E01A.
- Keep error/empty states usable without a populated canvas. Do not add a fake
  chart just to satisfy the reference diagram.
