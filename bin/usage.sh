#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$DIR/../skills/usage/scripts/usage.py"

if [ ! -f "$SCRIPT_PATH" ]; then
    SCRIPT_PATH="$HOME/.gemini/config/plugins/antigravity-usage/skills/usage/scripts/usage.py"
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    SCRIPT_PATH="$HOME/.gemini/config/skills/usage/scripts/usage.py"
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: usage.py script not found." >&2
    exit 1
fi

if command -v python3 >/dev/null 2>&1; then
    exec python3 "$SCRIPT_PATH" "$@"
elif command -v python >/dev/null 2>&1; then
    exec python "$SCRIPT_PATH" "$@"
else
    echo "Error: Python was not found on PATH." >&2
    exit 1
fi
