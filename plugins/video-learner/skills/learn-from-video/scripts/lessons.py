#!/usr/bin/env python3
"""Helpers for learn-from-video: find, scaffold and check topic lesson skills.

A lesson skill is a personal Claude Code skill at
~/.claude/skills/<topic>-video-lessons/ that remembers what a set of videos
taught. This script does the mechanical parts so they are the same every time;
the studying and writing is Claude's job.

Commands:
  lessons.py list                      Existing lesson skills, their video counts
                                       and descriptions (for routing a new video).
  lessons.py new <topic> --title T --about A --use-when U
                                       Scaffold <topic>-video-lessons from the
                                       templates. Refuses to overwrite.
  lessons.py video-id <url-or-path>    Stable id used for note/transcript names.
  lessons.py save-transcript <skill> <id> <file> [--title T] [--url U] [--via V]
                                       Copy a /watch transcript.txt into
                                       references/transcripts/<id>.txt with a header.
  lessons.py check <skill>             Consistency check: index vs notes vs
                                       transcripts, and "(n/N videos)" counts.

<skill> may be a folder name (cooking-video-lessons), a topic (cooking) or a
path. Set VIDEO_LESSONS_DIR to use a skills folder other than ~/.claude/skills.

Pure stdlib. Python 3.10+.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES = SCRIPT_DIR.parent / "templates"
SUFFIX = "-video-lessons"

YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def skills_root() -> Path:
    override = os.environ.get("VIDEO_LESSONS_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude" / "skills"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def resolve_skill(name: str) -> Path:
    candidate = Path(name).expanduser()
    if candidate.is_dir() and (candidate / "SKILL.md").exists():
        return candidate
    root = skills_root()
    slug = slugify(name)
    for folder in (slug, slug + SUFFIX, slug.removesuffix(SUFFIX) + SUFFIX):
        if (root / folder / "SKILL.md").exists():
            return root / folder
    raise SystemExit(f"no lesson skill named {name!r} under {root}")


def _frontmatter(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not text.startswith("---"):
        return out
    end = text.find("\n---", 3)
    for line in text[3:end if end != -1 else None].splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() and not key.startswith(" "):
            out[key.strip()] = value.strip()
    return out


def index_rows(skill: Path) -> list[list[str]]:
    """Data rows of the table in references/video-index.md (header skipped)."""
    path = skill / "references" / "video-index.md"
    if not path.exists():
        return []
    rows: list[list[str]] = []
    seen_header = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if not seen_header:
            seen_header = True
            continue
        rows.append(cells)
    return rows


# ---------------------------------------------------------------- commands


def cmd_list(_: argparse.Namespace) -> int:
    root = skills_root()
    skills = sorted(p for p in root.glob(f"*{SUFFIX}") if (p / "SKILL.md").exists()) if root.exists() else []
    if not skills:
        print(f"No lesson skills yet under {root}.")
        return 0
    for skill in skills:
        meta = _frontmatter((skill / "SKILL.md").read_text(encoding="utf-8"))
        n = len(index_rows(skill))
        print(f"## {skill.name}  ({n} video{'s' if n != 1 else ''})")
        print(f"path: {skill}")
        print(f"description: {meta.get('description', '(none)')}")
        print()
    return 0


def _render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    leftover = re.findall(r"\{\{[A-Z_]+\}\}", template)
    if leftover:
        raise SystemExit(f"template placeholders not filled: {sorted(set(leftover))}")
    return template


def cmd_new(args: argparse.Namespace) -> int:
    slug = slugify(args.topic).removesuffix(SUFFIX)
    if not slug:
        raise SystemExit("topic must contain letters or digits")
    name = slug + SUFFIX
    dest = skills_root() / name
    if dest.exists():
        raise SystemExit(f"{dest} already exists; update it instead of creating a new one")

    values = {
        "NAME": name,
        "TOPIC": re.sub(r"\s+", " ", args.topic).strip().lower(),
        "TITLE": args.title.strip(),
        "ABOUT": args.about.strip(),
        "USE_WHEN": args.use_when.strip(),
        "DATE": _dt.date.today().isoformat(),
    }
    files = {
        "SKILL.md.tmpl": "SKILL.md",
        "references/principles.md.tmpl": "references/principles.md",
        "references/video-index.md.tmpl": "references/video-index.md",
    }
    for src, rel in files.items():
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_render((TEMPLATES / src).read_text(encoding="utf-8"), values), encoding="utf-8")
    (dest / "references" / "videos").mkdir(parents=True, exist_ok=True)
    (dest / "references" / "transcripts").mkdir(parents=True, exist_ok=True)
    print(f"created {dest}")
    print(f"note template: {TEMPLATES / 'references' / 'videos' / 'video-note.md.tmpl'}")
    return 0


def video_id(source: str) -> str:
    match = YOUTUBE_RE.search(source)
    if match:
        return match.group(1)
    if re.match(r"^https?://", source, re.I):
        ytdlp = shutil.which("yt-dlp")
        if ytdlp:
            try:
                proc = subprocess.run(
                    [ytdlp, "--skip-download", "--no-warnings", "--print", "%(extractor_key)s-%(id)s", source],
                    capture_output=True, text=True, timeout=60,
                )
                line = (proc.stdout.strip().splitlines() or [""])[-1]
                if proc.returncode == 0 and line:
                    return slugify(line)[:60]
            except (OSError, subprocess.TimeoutExpired):
                pass
        return "url-" + hashlib.sha1(source.encode("utf-8")).hexdigest()[:10]
    return slugify(Path(source).stem)[:60] or "video-" + hashlib.sha1(source.encode()).hexdigest()[:10]


def cmd_video_id(args: argparse.Namespace) -> int:
    print(video_id(args.source))
    return 0


def cmd_save_transcript(args: argparse.Namespace) -> int:
    skill = resolve_skill(args.skill)
    src = Path(args.file).expanduser()
    body = src.read_text(encoding="utf-8").strip() if src.exists() else ""
    header = []
    if args.title:
        header.append(f"# {args.title}")
    if args.url:
        header.append(f"# Source: {args.url}")
    header.append(f"# Transcript via: {args.via or 'unknown'}")
    out = skill / "references" / "transcripts" / f"{args.id}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(header) + "\n\n" + (body or "(no speech)") + "\n", encoding="utf-8")
    print(f"saved {out}")
    return 0


COUNT_RE = re.compile(r"\((\d+)\s*/\s*(\d+)\s+videos?\)")


def cmd_check(args: argparse.Namespace) -> int:
    skill = resolve_skill(args.skill)
    problems: list[str] = []
    notes: list[str] = []

    skill_md = (skill / "SKILL.md").read_text(encoding="utf-8")
    meta = _frontmatter(skill_md)
    if meta.get("name") != skill.name:
        problems.append(f"SKILL.md name is {meta.get('name')!r}, folder is {skill.name!r}")
    if len(meta.get("description", "")) < 80:
        problems.append("SKILL.md description is missing or too short to trigger reliably")

    rows = index_rows(skill)
    total = len(rows)
    indexed = {r[0].strip("` ") for r in rows if r}
    note_ids = {p.stem for p in (skill / "references" / "videos").glob("*.md")}
    transcript_ids = {p.stem for p in (skill / "references" / "transcripts").glob("*.txt")}

    for vid in sorted(note_ids - indexed):
        problems.append(f"videos/{vid}.md has no row in video-index.md")
    for vid in sorted(indexed - note_ids):
        problems.append(f"video-index.md lists {vid} but videos/{vid}.md is missing")
    for vid in sorted(transcript_ids - indexed):
        problems.append(f"transcripts/{vid}.txt has no row in video-index.md")
    for vid in sorted(indexed - transcript_ids):
        notes.append(f"no transcripts/{vid}.txt (fine if it had no speech; save '(no speech)' to make that explicit)")

    for num, den in COUNT_RE.findall(skill_md):
        n, d = int(num), int(den)
        if d != total:
            problems.append(f"count ({n}/{d} videos) in SKILL.md, but video-index.md has {total} videos")
        if n > d:
            problems.append(f"count ({n}/{d} videos) has more sources than videos")
    if total and not COUNT_RE.search(skill_md):
        notes.append("SKILL.md one-page list has no '(n/N videos)' counts yet")

    principles = skill / "references" / "principles.md"
    if not principles.exists():
        problems.append("references/principles.md is missing")

    print(f"{skill.name}: {total} video(s), {len(note_ids)} note(s), {len(transcript_ids)} transcript(s)")
    for line in notes:
        print(f"  note: {line}")
    for line in problems:
        print(f"  PROBLEM: {line}")
    if not problems:
        print("  ok")
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="lessons", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=cmd_list)

    p = sub.add_parser("new")
    p.add_argument("topic", help="short topic, e.g. 'cooking' or 'video editing'")
    p.add_argument("--title", required=True, help="human title, e.g. 'Home cooking'")
    p.add_argument("--about", required=True, help="what kinds of videos feed it")
    p.add_argument("--use-when", required=True, help="tasks that should load it")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("video-id")
    p.add_argument("source")
    p.set_defaults(func=cmd_video_id)

    p = sub.add_parser("save-transcript")
    p.add_argument("skill")
    p.add_argument("id")
    p.add_argument("file", help="transcript.txt from the /watch work dir")
    p.add_argument("--title")
    p.add_argument("--url")
    p.add_argument("--via", help="captions | whisper (local faster-whisper, small) | ...")
    p.set_defaults(func=cmd_save_transcript)

    p = sub.add_parser("check")
    p.add_argument("skill")
    p.set_defaults(func=cmd_check)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
