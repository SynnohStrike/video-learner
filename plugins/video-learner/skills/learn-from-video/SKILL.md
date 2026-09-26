---
name: learn-from-video
version: "0.1.0"
description: Study videos the user sends to learn from (YouTube, TikTok, Instagram, Vimeo, local files) and turn what they teach into a permanent topic "lessons" skill at ~/.claude/skills/<topic>-video-lessons/, so every future Claude Code session knows it. Uses /watch for transcripts and frames. Use whenever the user says "learn from this video", "study these", "remember what this says", "add this to what you know about X", sends one or more video links to learn a skill or technique from (rather than to ask one question about), or asks to update, review or clean up a video-lessons skill.
argument-hint: "<video-url-or-path> [more urls] [topic or focus]"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, AskUserQuestion
license: MIT
user-invocable: true
---

# Learn from videos → lesson skills

The user sends videos to learn from. You study them (transcript for what is
said, frames for what is shown) and write what they teach into a **topic
lessons skill** in the user's personal skills folder:

```
~/.claude/skills/<topic>-video-lessons/
  SKILL.md                      trigger description + the lessons in one page
  references/principles.md      every lesson: sources, exact numbers, NEW/AGREES/CONFLICTS
  references/video-index.md     one row per video
  references/videos/<id>.md     notes per video
  references/transcripts/<id>.txt
```

Because it is a normal skill with a strong "use whenever..." description,
every later session loads it automatically when the topic comes up. The
lessons skill is the product; a chat summary alone is not enough.

## Paths

Set these once per run from the path of this SKILL.md (your harness showed
it when you read this file):

- `LEARN_DIR` = the directory containing this SKILL.md
- `WATCH_DIR` = `LEARN_DIR/../watch` (the /watch skill in the same plugin)
- `LESSONS` = `python3 "$LEARN_DIR/scripts/lessons.py"` (on Windows use
  `python` instead of `python3`, everywhere)

Templates for every generated file are in `LEARN_DIR/templates/`.

## Step 1 — Preflight

Run `python3 "$WATCH_DIR/scripts/setup.py" --check`. Exit 0 → carry on
silently. Otherwise follow Step 0 of `WATCH_DIR/SKILL.md` (it offers free
local Whisper, so videos without captions still get a transcript).

## Step 2 — Get every video's transcript and basics (cheap pass)

For each video, run /watch in transcript mode first. It is fast, costs no
image tokens, and gives title, creator, length and the transcript:

```bash
python3 "$WATCH_DIR/scripts/watch.py" "<url>" --detail transcript --out-dir "<scratch>/<id>"
$LESSONS video-id "<url>"          # the id used for file names
```

Use a scratch or temp folder for `--out-dir`, never the lessons skill. The
transcript is saved as `<out-dir>/transcript.txt`. If the report says "no
speech detected (music only / no speech)", the video is purely visual: the
frames carry everything.

## Step 3 — Route each video to a topic

```bash
$LESSONS list
```

This prints every existing `*-video-lessons` skill with its description and
video count. For each video decide which topic skill(s) it belongs to:

- **Reuse** an existing topic whenever it fits, even loosely. A cooking
  video about knife skills goes into `cooking-video-lessons`, not a new
  `knife-skills-video-lessons`.
- **Several topics** are fine: a video can feed more than one skill. Each
  skill must stand alone, so each gets its own note (only the lessons that
  matter to that topic) and its own copy of the transcript.
