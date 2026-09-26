# Notice and credits

## claude-video by Bradley Bonanno

The `watch` skill in this plugin is a fork of the `watch` skill from
**[claude-video](https://github.com/bradautomates/claude-video)** by
**Bradley Bonanno** ([@bradautomates](https://github.com/bradautomates)),
version 0.2.0, released under the MIT License:

> MIT License
>
> Copyright (c) 2026 Bradley Bonanno

His work is the whole video pipeline this plugin stands on: the yt-dlp
download and caption fetching, scene-aware and keyframe frame extraction with
ffmpeg, near-duplicate frame removal, transcript-cue frames, focus ranges,
the Groq / OpenAI Whisper clients with chunking and retries, the setup
preflight and installer, the SessionStart hook, and the test suite. If you
find `/watch` useful, star and support
[the original project](https://github.com/bradautomates/claude-video).

### What this fork changed

- `scripts/whisper.py`: added a local, offline Whisper backend using
  faster-whisper (CPU, int8, model `small` by default, optional word
  timestamps), backend auto-selection (Groq -> OpenAI -> local), and
  "music only / no speech" detection.
- `scripts/watch.py`: `--whisper local`, `--whisper-model`,
  `--word-timestamps`; audio-only inputs skip frame extraction; transcript
  saved to the work dir; no-speech reporting.
- `scripts/setup.py`: a local faster-whisper install counts as a transcriber
  (no API key needed); `--install-local-whisper`; interactive install offer;
  no false file-permission warning on Windows.
- `scripts/config.py`: `WATCH_WHISPER_MODEL`.
- `hooks/scripts/check-setup.sh`: knows about local Whisper; no permission
  warning on Windows.
- `SKILL.md`: documents the above.
- Tests: paths moved to the plugin layout, a Windows path fix, and new tests
  for the local backend.

`download.py`, `frames.py` and `transcribe.py` are unchanged apart from a
one-line origin comment.

## New in video-learner

The `learn-from-video` skill, its templates and `lessons.py`, and the local
Whisper work above are Copyright (c) 2026 SynnohStrike, MIT License.

## Third-party tools used at runtime (not bundled)

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense)
- [FFmpeg](https://ffmpeg.org) (LGPL/GPL)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT) and the
  OpenAI Whisper model weights (MIT)
