# 0001 Database profile authority

**Accepted.** Use the existing profile table for all persistent experiment
configuration. File-backed policies could diverge across setup, headless tools
and runs. A shared profile ID and hash let consumers use the same policy and let
section editors reject stale drafts. Keep the E02A-derived baseline in seed
source for fresh initialization and explicit promotion. Retain E03A's Decimal
hard sizing rules under `experiments.e03a` because they express a separate
analytical model. Refresh shared inputs by explicit action.