- **Create a new topic** only when nothing fits. Pick a short, broad topic
  name that future videos will also fit ("video editing", not "caption
  animation in one app"). Then scaffold it:

```bash
$LESSONS new "home cooking" --title "Home cooking" \
  --about "recipes, knife skills, heat control, meal prep" \
  --use-when "cooking, planning meals, following or adapting a recipe, or choosing kitchen gear"
```

Then open the new `SKILL.md` and sharpen the `description` so it triggers
reliably: name the concrete tasks, keywords and questions that should load
it, and end with "even if the videos are not mentioned". A vague
description means the lessons are never used.

If routing is genuinely ambiguous (a new topic vs. stretching an old one),
ask the user with one short question; otherwise decide yourself.

## Step 4 — Study

For each video, read the transcript, then look at frames where the visuals
matter (style, layout, colours, on-screen text, pacing, demonstrations):

```bash
python3 "$WATCH_DIR/scripts/watch.py" "<url or downloaded file>" --out-dir "<scratch>/<id>"
```

Read every frame path it lists. For a video over ~10 minutes, don't scan
the whole thing sparsely: use `--start/--end` on the sections the transcript
says matter, and `--timestamps` for moments the speaker points at ("look at
this", "see how"). A talking head with nothing on screen needs no frames.

**Several long videos → subagents in parallel.** With more than one video
over ~10 minutes, or more than ~4 videos in total, give each subagent one
long video (or a few short ones). Brief each with: the video URL and its
`transcript.txt` path, the `WATCH_DIR` path, the target skill's
`references/principles.md` path, the note template
(`LEARN_DIR/templates/references/videos/video-note.md.tmpl`), and the rules
below. Ask it to return the finished note text and a list of lessons marked
NEW / AGREES / CONFLICTS with lesson numbers. **Only you** edit `SKILL.md`,
`principles.md` and `video-index.md`, so parallel agents never overwrite
each other.

### What to capture

- Each lesson in plain words, with the **exact numbers** the creator gave
  (durations, counts, percentages, settings, sizes, temperatures, dB...) and
  the **timestamp** `[m:ss]`.
- Things shown but not said, from frames, marked "on screen".
- Why, if the creator said why.
- Whether it is **NEW**, **AGREES** or **CONFLICTS** with the rulebook.
  Conflicts keep both sides with sources; never silently pick one.

### Rules

- **Never invent numbers.** If a video gives no number, say so. Anything you
  work out yourself is marked **(inference)**.
- **Skip** sponsor reads, app click-paths ("click Effects, then Transform,
  then..."), channel plugs and motivation. Keep the idea behind a click-path
  ("keyframe a slow zoom"), drop the menu route. List what was skipped in
  the note's "Skipped" section.
- Say **how** each video was studied (captions / local Whisper / API
  Whisper, frames or not) and what could not be checked.
- Auto-captions and Whisper mis-hear names and jargon; fix obvious errors in
  the note and don't build a lesson on one garbled word.
- Store only what the videos teach, not private details about the user.

## Step 5 — Write it into the lessons skill

For each target skill:

1. Save the transcript:
   `$LESSONS save-transcript <skill> <id> "<scratch>/<id>/transcript.txt" --title "<title>" --url "<url>" --via "<transcript source from the report>"`
   (a video with no speech still gets a transcript file saying `(no speech)`).
2. Write `references/videos/<id>.md` from the note template.
3. Add a row to `references/video-index.md`.
4. Update `references/principles.md`: new lessons get a new numbered
   section; existing ones get the new source, numbers and a History entry
   (NEW / AGREES / CONFLICTS). Add disagreements to "Where the videos
   disagree".
5. Update the one-page list in `SKILL.md`: at most ~12 numbered lessons,
   most important first, each one or two lines with its key numbers and a
   count `(n/N videos)`, where N is the total number of videos in the index.
   **Every count's N changes when a video is added**, so update them all.
   Keep the page to one screen; detail lives in `principles.md`.
6. If the new video changes how a lesson reads, rewrite the lesson; don't
   append contradictions.
7. Check it:
   `$LESSONS check <skill>` — fix every PROBLEM it prints.

Then delete the scratch folders (or keep them if the user may ask
follow-ups about the footage).

## Step 6 — Tell the user

A few plain lines, not a report:

- which skill(s) it went into (and that a new one was created, if so);
- what was **new**, with the one or two most useful numbers;
- what it **changes**: a lesson that got stronger, one that now has a
  conflict, or advice you'd now give differently;
- anything that could not be read (no captions and no speech, login wall,
  on-screen text too small).

Example: "Added to cooking-video-lessons (now 6 videos). New: rest steak 5
min per 2 cm of thickness (Chef A 3:10). It conflicts with the 10-minute
rest from video 2, so both are noted. The knife-grip lesson is now backed by
4 of 6 videos."

## Later sessions

Nothing to do: the lessons skill loads on its own when its topic comes up
or when the user asks what the videos said. If the user asks you to
review or tidy a lessons skill, re-read `principles.md`, merge duplicate
lessons, re-rank the one-page list and run `$LESSONS check`.
