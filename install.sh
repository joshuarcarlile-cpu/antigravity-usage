#!/usr/bin/env bash
set -e

echo "============================================================"
echo " Installing Antigravity /usage Telemetry Engine"
echo "============================================================"

HOME_DIR="${HOME}"
SKILL_DIR="${HOME_DIR}/.gemini/config/skills/usage"
LEGACY_PLUGIN_DIR="${HOME_DIR}/.gemini/config/plugins/antigravity-usage"
BIN_DIR="${HOME_DIR}/.gemini/antigravity-ide/bin"
AGY_BIN="${HOME_DIR}/.gemini/antigravity/bin"
LOCAL_BIN="${HOME_DIR}/.local/bin"

# 0. Clean up legacy plugin directory to prevent duplicate skill discovery
if [ -d "${LEGACY_PLUGIN_DIR}" ]; then
    echo "-> Removing legacy plugin directory to prevent duplications..."
    rm -rf "${LEGACY_PLUGIN_DIR}"
fi

mkdir -p "${SKILL_DIR}"
mkdir -p "${BIN_DIR}"
mkdir -p "${AGY_BIN}"
mkdir -p "${LOCAL_BIN}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IS_DEV=false
for arg in "$@"; do
    if [ "$arg" = "--dev" ]; then
        IS_DEV=true
    fi
done

if [ -f "${SCRIPT_DIR}/skills/usage/SKILL.md" ]; then
    if [ "$IS_DEV" = true ]; then
        echo "-> Installing in DEVELOPER MODE (Symlink)..."
        rm -rf "${SKILL_DIR}"
        ln -sfn "${SCRIPT_DIR}/skills/usage" "${SKILL_DIR}"
        echo "-> Live symlink linked: ${SKILL_DIR} -> ${SCRIPT_DIR}/skills/usage"
    else
        echo "-> Installing from local repository..."
        rm -rf "${SKILL_DIR}"/*
        cp -R "${SCRIPT_DIR}/skills/usage/"* "${SKILL_DIR}/"
    fi
    CLI_WRAPPER="${SCRIPT_DIR}/bin/usage.sh"
else
    echo "-> Downloading from GitHub..."
    TEMP_DIR="$(mktemp -d)"
    ARCHIVE_URL="https://github.com/joshuarcarlile-cpu/antigravity-usage/archive/refs/heads/main.tar.gz"
    curl -fsSL "${ARCHIVE_URL}" | tar -xz -C "${TEMP_DIR}" --strip-components=1
    rm -rf "${SKILL_DIR}"/*
    cp -R "${TEMP_DIR}/skills/usage/"* "${SKILL_DIR}/"
    CLI_WRAPPER="${TEMP_DIR}/bin/usage.sh"
fi

chmod +x "${CLI_WRAPPER}"
cp "${CLI_WRAPPER}" "${BIN_DIR}/usage"
cp "${CLI_WRAPPER}" "${AGY_BIN}/usage"
cp "${CLI_WRAPPER}" "${LOCAL_BIN}/usage"

if [ -n "${TEMP_DIR}" ] && [ -d "${TEMP_DIR}" ]; then
    rm -rf "${TEMP_DIR}"
fi

echo "-> CLI wrappers installed to ${BIN_DIR}/usage, ${AGY_BIN}/usage, and ${LOCAL_BIN}/usage"

# Verify installation with unit tests
if command -v python3 >/dev/null 2>&1; then
    echo "-> Verifying installation..."
    python3 "${SKILL_DIR}/tests/test_usage.py"
fi

echo ""
echo "Installation Complete!"
echo "  1. In any Antigravity chat, type: /usage or /cost"
echo "  2. In your terminal, run: usage (or usage --daily, usage --json)"
