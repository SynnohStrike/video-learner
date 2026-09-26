#!/usr/bin/env bash
# SessionStart hook for video-learner's /watch — one-line status so users know
# what's wired up. Silent on ready state to avoid spam. Points at the installer
# when something is missing.
#
# Based on the check-setup hook from claude-video by Bradley Bonanno (MIT).
set -euo pipefail

CONFIG_FILE="$HOME/.config/watch/.env"
SETUP_PY="\$CLAUDE_PLUGIN_ROOT/skills/watch/scripts/setup.py"

# Warn if the secrets file has loose permissions. Skipped on Windows (Git Bash /
# MSYS / Cygwin), where mode bits are synthetic and access is governed by ACLs.
case "$(uname -s 2>/dev/null || echo unknown)" in
  MINGW*|MSYS*|CYGWIN*) ;;
  *)
    if [[ -f "$CONFIG_FILE" ]]; then
      perms=$(stat -c '%a' "$CONFIG_FILE" 2>/dev/null || stat -f '%Lp' "$CONFIG_FILE" 2>/dev/null || echo "")
      if [[ -n "$perms" && "$perms" != "600" && "$perms" != "400" ]]; then
        echo "/watch: WARNING — $CONFIG_FILE has permissions $perms (should be 600)."
        echo "  Fix: chmod 600 $CONFIG_FILE"
      fi
    fi
    ;;
esac

# Load API keys from the config file without exporting them.
read_key() {
  local name="$1"
  if [[ -n "${!name:-}" ]]; then
    echo "${!name}"
    return
  fi
  if [[ -f "$CONFIG_FILE" ]]; then
    awk -F= -v k="$name" '
      /^[[:space:]]*#/ { next }
      $1 == k {
        sub(/^[[:space:]]*/, "", $2); sub(/[[:space:]]*$/, "", $2);
        gsub(/^["'\'']|["'\'']$/, "", $2);
        print $2; exit
      }
    ' "$CONFIG_FILE"
  fi
}

HAS_FFMPEG=""
HAS_YTDLP=""
command -v ffmpeg >/dev/null 2>&1 && HAS_FFMPEG="yes"
command -v yt-dlp >/dev/null 2>&1 && HAS_YTDLP="yes"

HAS_GROQ="$(read_key GROQ_API_KEY)"
HAS_OPENAI="$(read_key OPENAI_API_KEY)"
SETUP_COMPLETE="$(read_key SETUP_COMPLETE)"

# Fully configured → silent (Claude can surface status on demand via --check).
if [[ "$SETUP_COMPLETE" == "true" && -n "$HAS_FFMPEG" && -n "$HAS_YTDLP" ]]; then
  exit 0
fi

# Is faster-whisper importable? (find_spec does not import it, so this is fast.)
HAS_LOCAL=""
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1 && \
     "$py" -c 'import importlib.util,sys; sys.exit(0 if importlib.util.find_spec("faster_whisper") else 1)' >/dev/null 2>&1; then
    HAS_LOCAL="yes"
    break
  fi
done

# First-run / partially-configured → one-line hint.
if [[ -z "$HAS_FFMPEG" || -z "$HAS_YTDLP" ]]; then
  echo "/watch: needs ffmpeg + yt-dlp. Run \`python3 $SETUP_PY\` once to install and scaffold config."
elif [[ -z "$HAS_GROQ" && -z "$HAS_OPENAI" && -z "$HAS_LOCAL" ]]; then
  echo "/watch: ready for videos with native captions. For videos without captions, run \`python3 $SETUP_PY --install-local-whisper\` (free, offline) or add GROQ_API_KEY / OPENAI_API_KEY to ~/.config/watch/.env."
else
  echo "/watch: ready."
fi
