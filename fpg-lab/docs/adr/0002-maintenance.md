# 0002 Explicit maintenance and disposable runs

**Accepted.** Adopt reviewed SQLite schema as revision 1 and add explicit
migration, seeding and reset commands. Startup can recover interrupted jobs.
Schema and profile evolution require an explicit command with a report and a
transaction. Research history has a short useful lifetime and broad compatibility
would compete with current experiments. Retain reusable inputs on a run reset
and export individual records worth retaining.
