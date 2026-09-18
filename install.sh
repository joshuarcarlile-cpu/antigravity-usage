#!/usr/bin/env bash
set -e

echo "============================================================"
echo " Installing Antigravity /usage Telemetry Engine"
echo "============================================================"

HOME_DIR="${HOME}"
PLUGIN_DIR="${HOME_DIR}/.gemini/config/plugins/antigravity-usage"
BIN_DIR="${HOME_DIR}/.gemini/antigravity-ide/bin"
LOCAL_BIN="${HOME_DIR}/.local/bin"

mkdir -p "${PLUGIN_DIR}"
mkdir -p "${BIN_DIR}"
mkdir -p "${LOCAL_BIN}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "${SCRIPT_DIR}/plugin.json" ]; then
    echo "-> Installing from local repository..."
    cp -R "${SCRIPT_DIR}/"* "${PLUGIN_DIR}/"
else
    echo "-> Downloading from GitHub..."
    ARCHIVE_URL="https://github.com/joshuarcarlile-cpu/antigravity-usage/archive/refs/heads/main.tar.gz"
    curl -fsSL "${ARCHIVE_URL}" | tar -xz -C "${PLUGIN_DIR}" --strip-components=1
fi

chmod +x "${PLUGIN_DIR}/bin/usage.sh"
cp "${PLUGIN_DIR}/bin/usage.sh" "${BIN_DIR}/usage"
cp "${PLUGIN_DIR}/bin/usage.sh" "${LOCAL_BIN}/usage"

echo "-> CLI wrappers installed to ${BIN_DIR}/usage and ${LOCAL_BIN}/usage"

# Verify installation with unit tests
if command -v python3 >/dev/null 2>&1; then
    echo "-> Verifying installation..."
    python3 "${PLUGIN_DIR}/skills/usage/tests/test_usage.py"
fi

echo ""
echo "Installation Complete!"
echo "  1. In any Antigravity chat, type: /usage or /cost"
echo "  2. In your terminal, run: usage (or usage --daily, usage --json)"
