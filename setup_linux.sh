#!/usr/bin/env bash
# =============================================================================
#  setup_linux.sh — Linux Setup & Launcher for Media Downloader
# =============================================================================
#
#  USAGE
#    chmod +x setup_linux.sh   # (first time only)
#    ./setup_linux.sh
#
#  WHAT IT DOES
#    1. Detects the Linux distribution and CPU architecture
#    2. Identifies the correct native package manager (apt, dnf, pacman)
#    3. Checks for required tools: Python 3, pip, git, ffmpeg, venv module
#    4. Installs any missing system tools using the native package manager
#    5. Creates / re-uses a Python virtual environment at .venv/
#    6. Upgrades pip, wheel, and setuptools inside the venv
#    7. Installs / upgrades all Python packages from requirements.txt
#    8. Verifies the installed packages are importable
#    9. Ensures the downloads/ directory exists
#   10. Launches the Streamlit app in the browser
#
#  SUPPORTED DISTRIBUTIONS
#    • Ubuntu 20.04 LTS and later
#    • Debian 11 (Bullseye) and later
#    • Fedora 36 and later
#    • RHEL / CentOS Stream / Rocky Linux 8+
#    • Arch Linux and Manjaro
#    • Any Debian-based, RPM-based, or Arch-based distro
#
#  REQUIREMENTS
#    • An internet connection for first-time dependency installation
#    • sudo privileges for system package installation (only first time)
#
#  ENVIRONMENT VARIABLES (all optional)
#    STREAMLIT_PORT    — Port for the Streamlit server           (default: 8501)
#    SKIP_PKG_MANAGER  — Set to "1" to skip system package checks (default: 0)
#    RECREATE_VENV     — Set to "1" to delete and rebuild .venv  (default: 0)
#
#  EXAMPLES
#    ./setup_linux.sh                           # standard run
#    STREAMLIT_PORT=8888 ./setup_linux.sh       # custom port
#    SKIP_PKG_MANAGER=1 ./setup_linux.sh        # skip system package checks
#    RECREATE_VENV=1 ./setup_linux.sh           # fresh venv rebuild
#
# =============================================================================

set -euo pipefail   # Exit immediately on error, unset variable, or pipe failure

# ─── Terminal colour helpers ──────────────────────────────────────────────────
if [ -t 1 ]; then
    C_RESET="\033[0m"
    C_BOLD="\033[1m"
    C_RED="\033[31m"
    C_GREEN="\033[32m"
    C_YELLOW="\033[33m"
    C_BLUE="\033[34m"
    C_CYAN="\033[36m"
else
    C_RESET="" C_BOLD="" C_RED="" C_GREEN="" C_YELLOW="" C_BLUE="" C_CYAN=""
fi

# ─── Logging functions ────────────────────────────────────────────────────────
log_info()   { echo -e "${C_BLUE}[INFO]${C_RESET}  $(date '+%H:%M:%S')  $*"; }
log_ok()     { echo -e "${C_GREEN}[OK]${C_RESET}    $(date '+%H:%M:%S')  $*"; }
log_warn()   { echo -e "${C_YELLOW}[WARN]${C_RESET}  $(date '+%H:%M:%S')  $*"; }
log_error()  { echo -e "${C_RED}[ERROR]${C_RESET} $(date '+%H:%M:%S')  $*" >&2; }
log_step()   { echo -e "\n${C_BOLD}${C_CYAN}▶ $*${C_RESET}"; }
log_banner() {
    echo -e "\n${C_BOLD}${C_CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║       ⬇️  Media Downloader — Linux Setup & Launcher          ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${C_RESET}"
}

# ─── Error handler ───────────────────────────────────────────────────────────
trap 'log_error "Script failed at line ${LINENO}. Exiting."; exit 1' ERR

# ─── Cleanup on unexpected exit ──────────────────────────────────────────────
_VENV_WAS_NEW=0
cleanup() {
    local exit_code=$?
    if [[ "$_VENV_WAS_NEW" == "1" && -d "${VENV_DIR:-}" && "$exit_code" -ne 0 ]]; then
        log_warn "Removing incomplete virtual environment due to setup failure…"
        rm -rf "$VENV_DIR"
    fi
}
trap cleanup EXIT

# ─── Helper: retry a command up to N times with a short pause ────────────────
retry() {
    local attempts="$1"
    local delay="$2"
    shift 2
    local count=0
    until "$@"; do
        count=$(( count + 1 ))
        if [ "$count" -ge "$attempts" ]; then
            log_error "Command failed after ${attempts} attempt(s): $*"
            return 1
        fi
        log_warn "Attempt ${count}/${attempts} failed — retrying in ${delay}s…"
        sleep "$delay"
    done
}

