"""learn-from-video's lessons.py: scaffold, list, transcript saving and checks."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

LESSONS = (
    Path(__file__).resolve().parent.parent
    / "plugins" / "video-learner" / "skills" / "learn-from-video" / "scripts" / "lessons.py"
)


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, VIDEO_LESSONS_DIR=str(root))
    return subprocess.run(
        [sys.executable, str(LESSONS), *args], capture_output=True, text=True, env=env
    )


def _new(root: Path) -> Path:
    proc = _run(
        root, "new", "Home Cooking", "--title", "Home cooking",
        "--about", "recipes and knife skills", "--use-when", "cooking or planning meals",
    )
    assert proc.returncode == 0, proc.stderr
    return root / "home-cooking-video-lessons"


def test_new_scaffolds_full_layout(tmp_path):
    skill = _new(tmp_path)
    for rel in ("SKILL.md", "references/principles.md", "references/video-index.md"):
        text = (skill / rel).read_text(encoding="utf-8")
        assert "{{" not in text, rel
    assert (skill / "references" / "videos").is_dir()
    assert (skill / "references" / "transcripts").is_dir()
    head = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert "name: home-cooking-video-lessons" in head
    assert "home cooking videos" in head
    assert "Use this whenever cooking or planning meals" in head


def test_new_refuses_to_overwrite(tmp_path):
    _new(tmp_path)
    proc = _run(tmp_path, "new", "home cooking", "--title", "x", "--about", "y", "--use-when", "z")
    assert proc.returncode != 0
    assert "already exists" in proc.stderr


def test_fresh_skill_passes_check_and_lists(tmp_path):
    _new(tmp_path)
    assert _run(tmp_path, "check", "home-cooking").returncode == 0
    listing = _run(tmp_path, "list").stdout
    assert "home-cooking-video-lessons  (0 videos)" in listing


def _add_video(skill: Path, vid: str) -> None:
    index = skill / "references" / "video-index.md"
    index.write_text(
        index.read_text(encoding="utf-8")
        + f"| {vid} | Chef, Title (3:00) | 2026-01-01 | captions | knives |\n",
        encoding="utf-8",
    )
    (skill / "references" / "videos" / f"{vid}.md").write_text("# note\n", encoding="utf-8")


def test_check_catches_stale_counts_and_orphans(tmp_path):
    skill = _new(tmp_path)
    _add_video(skill, "abc123def45")
    _add_video(skill, "zzz999yyy88")
    (skill / "references" / "videos" / "orphan.md").write_text("# x\n", encoding="utf-8")
    skill_md = skill / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8").replace(
            "_No videos studied yet._", "1. **Sharp knives** (1/1 videos)."
        ),
        encoding="utf-8",
    )
    proc = _run(tmp_path, "check", str(skill))
    assert proc.returncode == 1
    assert "video-index.md has 2 videos" in proc.stdout
    assert "videos/orphan.md has no row" in proc.stdout


def test_check_passes_when_consistent(tmp_path):
    skill = _new(tmp_path)
    _add_video(skill, "abc123def45")
    src = tmp_path / "transcript.txt"
    src.write_text("[00:00] hello\n", encoding="utf-8")
    saved = _run(tmp_path, "save-transcript", "home-cooking", "abc123def45", str(src),
                 "--title", "T", "--url", "https://youtu.be/abc123def45", "--via", "captions")
    assert saved.returncode == 0, saved.stderr
    text = (skill / "references" / "transcripts" / "abc123def45.txt").read_text(encoding="utf-8")
    assert text.startswith("# T\n# Source: https://youtu.be/abc123def45\n# Transcript via: captions")
    skill_md = skill / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8").replace(
            "_No videos studied yet._", "1. **Sharp knives** (1/1 videos)."
        ),
        encoding="utf-8",
    )
    proc = _run(tmp_path, "check", "home-cooking-video-lessons")
    assert proc.returncode == 0, proc.stdout


def test_video_id_youtube_and_local(tmp_path):
    assert _run(tmp_path, "video-id", "https://www.youtube.com/shorts/jNQXAC9IVRw").stdout.strip() == "jNQXAC9IVRw"
    assert _run(tmp_path, "video-id", "https://youtu.be/dQw4w9WgXcQ?t=3").stdout.strip() == "dQw4w9WgXcQ"
    assert _run(tmp_path, "video-id", "https://www.youtube.com/watch?list=x&v=dQw4w9WgXcQ").stdout.strip() == "dQw4w9WgXcQ"
    assert _run(tmp_path, "video-id", "clips/My Great Video.mp4").stdout.strip() == "my-great-video"
