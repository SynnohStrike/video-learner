"""setup.py --json surfaces the resolved watch detail and transcriber."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

# The keyless expectations depend on whether this interpreter can import
# faster-whisper: if it can, local Whisper is a transcriber and no key is needed.
LOCAL = importlib.util.find_spec("faster_whisper") is not None

SETUP = Path(__file__).resolve().parent.parent / "plugins" / "video-learner" / "skills" / "watch" / "scripts" / "setup.py"


def _run(args, *, home=None, extra_env=None):
    env = dict(os.environ)
    env.pop("WATCH_DETAIL", None)
    # Don't let a real key in the developer's shell env leak into the test.
    env.pop("GROQ_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    env.pop("SETUP_COMPLETE", None)
    env.pop("WATCH_WHISPER_MODEL", None)
    if home is not None:
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)  # Windows
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SETUP), *args],
        capture_output=True, text=True, env=env,
    )


def _write_env(home: Path, body: str) -> None:
    cfg = home / ".config" / "watch"
    cfg.mkdir(parents=True, exist_ok=True)
    f = cfg / ".env"
    f.write_text(body, encoding="utf-8")
    f.chmod(0o600)


def test_json_reports_watch_detail():
    proc = _run(["--json"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["watch_detail"] == "balanced"


def test_keyless_completed_setup_proceeds_silently(tmp_path):
    """A user who finished setup without a key must NOT be nagged forever."""
    _write_env(tmp_path, "GROQ_API_KEY=\nOPENAI_API_KEY=\nSETUP_COMPLETE=true\n")
    chk = _run(["--check"], home=tmp_path)
    assert chk.returncode == 0, f"keyless-complete should pass --check; got {chk.returncode}: {chk.stderr}"
    assert chk.stdout == "" and chk.stderr == ""

    js = json.loads(_run(["--json"], home=tmp_path).stdout)
    assert js["can_proceed"] is True
    assert js["first_run"] is False
    assert js["setup_complete"] is True
    # without local Whisper, status still encourages a transcriber
    assert js["status"] == ("ready" if LOCAL else "needs_key")
    assert js["local_whisper"] is LOCAL


def test_keyless_first_run(tmp_path):
    """First run with no key: ready if faster-whisper is installed, else exit 3."""
    _write_env(tmp_path, "GROQ_API_KEY=\nOPENAI_API_KEY=\n")
    chk = _run(["--check"], home=tmp_path)
    js = json.loads(_run(["--json"], home=tmp_path).stdout)
    assert js["first_run"] is True
    if LOCAL:
        assert chk.returncode == 0, chk.stderr
        assert js["can_proceed"] is True
        assert js["status"] == "ready"
        assert js["whisper_backend"] == "local"
    else:
        assert chk.returncode == 3, chk.stderr
        assert "--install-local-whisper" in chk.stderr
        assert js["can_proceed"] is False
        assert js["whisper_backend"] is None


def test_key_beats_local(tmp_path):
    """An API key is preferred over local Whisper when both exist."""
    _write_env(tmp_path, "OPENAI_API_KEY=sk-test-abc\n")
    js = json.loads(_run(["--json"], home=tmp_path).stdout)
    assert js["whisper_backend"] == "openai"


def test_json_reports_whisper_model(tmp_path):
    _write_env(tmp_path, "WATCH_WHISPER_MODEL=base.en\n")
    js = json.loads(_run(["--json"], home=tmp_path).stdout)
    assert js["whisper_model"] == "base.en"


def test_key_present_is_ready(tmp_path):
    _write_env(tmp_path, "GROQ_API_KEY=sk-test-abc\n")
    chk = _run(["--check"], home=tmp_path)
    assert chk.returncode == 0, chk.stderr

    js = json.loads(_run(["--json"], home=tmp_path).stdout)
    assert js["status"] == "ready"
    assert js["can_proceed"] is True
    assert js["whisper_backend"] == "groq"
