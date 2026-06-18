---
name: youtube
description: Download from YouTube with yt-dlp — full video, audio-only MP3, subtitles/transcript, metadata JSON, whole playlists, and thumbnails. Real yt-dlp binary (network). Binding-only in the thesis benchmark.
---

# YouTube Skill

Use this skill to fetch content from YouTube via the **real `yt-dlp` binary**. Because it
touches the network, it is evaluated **binding-only** (command correctness, no execution)
in the thesis benchmark to keep runs offline and side-effect-free. It pairs with the ffmpeg
skill for a real two-step composite (`composite_youtube_to_mp3`: yt-dlp → ffmpeg).

> The commands below are the gold grammar; the discriminating flags distinguish the
> sibling actions (all start with `yt-dlp <url>`).

## Commands (via bash) — invoke `yt-dlp` directly

### Download the full video (bare)
`yt-dlp "<url>"`

### Download audio as MP3 (discriminator: `-x --audio-format mp3`)
`yt-dlp -x --audio-format mp3 "<url>"`

### Fetch subtitles / transcript (discriminator: `--write-auto-sub --skip-download`)
`yt-dlp --write-auto-sub --skip-download "<url>"`

### Dump metadata JSON (discriminator: `--dump-json --skip-download`)
`yt-dlp --dump-json --skip-download "<url>"`

### Download a whole playlist (discriminator: `--yes-playlist`)
`yt-dlp --yes-playlist "<playlist-url>"`

### Download the thumbnail (discriminator: `--write-thumbnail --skip-download`)
`yt-dlp --write-thumbnail --skip-download "<url>"`

## Notes
- `download_video` (bare) vs `download_audio` (`-x`) is a sibling pair distinguished only by
  the `-x` flag — binding cannot assert the *absence* of `-x`, so routing carries the
  discrimination for the bare-video case.
- `download_audio` collides cross-skill with the ffmpeg skill's `extract_audio` ("rip the
  mp3"); the source (URL vs local file) is the discriminator. See the findings report.
- Composite `composite_youtube_to_mp3` chains `download_audio` → `ffmpeg` transcode.
