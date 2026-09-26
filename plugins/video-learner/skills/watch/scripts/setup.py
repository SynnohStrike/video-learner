#!/usr/bin/env python3
# From claude-video by Bradley Bonanno (MIT); modified in video-learner to add local faster-whisper. See LICENSE / NOTICE.md.
"""Setup / preflight for /watch.

Modes:
  setup.py --check                  Silent preflight. Exit 0 if ready, 2/3/4 on failure.
  setup.py --json                   Machine-readable status for Claude to parse.
  setup.py --install-local-whisper  pip install faster-whisper (free, offline transcription).
  setup.py                          Installer. Auto-installs deps, scaffolds .env, marks
                                    SETUP_COMPLETE. On an interactive terminal with no API
                                    key and no faster-whisper, offers to install it.

Design:
- Silent on success: --check exits 0 with no output when everything's ready so
  that /watch doesn't spam "setup is complete" on every turn.
- Idempotent: re-running the installer is safe — it never clobbers existing
  keys and only appends missing ones.
- SETUP_COMPLETE=true in ~/.config/watch/.env tells us the user has been
  through a successful installer run at least once.
- Never sudo. On macOS, auto-install via brew. Elsewhere, print exact commands.
- Never write an API key to disk automatically — only scaffold placeholders.
- A transcriber is either an API key (Groq / OpenAI) or a local faster-whisper
  install. Either one makes /watch fully ready; no API key is ever required.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from config import get_config  # noqa: E402
from whisper import local_whisper_available  # noqa: E402


REQUIRED_BINARIES = ["ffmpeg", "ffprobe", "yt-dlp"]
CONFIG_DIR = Path.home() / ".config" / "watch"
CONFIG_FILE = CONFIG_DIR / ".env"
ENV_TEMPLATE = """# /watch configuration
#
# Whisper transcription fallback — used only when yt-dlp cannot get captions
# (or when you point /watch at a local file with no subtitles).
#
# Order: Groq key -> OpenAI key -> local faster-whisper.
#
# Local (free, offline, no key): `pip install faster-whisper`. Runs on CPU;
# nothing leaves your machine. The first run downloads the model once.
# Model size (tiny | base | small | medium | large-v3, or *.en variants):
# WATCH_WHISPER_MODEL=small
#
# API keys are optional. Groq runs whisper-large-v3 fast and cheap; OpenAI is
# the compatible fallback. With a key set, only the extracted audio is sent.
# Get a Groq key:  https://console.groq.com/keys
# Get an OpenAI key:  https://platform.openai.com/api-keys
#
# With no key and no faster-whisper, videos without native captions come
# back frames-only.

GROQ_API_KEY=
OPENAI_API_KEY=

# Default watch behavior (the /watch first-run wizard sets this for you).
# Allowed values: transcript | efficient | balanced | token-burner
# Keep the value on its own line with no trailing comment.
# WATCH_DETAIL=balanced
"""


def _which(name: str) -> str | None:
    return shutil.which(name)


def _check_binaries() -> list[str]:
    return [b for b in REQUIRED_BINARIES if not _which(b)]


_PERM_WARNED: set[str] = set()


def _check_file_permissions(path: Path) -> None:
    """Warn to stderr (once per path per process) if a secrets file is
    world/group readable."""
    key = str(path)
    if key in _PERM_WARNED:
        return
    if os.name == "nt":
        # Windows reports every file as 0o666; access is governed by NTFS ACLs
        # (a user profile is private by default), so the mode check is noise.
        return
    try:
        mode = path.stat().st_mode
        if mode & 0o044:
            _PERM_WARNED.add(key)
            sys.stderr.write(
                f"[watch] WARNING: {path} is readable by other users. "
                f"Run: chmod 600 {path}\n"
            )
            sys.stderr.flush()
    except OSError:
        pass


def _read_env_key(name: str) -> str | None:
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    if not CONFIG_FILE.exists():
        return None
    _check_file_permissions(CONFIG_FILE)
    try:
        for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, raw = line.partition("=")
            if key.strip() != name:
                continue
            raw = raw.strip()
            if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
                raw = raw[1:-1]
            return raw or None
    except OSError:
        return None
    return None


def _have_api_key() -> tuple[bool, str | None]:
    if _read_env_key("GROQ_API_KEY"):
        return True, "groq"
    if _read_env_key("OPENAI_API_KEY"):
        return True, "openai"
    return False, None


def _transcriber() -> str | None:
    """The backend /watch would use for Whisper: groq, openai, local, or None."""
    has_key, backend = _have_api_key()
    if has_key:
        return backend
    if local_whisper_available():
        return "local"
    return None


def _pip_install_faster_whisper() -> bool:
    """pip install faster-whisper into the interpreter running this script."""
    base = [sys.executable, "-m", "pip", "install", "--upgrade", "faster-whisper"]
    attempts = [base]
    if sys.prefix == sys.base_prefix:  # not in a venv → --user is a sane retry
        attempts.append(base[:4] + ["--user"] + base[4:])
    for cmd in attempts:
        print(f"[setup] running: {' '.join(cmd)}", file=sys.stderr)
        if subprocess.run(cmd).returncode == 0:
            import importlib

            importlib.invalidate_caches()
            return True
    print(
        "[setup] pip install failed. If your Python is 'externally managed' (Homebrew, "
        "Debian/Ubuntu), install into a virtual environment or run:\n"
        f"  {Path(sys.executable).name} -m pip install --user --break-system-packages faster-whisper",
        file=sys.stderr,
    )
    return False


def cmd_install_local_whisper() -> int:
    if local_whisper_available():
        print("[setup] faster-whisper is already installed — local transcription is ready.")
        return 0
    if not _pip_install_faster_whisper():
        return 5
    print("[setup] faster-whisper installed — free offline transcription is ready.")
    print("[setup] the first transcription downloads the model (small is about 460 MB) once.")
    return 0


def is_first_run() -> bool:
    """True if the installer hasn't completed successfully yet."""
    return _read_env_key("SETUP_COMPLETE") != "true"


