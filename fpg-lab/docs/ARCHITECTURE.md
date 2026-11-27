# Lab architecture

Lab owns UI, worker and analysis orchestration, experiment policy and persistence.
Core provides reusable algorithms and public types. Imports go from Lab to
[Core's public API](../../docs/API_GUIDE.md). Keep SQLite, NiceGUI and prepared
inputs in Lab.

The database is authoritative for persistent configuration. A single named
record can be selected by UI, headless scripts and tools, and transactions give
section editors a shared conflict check. Read operations leave records intact.
A draft becomes persistent on save. Use the selected ID, or resolve the active
record when the ID is omitted. Seed assets supply maintenance operations and
prepared inputs such as hint maps remain separately portable.

Four values identify different things. SQLite `user_version` is the database
revision. The profile payload uses Lab schema 6, which maps to Core aggregate
schema 2. The installed Core package version identifies the validator and
execution dependency. The configuration hash identifies the normalized saved
document and guards edits. Persistent run submission captures the profile ID,
hash and effective inputs. E03A keeps analysis and locks in the tab and saves only
its typed portion of a profile. See [configuration ownership](adr/0001-profile-authority.md).

Runs are local research observations. Keep current results readable and export
selected records when a particular observation matters. Historical execution and
result compatibility are unnecessary for developing current research flows.
Profiles, templates, saved P01B presets and E02B plans remain useful across
runs. See [maintenance and run retention](adr/0002-maintenance.md).

E and P describe research scope. Choose useful views, stages, storage and
execution mechanisms for each question. Use [existing patterns](EXPERIMENTS.md)
when they fit.

Shared execution utilities live in `fpg_lab.core.results`, database row
materialization in `fpg_lab.database.serialization`, and portable hint-map
validation in `fpg_lab.integrations.fpg_core.hint_map`. P01 trial export remains
owned by `p01b_input`. The `BackgroundExecutor` serves P01, E02 and quick hint
work; workers own their database sessions.

Portable floor-plan decoding lives in `integrations.fpg_core.floor_plan`;
E02A stage export assembly remains in `integrations.fpg_core.e02a_export`.

The shared refinement profile and candidate-hint conversion live under
`integrations.fpg_core.solver` and `hint_map`; stage ordering, failure policy
and persistence remain in each experiment flow.

The shared `ResultWorkspace` supplies view switching, a dominant main area and
contextual sidebar; E03A embeds it below its profile selector. Setup pages adapt
the same priorities to their task. See [UI composition](adr/0003-ui-workspaces.md)
and [UI standards](UI_STANDARDS.md).
