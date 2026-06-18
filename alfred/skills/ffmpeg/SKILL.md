---
name: ffmpeg
description: Local media processing with ffmpeg — extract audio to MP3, transcode formats, trim segments, capture frames, resize, and concatenate. Real ffmpeg binary; deterministic, offline, no network. Binding-only in the thesis benchmark.
---

# ffmpeg Skill

Use this skill for local audio/video processing. Unlike the mock skills, this wraps the
**real `ffmpeg` binary** — it is deterministic, offline, and side-effect-contained (it only
reads/writes local files). It is a strong **composite** customer: real multi-step DAGs that
chain file artifacts between steps.

> **Binding-only in the benchmark.** We score command correctness (does the reflexer emit the
> right flags?) and do not execute against the user's files during evaluation. The commands
> below are the gold grammar; the discriminating flags are noted.

## Commands (via bash) — invoke `ffmpeg` directly

### Extract audio to MP3 (discriminator: `-vn -acodec libmp3lame`)
`ffmpeg -i "<input>" -vn -acodec libmp3lame "<output>.mp3"`

### Transcode container/format (output extension sets the target)
`ffmpeg -i "<input>" "<output>.<ext>"`

### Trim a time segment (discriminator: `-ss … -to …`)
`ffmpeg -i "<input>" -ss <start> -to <end> -c copy "<output>"`

### Capture a single frame (discriminator: `-vframes 1`)
`ffmpeg -i "<input>" -ss <time> -vframes 1 "<output>.png"`

### Resize / scale to a target width (discriminator: `-vf scale=W:-1`)
`ffmpeg -i "<input>" -vf scale=<width>:-1 "<output>"`

### Concatenate files from a list (discriminator: `-f concat`)
`ffmpeg -f concat -i "<list.txt>" -c copy "<output>"`

## Notes
- Timestamps are `HH:MM:SS` or seconds.
- `-c copy` does a stream copy (fast, no re-encode) for trim/concat.
- Composite `composite_ffmpeg_clip_to_gif` chains **trim → transcode** (to `.gif`).
- ffmpeg actions about *audio* (`extract_audio`) collide cross-skill with the YouTube
  skill's `download_audio` — both center on "audio/mp3"; the source (local file vs URL) is
  the true discriminator. This cross-skill collision is documented in the findings report.
