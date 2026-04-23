# test-runs

Archive of test-suite runs executed against a live Audiobookshelf fork
that has the iOS HLS persistent-cache feature enabled
(`ENABLE_IOS_HLS_PERSIST=1` or `enableIosHlsPersist: true` in
server settings).

## What's recorded here

Each file in this directory captures a single end-to-end run of the
automated test suite (the "4. Automated test suite (fork only)" fieldset
in [index.html](../index.html)). A run is considered worth archiving
when it validates or regresses one of:

- the persistence invariant (manifest URL survives session close and
  server restart),
- cross-user DELETE authorization,
- idempotency of `DELETE /api/session/:id/hls-cache`,
- round-trip semantics (DELETE → 404 on subsequent GET),
- ffmpeg-exit race handling.

## Filename convention

```
YYYY-MM-DD_<branch-or-shortsha>_<result>.md
```

Example: `2026-04-23_93ac4c6c_14of14.md`

Use the fork server's commit SHA (short), not the test-harness SHA.

## What each run file contains

1. **Metadata** — run date/time, fork commit, image tag, server version,
   test client version, which two users (by role), which library item.
2. **Matrix** — the full 14-test table with expected / actual / result.
   Copy from the browser UI verbatim.
3. **Observations** — anything notable: timing, performance, log noise,
   deviation from prior runs, partial-transcode coverage.
4. **Server log excerpt** — the relevant portion of the fork's daily
   log (`$METADATA/logs/daily/YYYY-MM-DD.txt`). Trim to the run
   window; keep stack traces; redact tokens.

## When to archive a run

- After any commit that touches the persistence path, DELETE handler,
  ownership check, or orphan sweeper.
- Before filing / refreshing the upstream PR.
- If the suite regresses — archive the failure, then archive the
  subsequent fix run to document the delta.

Skip archiving for purely cosmetic changes, README-only edits, or
repeat runs with no meaningful variable change.
