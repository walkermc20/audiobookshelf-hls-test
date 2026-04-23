# audiobookshelf-hls-test

A tiny test harness for verifying that an
[Audiobookshelf](https://github.com/advplyr/audiobookshelf) server produces
HLS output in a shape that an iOS `AVAssetDownloadURLSession` can consume,
including manifest URLs that survive the playback session being closed.

Built to scope a proposed server-side change: add opt-in persistent HLS
output so a third-party iOS client (such as
[ShelfPlayer](https://github.com/rasmuslos/ShelfPlayer)) can collapse its
dual streaming / downloaded-file paths into a single `AVPlayer` pipeline
over HLS.

## What it does

- Serves a single-page HTML test client at `http://localhost:8088`.
- Proxies `/upstream/api/...` and `/upstream/hls/...` from the page to a
  user-configured ABS server (per-request `x-upstream` header).
- Uses [hls.js](https://github.com/video-dev/hls.js) to play the HLS
  manifest returned by `POST /api/items/:id/play` with
  `forceTranscode: true`.
- Logs every manifest and segment request so you can see the full flow.

## What it proves

**Against an unmodified ABS:**

1. The existing play endpoint returns an HLS manifest URL when the client
   asks for transcode.
2. The manifest is complete up front (all segment entries listed, so the
   manifest is compatible with `AVAssetDownloadURLSession`'s model of
   "asset download").
3. Segment auth is session-ID-as-bearer, which works cleanly with
   AVFoundation's segment fetcher.

**Against a fork with persistent HLS enabled:**

4. Manifest URLs continue to serve segments from disk after the playback
   session closes, after the server idle-expiry runs, and across container
   restarts. That is the prerequisite for multi-day
   `AVAssetDownloadURLSession` downloads.

## Automated test suite

The "4. Automated test suite (fork only)" section of the page runs 14
tests in sequence against a live fork. Three inputs are needed: an ABS
base URL, two users' API tokens (a real second user — not a second API
key attached to the first user), and a library item ID. Each run
creates and cleans up its own sessions.

The suite builds a scenario where session A is auto-closed by the
creation of session B (which exercises the persistence path), then
walks through both the in-memory and marker-based auth branches of
`DELETE /api/session/:id/hls-cache`, a full manifest 404 round-trip,
idempotency, and the edge-case UUID handling.

| # | Test | Expected |
|---|---|---|
| 1 | User 1 token valid (`GET /api/me`) | `200` |
| 2 | User 2 token valid (`GET /api/me`) | `200` |
| 3 | Create session A — User 1, `mediaPlayer: "ios-hls"` | uuid, `playMethod=2` |
| 4 | Manifest A fetchable (session still in memory) | `200` |
| 5 | Create session B — User 1, auto-closes A | new uuid |
| 6 | Manifest A still serves after A closed (persistence) | `200` |
| 7 | User 2 DELETE on session A → cross-user blocked via marker | `403` |
| 8 | Manifest A still serves after the forbidden DELETE | `200` |
| 9 | User 1 DELETE on session A (owner) | `200` |
| 10 | Manifest A 404 after owner DELETE (full round-trip) | `404` |
| 11 | DELETE session A again (idempotent) | `200` |
| 12 | DELETE with non-UUID path | `400` |
| 13 | DELETE with unknown UUID (idempotent) | `200` |
| 14 | Cleanup: DELETE session B | `200` |

Critical tests (1, 2, 3, 5) abort the run if they fail — subsequent
tests depend on their side effects. Non-critical tests continue so a
failure in one row doesn't mask results for the rest.

What each group proves:

- **1-2** — auth plumbing and the fact that User 2 is actually a
  distinct user (an API key attached to User 1 would silently pass
  ownership checks elsewhere).
- **3-5** — the play-endpoint opt-in path produces an HLS response
  and multiple sessions for the same user auto-close prior sessions.
- **6** — the persistence invariant: manifest URLs outlive their
  session's in-memory lifetime.
- **7-8** — marker-based cross-user authorization works *and* a
  forbidden DELETE leaves the cache intact (not a partial-delete).
- **9-10** — the legitimate teardown path actually removes the files
  and subsequent fetches return 404.
- **11-13** — idempotency on repeat, bogus UUIDs, and unknown UUIDs
  — all the shapes a crashed or buggy client might send.
- **14** — kill-ffmpeg-before-rm works when the session being deleted
  is still in memory (session B hasn't been auto-closed yet).

## Running

Requires Python 3.7+ (uses only stdlib).

```bash
python server.py
# open http://localhost:8088 in a browser
```

In the page:

1. Fill in your ABS base URL and an API token (Settings → Users → API Token
   in ABS).
2. Click **Browse libraries / items** to confirm auth.
3. Click **Request playback session & load** — should play audio via HLS.

See `fork-deploy/docker-compose.fork.yml` for a sample parallel deployment
of a forked ABS with the persistent-HLS patch enabled.

## Test run archive

See [`test-runs/`](./test-runs/) for recorded end-to-end runs of the
automated suite against the fork. Each run is a markdown file with
metadata, the 14-test matrix, observations, and a scoped server-log
excerpt. Most recent:
[2026-04-23 / `93ac4c6c` / 14 of 14 PASS](./test-runs/2026-04-23_93ac4c6c_14of14.md).

## Related

- Reference server-side patch: https://github.com/walkermc20/audiobookshelf/commit/ac47208a
- Public test image: `ghcr.io/walkermc20/audiobookshelf:ios-hls-persistent`
