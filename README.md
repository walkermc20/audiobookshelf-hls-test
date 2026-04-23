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
