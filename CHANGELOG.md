# Changelog

All notable changes to video-learner. Versions follow semver.

## 0.1.0 — 2026-09-25

First release.

### Added

- **watch skill**, forked from the `watch` skill of
  [claude-video](https://github.com/bradautomates/claude-video) 0.2.0 by
  Bradley Bonanno (MIT).
- **Local, offline Whisper backend** using faster-whisper (CPU, int8,
  model `small` by default). Used automatically when a video has no captions
  and no Groq/OpenAI key is set; force it with `--whisper local`.
- `--whisper-model` and `WATCH_WHISPER_MODEL` to choose the local model.
- `--word-timestamps`: per-word timings from local Whisper in `words.json`.
- **No-speech detection**: silent segments are dropped, and an empty result
  or low language confidence is reported as "music only / no speech" rather
  than a made-up transcript.
- The transcript is saved as `transcript.txt` in the work dir.
- Audio-only inputs (`.wav`, `.mp3`, ...) are transcribed without trying to
  extract frames.
- `setup.py --install-local-whisper`, and setup treats an installed
  faster-whisper as a transcriber, so no API key is ever required.
- **learn-from-video skill**: studies videos and creates or updates topic
  lessons skills under `~/.claude/skills/<topic>-video-lessons/`, with
  templates and a `lessons.py` helper (`list`, `new`, `video-id`,
  `save-transcript`, `check`).
- Tests for the local backend and the lessons helper.

### Changed (from upstream claude-video 0.2.0)

- Backend order is Groq key -> OpenAI key -> local faster-whisper.
- No false "file is readable by other users" warning on Windows (setup
  check and SessionStart hook).
- Upstream frame-count tests now also pass on Windows paths.
