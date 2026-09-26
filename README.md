# video-learner

**Let Claude watch videos, and remember what it learned from them.**

A Claude Code plugin with two skills:

- **`watch`** — paste a video link or file and ask about it. Claude downloads
  it, looks at the frames, reads the transcript and answers. Transcription
  works **with no API key**: captions first, then Groq or OpenAI Whisper if you
  have a key, and otherwise **free, offline Whisper on your own machine**.
- **`learn-from-video`** — send videos to learn from ("learn from these
  cooking videos"). Claude studies them and writes what they teach into a
  **lessons skill** in your personal skills folder, so every later Claude
  Code session already knows it.

> The `watch` skill is a fork of
> **[claude-video](https://github.com/bradautomates/claude-video) by Bradley
> Bonanno**, used under the MIT License. All of the video pipeline (download,
> scene-aware frames, captions, API Whisper) is his work; this fork adds the
> offline Whisper backend, no-speech detection and the learning skill. See
> [Credits](#credits).

```
/plugin marketplace add SynnohStrike/video-learner
/plugin install video-learner@video-learner
```

---

## What it looks like

```
You:    learn from these videos about knife skills:
        https://youtu.be/AAAAAAAAAAA https://youtu.be/BBBBBBBBBBB

Claude: (runs /watch on both, reads the transcripts, looks at the frames
        where the chef demonstrates each grip)

        Added both to a new skill, cooking-video-lessons (2 videos).
        New: the "claw" grip with knuckles guiding the blade (both videos),
        and hone before every session, 5-6 strokes per side (video 1, 2:40).
        They disagree on rocking vs. push cuts for onions; both are noted.
        Couldn't read the brand on the whetstone; it wasn't said aloud.
```

A week later, in a new chat:

```
You:    how should I hold the knife to dice this onion?

Claude: (the cooking-video-lessons skill loads by itself)
        Use the claw grip from your videos: ...
```

And for a one-off question, no learning:

```
/video-learner:watch https://youtu.be/CCCCCCCCCCC what settings does she use for the export?
```

## How it works

### Watching a video

```
URL or file
  │
  ├─ yt-dlp ──────────── metadata + native captions (free; no video download needed
  │                      for transcript-only questions)
  ├─ yt-dlp ──────────── video download (only when frames are needed)
  ├─ ffmpeg ──────────── scene-aware frames (or fast keyframes), near-duplicates
  │                      dropped, frame count scaled to the video's length
  └─ transcript, first one that works:
       1. native captions (manual or auto-generated)
       2. Groq Whisper (whisper-large-v3)       if GROQ_API_KEY is set
       3. OpenAI Whisper (whisper-1)            if OPENAI_API_KEY is set
       4. local faster-whisper (CPU, int8)      if installed: free, offline
```

The script prints a report with every frame's path and timestamp plus the
timestamped transcript. Claude then opens each frame as an image, so it has
both *seen* and *heard* the video before answering.

If the audio has no speech (music, silence, ambience), the local backend
says **"no speech detected (music only / no speech)"** instead of inventing
lyrics, and Claude works from the frames.

### Learning from videos

1. **Transcript pass** — `/watch --detail transcript` on each video: fast and
   cheap, gives title, creator, length and the words.
2. **Route** — each video goes to the right topic skill
   (`~/.claude/skills/<topic>-video-lessons/`). An existing topic is reused
   whenever it fits; a new one is created only when nothing does. One video
   can feed several topics.
3. **Study** — the transcript for content, frames for visual style (layouts,
   colours, on-screen text, pacing, demonstrations). Several long videos are
   studied in parallel by subagents.
4. **Write** — a note per video, the saved transcript, an index row, and the
   rulebook (`principles.md`) with each lesson's sources, the creators' exact
   numbers with timestamps, and whether the video is **NEW**, **AGREES** or
   **CONFLICTS**. The skill's one-page list is re-ranked with counts like
   "(3/10 videos)".
5. **Report** — a few plain lines: what was new and what it changes.

A generated lessons skill looks like this:

```
~/.claude/skills/cooking-video-lessons/
  SKILL.md                         "Use this whenever cooking, planning meals, ..."
                                   + the lessons on one page, with counts
  references/principles.md         every lesson, sources, numbers, NEW/AGREES/CONFLICTS
  references/video-index.md        one row per video
  references/videos/<id>.md        notes per video (incl. "What's on screen")
  references/transcripts/<id>.txt  the transcripts, with [mm:ss] marks
```

Rules the learning skill follows: never invent numbers (guesses are marked
**(inference)**); skip sponsor reads, app click-paths and motivation; say how
each video was studied and what couldn't be checked; keep both sides of a
disagreement.

## Requirements

- **Claude Code**
- **Python 3.10+**
- **ffmpeg** (with ffprobe)
- **yt-dlp** (keep it up to date; sites change often)
- **faster-whisper** (optional but recommended: the free offline transcriber)

### macOS

```bash
brew install python ffmpeg yt-dlp
python3 -m pip install --user faster-whisper
```

If pip refuses with "externally-managed-environment", use a virtual
environment, or add `--break-system-packages`.

### Linux (Debian / Ubuntu)

```bash
sudo apt install python3 python3-pip ffmpeg
python3 -m pip install --user yt-dlp faster-whisper
```

Fedora: `sudo dnf install python3 python3-pip ffmpeg` (ffmpeg comes from
RPM Fusion). The same "externally managed" note applies.

### Windows

```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
winget install yt-dlp.yt-dlp
python -m pip install faster-whisper
```

Open a new terminal after installing so the new programs are on your PATH.

You don't have to do this by hand: the first time you use `/watch`, Claude
runs the setup check. On macOS it installs ffmpeg and yt-dlp with Homebrew;
elsewhere it prints the exact commands. It offers to install faster-whisper
for you (`setup.py --install-local-whisper`).

## Install

In Claude Code:

```
/plugin marketplace add SynnohStrike/video-learner
/plugin install video-learner@video-learner
```

Restart Claude Code (or start a new session) so the skills load. To update
later: `/plugin marketplace update video-learner`.

> Already have the original `watch@claude-video` plugin? Both provide a
> `watch` skill. Keep one to avoid confusion:
> `/plugin uninstall watch@claude-video`.

The first local transcription downloads the Whisper model once (`small` is
about 460 MB) and caches it.

## Usage

### Ask about a video

```
/video-learner:watch https://youtu.be/<id> what hook do they open with?
/video-learner:watch ~/Downloads/demo.mp4 summarize this
/video-learner:watch https://youtu.be/<id> what happens between 2:15 and 2:45?
```

Plugin skills are namespaced, hence `video-learner:watch`. You can also just
paste a link and ask; Claude picks the skill by itself.

Useful flags Claude can pass for you (or you can ask for):

| Flag | What it does |
|---|---|
| `--detail transcript` | no frames, transcript only (cheapest) |
| `--start 2:15 --end 2:45` | focus on a section, with denser frames |
| `--timestamps 1:10,4:32` | grab frames at exact moments |
| `--whisper local` | force offline transcription even if you have a key |
| `--whisper-model medium` | bigger local model: more accurate, slower |
| `--word-timestamps` | per-word timings (local Whisper) in `words.json` |
| `--no-whisper` | never transcribe audio; captions or frames only |

### Learn from videos

Just say it:

```
learn from these video editing tutorials: <url> <url> <url>
study this and remember it: <url>
add this to what you know about sourdough: <url>
```

Claude uses the `learn-from-video` skill, then tells you what was new.

### Use what was learned, later

In any later session, just work on the topic, or ask:

```
what did the editing videos say about caption length?
which of the cooking videos disagreed about resting meat?
```

The lessons skill loads by itself when the topic comes up.

## Configuration

Settings live in `~/.config/watch/.env` (created on first run; the same file
the original claude-video plugin uses):

```bash
# Optional API keys. Leave blank to use captions + local Whisper only.
GROQ_API_KEY=
OPENAI_API_KEY=

# Default detail: transcript | efficient | balanced | token-burner
WATCH_DETAIL=balanced

# Local Whisper model: tiny | base | small | medium | large-v3 (or *.en)
WATCH_WHISPER_MODEL=small

SETUP_COMPLETE=true
```

Put each value on its own line with no trailing comment.

**Detail modes**

| Mode | Frames | Good for |
|---|---|---|
| `transcript` | none | talks, podcasts, anything where only the words matter |
| `efficient` | keyframes, up to 50 | a quick look |
| `balanced` (default) | scene-aware, up to 100 | most videos |
| `token-burner` | scene-aware, no cap | when every visual detail matters |

**Local Whisper models** (downloaded once, then cached): `tiny` (~75 MB,
fastest, roughest), `base`, `small` (~460 MB, the default), `medium`
(~1.5 GB), `large-v3` (most accurate, slowest). English-only `*.en`
variants such as `small.en` are a little better on English.

## Privacy

- **yt-dlp** talks only to the site the link points to, and only fetches
  public data (no logins, no cookies).
- **Local Whisper**: audio never leaves your computer. The only network use
  is the one-time model download from Hugging Face.
- **Groq / OpenAI**: only if you set a key, and only the extracted audio
  (mono, 16 kHz) is uploaded, never the video. The Groq key only goes to
  Groq, the OpenAI key only to OpenAI.
- **Files** — downloads, frames and audio go to a temp folder that Claude can
  delete when done. Lessons skills and their transcripts are plain files in
  `~/.claude/skills/` on your machine.
- Frames and transcripts that Claude reads become part of your Claude
  conversation, like any other file Claude opens.

## Limitations

- **Login-walled, private, members-only or region-locked videos** can't be
  downloaded. Claude will say so rather than retry.
- **Long videos**: frames are spread thin past ~10 minutes, so Claude
  focuses on sections (`--start/--end`). Local Whisper on CPU is slower than
  the APIs and scales with length; for hour-long videos a Groq key or a
  smaller model (`base`) helps.
- **Frame cost**: frames are images, and images use tokens. 80 frames at
  512 px is roughly 50-80k tokens. `--detail transcript` costs almost
  nothing.
- **Transcripts mis-hear** names and jargon, from auto-captions and Whisper
  alike. Lessons are built from meaning, not single words.
- **YouTube changes often**: update yt-dlp when downloads fail. Recent
  yt-dlp versions want a JavaScript runtime (Deno) for full YouTube support
  and print a warning without one; captions usually still work.

## Development

```bash
python -m pip install pytest
python -m pytest tests
```

The tests build tiny clips with ffmpeg and fake faster-whisper, so they run
offline in a few seconds.

Layout:

```
.claude-plugin/marketplace.json        the marketplace (one plugin)
plugins/video-learner/
  .claude-plugin/plugin.json
  hooks/                               SessionStart setup hint
  skills/watch/                        forked /watch skill + scripts
  skills/learn-from-video/             learning skill, templates, lessons.py
tests/
```

## Credits

- **Bradley Bonanno** — author of
  [claude-video](https://github.com/bradautomates/claude-video), the MIT
  project the `watch` skill is forked from. The download, frame, caption and
  API Whisper pipeline, the setup flow and most of the tests are his.
  Details of what changed are in [NOTICE.md](NOTICE.md).
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) by SYSTRAN,
  [yt-dlp](https://github.com/yt-dlp/yt-dlp), and [FFmpeg](https://ffmpeg.org).

## License

MIT. Copyright (c) 2026 Bradley Bonanno (original claude-video code) and
Copyright (c) 2026 SynnohStrike (this fork and new work). See
[LICENSE](LICENSE).
