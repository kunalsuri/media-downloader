#!/usr/bin/env bash
# =============================================================================
#  run_tests.sh — One-click test runner for Media Downloader (macOS / Linux)
#
#  Usage:
#    chmod +x run_tests.sh && ./run_tests.sh        # all offline tests
#    ./run_tests.sh --network                        # + PyPI & YouTube live
#    ./run_tests.sh --cov                            # + coverage report
# =============================================================================
set -euo pipefail

echo
echo "========================================"
echo " Media Downloader | Test Suite"
echo "========================================"
echo

# ── Activate virtual environment if present ──────────────────────────────────
if [ -f ".venv/bin/activate" ]; then
    echo "[*] Activating virtual environment (.venv) ..."
    # shellcheck source=/dev/null
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    echo "[*] Activating virtual environment (venv) ..."
    # shellcheck source=/dev/null
    source venv/bin/activate
else
    echo "[!] No .venv found — running with system Python."
    echo "    For isolation: python -m venv .venv && source .venv/bin/activate"
    echo
fi

# ── Install dev dependencies ─────────────────────────────────────────────────
echo "[*] Installing test dependencies (requirements-dev.txt) ..."
pip install -r requirements-dev.txt -q
echo

# ── Parse arguments ──────────────────────────────────────────────────────────
NETWORK=false
COV=false

for arg in "$@"; do
    case "$arg" in
        --network) NETWORK=true ;;
        --cov)     COV=true ;;
    esac
done

# ── Build pytest command ─────────────────────────────────────────────────────
PYTEST_ARGS=("--tb=short" "-v")

if [ "$NETWORK" = false ]; then
    PYTEST_ARGS+=("-m" "not network and not slow")
    echo "[*] Offline mode: network/slow tests skipped (pass --network to include)."
else
    echo "[*] Network mode: PyPI + YouTube live tests INCLUDED."
fi

if [ "$COV" = true ]; then
    PYTEST_ARGS+=("--cov=downloader" "--cov-report=term-missing")
    echo "[*] Coverage mode: terminal report enabled."
fi

echo

# ── Run pytest ────────────────────────────────────────────────────────────────
echo "[*] Running tests ..."
echo

set +e
pytest "${PYTEST_ARGS[@]}"
EXIT_CODE=$?
set -e

# ── Summary ───────────────────────────────────────────────────────────────────
echo
echo "========================================"
if [ "$EXIT_CODE" -eq 0 ]; then
    echo " RESULT: ALL TESTS PASSED  ✓"
else
    echo " RESULT: SOME TESTS FAILED  ✗"
    echo " Review the output above for details."
fi
echo "========================================"
echo

exit "$EXIT_CODE"