def _scaffold_env() -> bool:
    """Create ~/.config/watch/.env with placeholders if missing."""
    if CONFIG_FILE.exists():
        return False
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(ENV_TEMPLATE, encoding="utf-8")
    try:
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass
    return True


def _write_setup_complete() -> None:
    """Idempotently append SETUP_COMPLETE=true to .env.

    Used only after a fully successful install (deps + key). Future sessions
    detect this marker to skip wizard-style UI and stay silent.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = ""
    if CONFIG_FILE.exists():
        existing = CONFIG_FILE.read_text(encoding="utf-8")
        for line in existing.splitlines():
            if line.strip().startswith("SETUP_COMPLETE="):
                return
        if existing and not existing.endswith("\n"):
            existing += "\n"
        CONFIG_FILE.write_text(existing + "SETUP_COMPLETE=true\n", encoding="utf-8")
    else:
        CONFIG_FILE.write_text(ENV_TEMPLATE + "\nSETUP_COMPLETE=true\n", encoding="utf-8")
    try:
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass


def _brew_pkg(missing: list[str]) -> list[str]:
    pkgs: list[str] = []
    for bin_name in missing:
        if bin_name in ("ffmpeg", "ffprobe"):
            if "ffmpeg" not in pkgs:
                pkgs.append("ffmpeg")
        elif bin_name == "yt-dlp":
            if "yt-dlp" not in pkgs:
                pkgs.append("yt-dlp")
        else:
            pkgs.append(bin_name)
    return pkgs


def _install_macos(missing: list[str]) -> tuple[bool, str]:
    if _which("brew") is None:
        return False, (
            "Homebrew is not installed. Install it from https://brew.sh, then re-run setup. "
            "Or install manually: `brew install " + " ".join(_brew_pkg(missing)) + "`"
        )
    pkgs = _brew_pkg(missing)
    if not pkgs:
        return True, "nothing to install"
    cmd = ["brew", "install", *pkgs]
    print(f"[setup] running: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        return False, f"brew install failed with exit code {result.returncode}"
    return True, f"installed via brew: {', '.join(pkgs)}"


def _install_hint_linux(missing: list[str]) -> str:
    pkgs = _brew_pkg(missing)
    hints = []
    if "ffmpeg" in pkgs:
        hints.append("apt: `sudo apt install ffmpeg` or dnf: `sudo dnf install ffmpeg`")
    if "yt-dlp" in pkgs:
        hints.append("`pipx install yt-dlp` (recommended) or `pip install --user yt-dlp`")
    return "\n  ".join(hints) if hints else "nothing to install"


def _install_hint_windows(missing: list[str]) -> str:
    pkgs = _brew_pkg(missing)
    hints = []
    if "ffmpeg" in pkgs:
        hints.append("winget: `winget install Gyan.FFmpeg`")
    if "yt-dlp" in pkgs:
        hints.append("winget: `winget install yt-dlp.yt-dlp` or pip: `pip install --user yt-dlp`")
    return "\n  ".join(hints) if hints else "nothing to install"


def _status() -> dict:
    """Structured preflight snapshot.

    `status` describes the *ideal* state: a transcriber (an API key OR a local
    faster-whisper install) is encouraged, so an install with neither still
    reports `needs_key` on the very first run — that's the agent's cue to offer
    local Whisper (free) or a key.

    `can_proceed` is the operational gate: /watch can run as long as the
    binaries are present AND there is a transcriber or the user already
    finished setup (consciously opting out of Whisper). A user without one who
    completed setup is NOT nagged on every call.
    """
    missing = _check_binaries()
    has_key, _ = _have_api_key()
    local = local_whisper_available()
    backend = _transcriber()
    has_transcriber = backend is not None
    setup_complete = not is_first_run()

    if not missing and has_transcriber:
        status = "ready"
    elif missing and not has_transcriber:
        status = "needs_install_and_key"
    elif missing:
        status = "needs_install"
    else:
        status = "needs_key"

    can_proceed = (not missing) and (has_transcriber or setup_complete)

    cfg = get_config()
    return {
        "status": status,
        "can_proceed": can_proceed,
        "first_run": not setup_complete,
        "setup_complete": setup_complete,
        "missing_binaries": missing,
        "whisper_backend": backend,
        "has_api_key": has_key,
        "local_whisper": local,
        "whisper_model": cfg["whisper_model"],
        "config_file": str(CONFIG_FILE),
        "watch_detail": cfg["detail"],
        "platform": platform.system(),
    }


def cmd_check() -> int:
    """Silent-on-success preflight.

    Exit 0 with no output when /watch can run. A local faster-whisper install
    counts as a transcriber, so no API key is needed. A user with neither who
    already finished setup (SETUP_COMPLETE=true) also counts as ready — Whisper
    is encouraged, not required — so they are never nagged on follow-up calls.

    On a state that blocks /watch, print one actionable line to stderr:
      2 → binaries missing
      3 → genuine first run with no transcriber (offer local Whisper or a key)
      4 → both missing
    """
    s = _status()
    if s["can_proceed"]:
        return 0

    parts = []
    if s["missing_binaries"]:
        parts.append(f"missing binaries: {', '.join(s['missing_binaries'])}")
    if not s["whisper_backend"] and not s["setup_complete"]:
        parts.append(
            "no transcriber (install faster-whisper with --install-local-whisper, "
            "or set GROQ_API_KEY / OPENAI_API_KEY)"
        )
    installer = Path(__file__).resolve()
    sys.stderr.write(
        f"[watch] setup incomplete ({'; '.join(parts)}). "
        f"Run: python3 {installer}\n"
    )
    sys.stderr.flush()

    if s["missing_binaries"] and not s["whisper_backend"]:
        return 4
    if s["missing_binaries"]:
        return 2
    return 3


def cmd_json() -> int:
    json.dump(_status(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_install() -> int:
    missing = _check_binaries()
    installed_deps = False
    if missing:
        system = platform.system()
        if system == "Darwin":
            ok, msg = _install_macos(missing)
            print(f"[setup] {msg}", file=sys.stderr)
            if not ok:
                return 2
            still_missing = _check_binaries()
            if still_missing:
                print(f"[setup] still missing after install: {', '.join(still_missing)}", file=sys.stderr)
                return 2
            installed_deps = True
        elif system == "Linux":
            print("[setup] dependencies missing on Linux — please install:", file=sys.stderr)
            print("  " + _install_hint_linux(missing), file=sys.stderr)
            return 2
        elif system == "Windows":
            print("[setup] dependencies missing on Windows — please install:", file=sys.stderr)
            print("  " + _install_hint_windows(missing), file=sys.stderr)
            return 2
        else:
            print(f"[setup] unsupported platform ({system}) for auto-install. Install manually:", file=sys.stderr)
            print(f"  missing: {', '.join(missing)}", file=sys.stderr)
            return 2

    created = _scaffold_env()
    if created:
        print(f"[setup] created config: {CONFIG_FILE}")
    else:
        print(f"[setup] config exists: {CONFIG_FILE}")

    backend = _transcriber()
    if backend is None and sys.stdin is not None and sys.stdin.isatty():
        answer = input(
            "[setup] No API key and no local Whisper. Install faster-whisper now for free, "
            "offline transcription? [Y/n] "
        ).strip().lower()
        if answer in ("", "y", "yes") and _pip_install_faster_whisper():
            backend = _transcriber()

    if backend:
        _write_setup_complete()
        label = "local faster-whisper (offline, no key)" if backend == "local" else backend
        print(f"[setup] ready. whisper backend: {label}")
        if installed_deps:
            print("[setup] installed dependencies; /watch is fully set up.")
        return 0

    print("")
    print("[setup] one step left: give /watch a way to transcribe videos without captions.")
    print("")
    print("  Free and offline (recommended, no key):")
    print(f"    {Path(sys.executable).name} {Path(__file__).resolve()} --install-local-whisper")
    print("")
    print(f"  Or edit {CONFIG_FILE} and set either:")
    print("    GROQ_API_KEY=...    (fast, cheap; get one at console.groq.com/keys)")
    print("    OPENAI_API_KEY=...  (get one at platform.openai.com/api-keys)")
    print("")
    print("  Without either, /watch still works but videos without captions come back frames-only.")
    return 3


def main() -> int:
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--check":
            return cmd_check()
        if arg == "--json":
            return cmd_json()
        if arg == "--install-local-whisper":
            return cmd_install_local_whisper()
    return cmd_install()


if __name__ == "__main__":
    raise SystemExit(main())
