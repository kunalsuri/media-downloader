#!/usr/bin/env bash
# =============================================================================
#  launch.sh — Media Downloader | macOS / Linux launcher
#
#  Usage:
#    chmod +x launch.sh && ./launch.sh
#
#  What it does:
#    1. Verifies Python 3.10+ is on PATH
#    2. Creates / reuses a virtual environment at .venv/
#    3. Installs packages from requirements.txt
#    3.5 Checks for yt-dlp updates and installs the latest if available
#    4. Launches Streamlit at http://localhost:8501
#
#  Environment variables (all optional):
#    STREAMLIT_PORT  — Port for the server (default: 8501)
#    RECREATE_VENV   — Set to 1 to delete and rebuild .venv
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")"

# ── Validate required project files ─────────────────────────────────────────
if [ ! -f "app.py" ]; then
    echo " [ERROR] app.py not found. Run launch.sh from inside the project folder."
    exit 1
fi
if [ ! -f "requirements.txt" ]; then
    echo " [ERROR] requirements.txt not found."
    exit 1
fi

STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

echo
echo " +----------------------------------------------------------+"
echo " |  ⬇️  Media Downloader  |  Setup & Launcher              |"
echo " +----------------------------------------------------------+"
echo

# =============================================================================
#  STEP 1 — Verify Python 3.10+
# =============================================================================
echo " [1/4] Checking Python..."

if ! command -v python3 &>/dev/null; then
    echo " [ERROR] python3 not found. Install Python 3.10+ from https://python.org"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo " [ERROR] Python 3.10+ required. Found: ${PY_VER}"
    exit 1
fi
echo " [OK]   Python ${PY_VER} found."

# =============================================================================
#  STEP 2 — Create or reuse virtual environment
# =============================================================================
echo
echo " [2/4] Setting up virtual environment..."

if [ "${RECREATE_VENV:-0}" = "1" ] && [ -d ".venv" ]; then
    echo " [WARN]  RECREATE_VENV=1 — removing existing .venv/ ..."
    rm -rf .venv
fi

FIRST_RUN=0
if [ ! -f ".venv/bin/activate" ]; then
    echo " [SETUP] Creating virtual environment at .venv/ ..."
    python3 -m venv --upgrade-deps .venv
    echo " [OK]   Virtual environment created."
    FIRST_RUN=1
else
    echo " [OK]   Existing virtual environment found."
fi

# shellcheck source=/dev/null
source .venv/bin/activate
echo " [OK]   Virtual environment activated."

# =============================================================================
#  STEP 3 — Install / verify packages
# =============================================================================
echo
echo " [3/4] Installing / verifying packages..."

if [ "$FIRST_RUN" -eq 1 ]; then
    python3 -m pip install --quiet --upgrade pip
    echo " [SETUP] Installing packages from requirements.txt ..."
    pip install --no-cache-dir -r requirements.txt
    echo " [OK]   All packages installed."
else
    pip install --quiet --no-cache-dir -r requirements.txt
    echo " [OK]   Packages verified."
fi

# =============================================================================
#  STEP 3.5 — Check for yt-dlp updates
#
#  Runs BEFORE Streamlit so the new version is active for this session.
#  Skipped silently when offline (exit 0).
# =============================================================================
echo
echo " [3.5/4] Checking for yt-dlp updates..."

if python3 -m downloader.updater; then
    : # success — output already printed by the updater
else
    echo " [WARN]  yt-dlp update attempt returned an error (see above)."
    echo "         The app will start with the currently installed version."
fi

# =============================================================================
#  STEP 4 — Launch Streamlit
# =============================================================================
echo
echo " [4/4] Starting Media Downloader..."
mkdir -p downloads

echo
echo " +----------------------------------------------------------+"
echo " |  App running at http://localhost:${STREAMLIT_PORT}"
echo " |  Press Ctrl+C to stop the server."
echo " +----------------------------------------------------------+"
echo

streamlit run app.py \
    "--server.port=${STREAMLIT_PORT}" \
    "--server.headless=false" \
    "--browser.gatherUsageStats=false"

echo
echo " Server stopped. Press Enter to close."
read -r
