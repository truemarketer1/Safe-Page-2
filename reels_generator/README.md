# Reels Hook Generator

Fully automated pipeline that turns a list of text hooks into ready-to-post
Instagram Reels, using a HeyGen AI avatar for the hook and FFmpeg to stitch
each hook onto a single pre-recorded "core message" video.

```
hooks.csv  ──►  HeyGen (avatar + voice clone)  ──►  FFmpeg concat  ──►  reel_*.mp4
```

## What's in here

```
reels_generator/
├── reels/
│   ├── config.py         env-driven settings (.env supported)
│   ├── heygen.py         HeyGen v2 client: submit + poll + download
│   ├── stitcher.py       FFmpeg concat with scale/pad normalization
│   ├── hooks_source.py   CSV + Google Sheets readers
│   ├── pipeline.py       parallel orchestration, caching, error collection
│   └── __main__.py       `python -m reels ...` CLI
├── tests/                pytest suite (network + ffmpeg fully mocked)
├── examples/
│   ├── hooks.example.csv
│   └── make_scenario_blueprint.json     Make.com import-ready blueprint
├── .env.example
└── requirements.txt      only needed for the Google Sheets reader
```

## One-time setup

1. **Train your HeyGen Instant Avatar** at https://app.heygen.com. Record
   2-5 minutes of yourself speaking to the camera. Note the resulting
   `avatar_id` and cloned `voice_id`.
2. **Record the core message once** and save it as `core_message.mp4` at
   1080x1920 (or whatever the `VIDEO_WIDTH`/`VIDEO_HEIGHT` env vars are set to).
3. **Install FFmpeg** and make sure `ffmpeg` is on your `PATH`
   (https://ffmpeg.org/download.html).
4. **Copy the env file and fill it in:**
   ```bash
   cp .env.example .env
   ```

## Daily workflow

```bash
# 1. Drop your 20 hooks in hooks.csv (one per line, or with a "hook" header)
#    or point HOOKS_CSV_PATH at a different file.

# 2. Run the pipeline.
python -m reels run --hooks-csv examples/hooks.example.csv

# Output:
#   Finished 5/5 reels
#     ok  #1: output/reel_001_most_people_will_never_figure_this_out.mp4
#     ok  #2: output/reel_002_i_used_to_think_burning_fat_was_about.mp4
#     ...
```

Each run:

- Submits every hook to HeyGen in parallel (up to `MAX_PARALLEL_GENERATIONS`).
- Polls each video until render is complete, then downloads it to
  `.hook_cache/` keyed by `sha256(avatar_id|voice_id|text)` — **re-running is
  free** for hooks you've already generated.
- Stitches each hook to `core_message.mp4` via FFmpeg's concat filter,
  normalizing both clips to a common resolution/fps/audio sample rate so the
  join is seamless.
- Writes the finished Reels to `output/reel_*.mp4` (H.264 + AAC, `+faststart`
  so Instagram accepts them without re-processing).

## Stitch only (no HeyGen)

If you generated a hook video elsewhere, skip the API:

```bash
python -m reels stitch \
  --hook hook.mp4 --core core_message.mp4 --output final.mp4
```

## Google Sheets input (optional)

```bash
pip install -r requirements.txt
python -m reels run \
  --sheet-id 1AbCdEf... \
  --sheet-range 'Hooks!A2:A' \
  --service-account ./gcp-service-account.json
```

Share the sheet with the service account's email (read access is enough).

## Make.com alternative (no local Python)

`examples/make_scenario_blueprint.json` is an import-ready scenario:

1. In Make.com, **Create scenario → Import blueprint** → select that JSON.
2. Reconnect the Google Sheets and Google Drive modules to your accounts.
3. Set `HEYGEN_API_KEY`, `HEYGEN_AVATAR_ID`, `HEYGEN_VOICE_ID` in the
   scenario's environment variables.
4. Replace `YOUR_SHEET_ID` and `YOUR_DRIVE_FOLDER_ID`.

The scenario watches the sheet for new rows, POSTs to HeyGen's generate
endpoint, polls `video_status.get` until `status=completed`, downloads the
rendered mp4, and uploads it to Drive. Stitching still needs to happen
locally (or via a follow-up scenario that calls an FFmpeg service).

## Environment variables

| Var | Required | Default | Notes |
| --- | --- | --- | --- |
| `HEYGEN_API_KEY` | ✓ | – | From https://app.heygen.com/settings?nav=API |
| `HEYGEN_AVATAR_ID` | ✓ | – | Your Instant Avatar id |
| `HEYGEN_VOICE_ID` | ✓ | – | Your cloned voice id |
| `CORE_VIDEO_PATH` |   | `core_message.mp4` | 1080x1920 recommended |
| `HOOKS_CSV_PATH` |   | `hooks.csv` | Fallback when `--hooks-csv` not passed |
| `OUTPUT_DIR` |   | `output` | Final stitched Reels land here |
| `CACHE_DIR` |   | `.hook_cache` | Generated hook mp4s are cached here |
| `VIDEO_WIDTH` / `VIDEO_HEIGHT` |   | `1080` / `1920` | Reels = vertical 9:16 |
| `POLL_INTERVAL_SECONDS` |   | `5` | How often to poll HeyGen status |
| `POLL_TIMEOUT_SECONDS` |   | `600` | Fail a hook after this long |
| `MAX_PARALLEL_GENERATIONS` |   | `4` | Concurrent HeyGen submissions |

## Running the tests

```bash
pip install pytest
cd reels_generator
python -m pytest
```

The suite uses only the standard library plus `pytest` — network calls,
HeyGen polling, and FFmpeg execution are all mocked so the tests run
offline and without FFmpeg installed.

## Cost reality check

- **HeyGen** — Creator plan (~$29/mo) gives ~15 minutes of generation. 20
  hooks × ~4s ≈ 80s/day, which fits comfortably. Bulk days may need the
  Team plan or add-on credits.
- **Make.com** — Free tier's 1000 ops/mo covers ~200 hooks/mo end-to-end.
- **FFmpeg + Python** — Free.