# ─── Helper: check if a command exists on PATH ───────────────────────────────
have() { command -v "$1" &>/dev/null; }

# ─── Helper: run sudo only when not already root ─────────────────────────────
# This avoids "sudo: command not found" errors in minimal Docker containers.
maybe_sudo() {
    if [[ "$EUID" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

# =============================================================================
#  SECTION 0 — Banner, OS validation & environment setup
# =============================================================================
log_banner

# Confirm we are running on Linux.
if [[ "$(uname -s)" != "Linux" ]]; then
    log_error "This script is designed for Linux only. Detected OS: $(uname -s)"
    log_info  "For macOS, run:   ./setup_macos.sh"
    log_info  "For Windows, run: .\\setup_windows.ps1  (in PowerShell)"
    exit 1
fi

# Detect CPU architecture.
ARCH="$(uname -m)"
log_info "Architecture: ${ARCH}"

# Read environment variable overrides with safe defaults.
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"
SKIP_PKG_MANAGER="${SKIP_PKG_MANAGER:-0}"
RECREATE_VENV="${RECREATE_VENV:-0}"

# Resolve the absolute path to the project directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
REQUIREMENTS="${SCRIPT_DIR}/requirements.txt"

log_info "Project root  : ${SCRIPT_DIR}"
log_info "Virtual env   : ${VENV_DIR}"
log_info "Streamlit port: ${STREAMLIT_PORT}"

# =============================================================================
#  SECTION 1 — Detect Linux distribution and package manager
# =============================================================================
log_step "Detecting Linux distribution"

PKG_MANAGER=""        # "apt" | "dnf" | "yum" | "pacman"
DISTRO_NAME=""

# /etc/os-release is the standard file for distribution identification.
if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    DISTRO_NAME="${NAME:-unknown}"
    DISTRO_ID="${ID:-unknown}"
    DISTRO_ID_LIKE="${ID_LIKE:-}"
    log_info "Distribution : ${DISTRO_NAME}"
    log_info "Distro ID    : ${DISTRO_ID}"
else
    log_warn "/etc/os-release not found — attempting package manager detection by binary."
    DISTRO_NAME="Unknown Linux"
    DISTRO_ID="unknown"
    DISTRO_ID_LIKE=""
fi

# Determine package manager based on distro ID and ID_LIKE.
_ids="${DISTRO_ID} ${DISTRO_ID_LIKE}"

if echo "$_ids" | grep -qiE 'ubuntu|debian|raspbian|linuxmint|elementary|pop'; then
    PKG_MANAGER="apt"
elif echo "$_ids" | grep -qiE 'fedora|rhel|centos|rocky|almalinux|ol'; then
    # Prefer dnf (Fedora 22+, RHEL 8+), fall back to yum for older RHEL/CentOS.
    if have dnf; then
        PKG_MANAGER="dnf"
    else
        PKG_MANAGER="yum"
    fi
elif echo "$_ids" | grep -qiE 'arch|manjaro|endeavouros|garuda'; then
    PKG_MANAGER="pacman"
elif have apt-get; then
    PKG_MANAGER="apt"
elif have dnf; then
    PKG_MANAGER="dnf"
elif have yum; then
    PKG_MANAGER="yum"
elif have pacman; then
    PKG_MANAGER="pacman"
else
    log_error "Could not detect a supported package manager (apt / dnf / pacman)."
    log_info  "Please install Python 3.10+, pip, git, and ffmpeg manually, then re-run"
    log_info  "this script with SKIP_PKG_MANAGER=1 to skip automatic installation."
    exit 1
fi

log_ok "Package manager: ${PKG_MANAGER}"

# =============================================================================
#  SECTION 2 — Validate project files
# =============================================================================
log_step "Validating project files"

if [[ ! -f "${SCRIPT_DIR}/app.py" ]]; then
    log_error "app.py not found in ${SCRIPT_DIR}."
    log_info  "Please run this script from inside the project directory."
    exit 1
fi

if [[ ! -f "$REQUIREMENTS" ]]; then
    log_error "requirements.txt not found at ${REQUIREMENTS}."
    exit 1
fi

log_ok "app.py and requirements.txt found."

# =============================================================================
#  SECTION 3 — Install system dependencies
# =============================================================================
log_step "Checking and installing system dependencies"

if [[ "$SKIP_PKG_MANAGER" == "1" ]]; then
    log_warn "SKIP_PKG_MANAGER=1 — skipping system package installation."
else
    # ── apt (Ubuntu / Debian) ─────────────────────────────────────────────────
    if [[ "$PKG_MANAGER" == "apt" ]]; then
        log_info "Updating apt package index…"
        retry 3 5 maybe_sudo apt-get update -qq

        log_info "Installing/verifying: python3, python3-pip, python3-venv, git, ffmpeg…"
        retry 3 10 maybe_sudo apt-get install -y -qq \
            python3 \
            python3-pip \
            python3-venv \
            git \
            ffmpeg \
            curl \
            ca-certificates
        log_ok "apt packages installed/verified."

    # ── dnf (Fedora / RHEL 8+ / CentOS Stream) ───────────────────────────────
    elif [[ "$PKG_MANAGER" == "dnf" ]]; then
        log_info "Installing/verifying: python3, python3-pip, git, ffmpeg…"
        # ffmpeg requires RPM Fusion repository on Fedora/RHEL.
        # We attempt to enable it; if it fails we continue — user may already have it.
        if ! rpm -q ffmpeg &>/dev/null; then
            log_info "Enabling RPM Fusion repository for ffmpeg…"
            maybe_sudo dnf install -y -q \
                "https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm" \
                "https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm" \
                2>/dev/null || log_warn "RPM Fusion setup skipped — ffmpeg may not be available."
        fi
        retry 3 10 maybe_sudo dnf install -y -q \
            python3 \
            python3-pip \
            git \
            ffmpeg \
            curl \
            ca-certificates 2>/dev/null || \
            retry 3 10 maybe_sudo dnf install -y -q python3 python3-pip git curl ca-certificates
        log_ok "dnf packages installed/verified."

    # ── yum (RHEL 7 / CentOS 7) ──────────────────────────────────────────────
    elif [[ "$PKG_MANAGER" == "yum" ]]; then
        log_info "Installing/verifying packages via yum…"
        retry 3 10 maybe_sudo yum install -y -q \
            python3 \
            python3-pip \
            git \
            curl
        # ffmpeg on old RHEL/CentOS requires EPEL + RPM Fusion; skip if unavailable.
        maybe_sudo yum install -y -q ffmpeg 2>/dev/null || \
            log_warn "ffmpeg not installed via yum. MP3/high-quality video may not work."
        log_ok "yum packages installed/verified."

    # ── pacman (Arch / Manjaro) ───────────────────────────────────────────────
    elif [[ "$PKG_MANAGER" == "pacman" ]]; then
        log_info "Syncing package database and installing/verifying packages…"
        retry 3 10 maybe_sudo pacman -Sy --noconfirm --needed \
            python \
            python-pip \
            git \
            ffmpeg \
            curl \
            ca-certificates
        log_ok "pacman packages installed/verified."
    fi
fi

# =============================================================================
#  SECTION 4 — Check Python 3 (≥ 3.10)
# =============================================================================
log_step "Checking Python 3"

PYTHON_BIN=""
for candidate in python3 python; do
    if have "$candidate"; then
        version_output="$("$candidate" --version 2>&1)"
        major="$(echo "$version_output" | grep -oE '[0-9]+' | head -1)"
        if [[ "$major" == "3" ]]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    log_error "Python 3 not found on PATH after installation attempt."
    log_info  "Please install Python 3.10+ manually and re-run this script."
    exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" --version 2>&1)"
log_ok "Python found: ${PYTHON_VERSION} (${PYTHON_BIN})"

# Enforce minimum version 3.10 (required by Streamlit ≥ 1.35).
PYTHON_MINOR="$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.minor)')"
PYTHON_MAJOR="$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.major)')"
if [[ "$PYTHON_MAJOR" -lt 3 ]] || { [[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -lt 10 ]]; }; then
    log_error "Python 3.10 or newer is required. Found: ${PYTHON_VERSION}"
    log_info  "On Ubuntu: sudo apt install python3.11"
    log_info  "On Fedora: sudo dnf install python3.11"
    log_info  "Or visit: https://www.python.org/downloads/"
    exit 1
fi
log_ok "Python version OK (≥ 3.10)"

# Verify the venv module is available (some distros ship it separately).
if ! "$PYTHON_BIN" -m venv --help &>/dev/null; then
    log_warn "python3-venv module not found. Attempting to install…"
    case "$PKG_MANAGER" in
        apt)    maybe_sudo apt-get install -y -qq "python$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')-venv" python3-venv ;;
        dnf)    maybe_sudo dnf install -y -q python3-venv ;;
        pacman) log_info "venv is included with python on Arch." ;;
        *)      log_error "Cannot auto-install python3-venv. Install it manually." ; exit 1 ;;
    esac
