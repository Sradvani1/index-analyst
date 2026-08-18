# PR-28: Daily Podcast Generation

**Status:** Complete

## Summary

Adds daily ~3-minute single-host podcast generation to the pipeline. A new
`generate-podcast` CLI command condenses the existing Substack article into a
TTS-optimized script via Gemini, then synthesizes it with Gemini TTS
(`gemini-3.1-flash-tts-preview` on the Interactions API) and encodes it to MP3
with ffmpeg. The audio is stored locally under gitignored `output/<date>/`;
the script text is mirrored to `memory/daily_reports/` and surfaced (with an
audio player) in the web viewer. Distribution is manual — upload the MP3 to
Substack, whose native podcast feed (`<pub>.substack.com/feed`) then includes
the episode automatically. No RSS code is required.

## Configuration

```env
SPX_GOOGLE_TTS_MODEL=gemini-3.1-flash-tts-preview
SPX_PODCAST_VOICE=Orus
SPX_GOOGLE_PODCAST_MAX_OUTPUT_TOKENS=4000
```

`GOOGLE_API_KEY` must be set (shared with the analytical pipeline). ffmpeg and
ffprobe must be installed for MP3 encoding and duration measurement.

The TTS input is prepended with a hardcoded style directive (`TTS_DIRECTIVE` in
`src/podcast_tts.py`) that requests a calm, measured, professional financial-news
delivery with steady pacing; the Gemini TTS API has no separate style field, so
tone is controlled inline. The stored script/transcript is the clean prose only.

## Implementation

- Added `PodcastScript` schema (`title` + continuous prose `script`).
- Added `src/podcast.py`: `PODCAST_INSTRUCTIONS` system prompt (single host,
  numbers/abbreviations spelled out, no headings/Markdown, no em
  dashes/colons/semicolons, no Monte Carlo or advice), `build_podcast_prompt`
  (HTML-unescapes the stored article), and `parse_podcast_response` /
  `validate_podcast_script` (word-count bounds 380-520, Markdown-artifact
  rejection).
- Added `run_podcast_script()` to `GooglePipelineClient` mirroring the Substack
  pass (schema-constrained JSON, default thinking, per-pass token budget).
  Intentionally not on the `PipelineLLMClient` protocol — Gemini-only; other
  providers untouched.
- Added `src/podcast_tts.py`: `PodcastTTSClient` calling
  `client.interactions.create()` with an audio response format and a prebuilt
  voice, decoding the base64 PCM (`audio/l16; rate=24000; channels=1`), piping
  it to ffmpeg for MP3 encoding, and measuring duration with ffprobe.
  Transient errors retry (reuses the pipeline's retry predicate); out-of-range
  durations are reported as warnings, never failures.
- Added `generate-podcast --date` CLI command for on-demand generation (not
  wired into the daily cron; run manually when an episode is wanted).
- Persisted the Substack editorial pass token telemetry (`input_tokens`,
  `output_tokens`, `cache_read_tokens`, `latency_ms`) in `run_log.json` so the
  daily pass costs can be tracked alongside the podcast telemetry already
  stored in `<date>-podcast-script.json`.
- Web viewer: `RunDetail` gained `podcast_script` + `podcast_audio`;
  `GET /api/runs/{date}/podcast.mp3` streams the gitignored MP3; a new
  `PodcastView` component renders the audio player and script on the run page.
- Artifacts: `output/<date>/<date>-podcast.mp3` (gitignored),
  `output/<date>/<date>-podcast-script.{md,json}`, and a committed mirror of
  the script at `memory/daily_reports/<date>-podcast-script.md`.

## Tests

- `tests/test_podcast.py` — prompt unescaping, parse/validate paths (bad JSON,
  word-count bounds, Markdown artifacts, extra fields).
- `tests/test_google_pipeline_client.py` — mocked-SDK assertion of schema,
  instructions, and `max_output_tokens` for `run_podcast_script`.
- `tests/test_podcast_tts.py` — base64/bytes decoding, mocked synthesis,
  ffmpeg failure, transient retry, and a real-ffmpeg encoding test.
- `tests/test_web_api.py` — podcast fields in `/api/runs/{date}` and the audio
  endpoint (200/404/bad-date).
- `tests/test_podcast_live.py` (`-m live`) — short real TTS clip.

Verified end-to-end on 2026-08-14: 450-word script, 162s MP3 (~3 minutes).

## Scope

Generation and local preview only. No RSS/feed code, no audio upload, no
intro/outro, no multi-speaker. Script generation uses the Gemini provider.