fi

# =============================================================================
#  SECTION 5 — Check ffmpeg (informational, non-fatal)
# =============================================================================
log_step "Checking ffmpeg"

if have ffmpeg; then
    log_ok "ffmpeg found: $(ffmpeg -version 2>&1 | head -1)"
else
    log_warn "ffmpeg not found on PATH."
    log_warn "MP3 extraction and high-quality video merging will not work."
    log_warn "To install ffmpeg manually:"
    log_info "  Ubuntu/Debian: sudo apt install ffmpeg"
    log_info "  Fedora:        sudo dnf install ffmpeg"
    log_info "  Arch:          sudo pacman -S ffmpeg"
fi

# =============================================================================
#  SECTION 6 — Create / re-use Python virtual environment
# =============================================================================
log_step "Setting up Python virtual environment"

if [[ "$RECREATE_VENV" == "1" && -d "$VENV_DIR" ]]; then
    log_warn "RECREATE_VENV=1 — removing existing virtual environment…"
    rm -rf "$VENV_DIR"
    log_ok "Old virtual environment removed."
fi

if [[ -d "$VENV_DIR" ]]; then
    log_info "Existing virtual environment found at ${VENV_DIR}."
else
    log_info "Creating virtual environment at ${VENV_DIR}…"
    "$PYTHON_BIN" -m venv --upgrade-deps "$VENV_DIR"
    _VENV_WAS_NEW=1
    log_ok "Virtual environment created."
fi

# Activate the venv for the remainder of this script.
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
log_ok "Virtual environment activated. Python: $(python --version), pip: $(pip --version | awk '{print $2}')"

# =============================================================================
#  SECTION 7 — Upgrade pip, wheel, and setuptools
# =============================================================================
log_step "Upgrading pip and build tools"

retry 3 5 pip install --quiet --upgrade pip
retry 3 5 pip install --quiet --upgrade wheel setuptools
log_ok "pip, wheel, and setuptools are up to date."

# =============================================================================
#  SECTION 8 — Install Python packages from requirements.txt
# =============================================================================
log_step "Installing Python packages from requirements.txt"

log_info "Running: pip install -r ${REQUIREMENTS}"
retry 3 10 pip install --no-cache-dir --upgrade -r "$REQUIREMENTS"
log_ok "All Python packages installed."

# =============================================================================
#  SECTION 9 — Verify critical package imports
# =============================================================================
log_step "Verifying package imports"

check_import() {
    local module="$1"
    if python -c "import ${module}" &>/dev/null; then
        log_ok "  ✔  ${module}"
    else
        log_error "Failed to import '${module}'."
        log_info  "Try: RECREATE_VENV=1 ./setup_linux.sh"
        exit 1
    fi
}

check_import streamlit
check_import yt_dlp
check_import requests
check_import certifi

log_ok "All critical imports verified."

# =============================================================================
#  SECTION 10 — Ensure the downloads directory exists
# =============================================================================
log_step "Checking downloads directory"

DOWNLOADS_DIR="${SCRIPT_DIR}/downloads"
if [[ ! -d "$DOWNLOADS_DIR" ]]; then
    mkdir -p "$DOWNLOADS_DIR"
    log_ok "Created downloads/ directory."
else
    log_ok "downloads/ directory exists."
fi

# =============================================================================
#  SECTION 11 — Launch Streamlit
# =============================================================================
log_step "Launching Streamlit application"

echo
echo -e "${C_BOLD}${C_GREEN}✅  Setup complete!${C_RESET}"
echo -e "   Opening ${C_CYAN}http://localhost:${STREAMLIT_PORT}${C_RESET} in your browser…"
echo -e "   Press ${C_BOLD}Ctrl + C${C_RESET} to stop the server.\n"

# Open the browser automatically on Linux using the first available launcher.
# This is best-effort; Streamlit also has its own browser-open mechanism.
(sleep 3 && {
    if have xdg-open; then
        xdg-open "http://localhost:${STREAMLIT_PORT}"
    elif have gnome-open; then
        gnome-open "http://localhost:${STREAMLIT_PORT}"
    elif have firefox; then
        firefox "http://localhost:${STREAMLIT_PORT}" &
    elif have google-chrome; then
        google-chrome "http://localhost:${STREAMLIT_PORT}" &
    fi
}) &>/dev/null &

cd "$SCRIPT_DIR"

exec streamlit run app.py \
    "--server.port=${STREAMLIT_PORT}" \
    "--server.headless=false" \
    "--browser.gatherUsageStats=false"
