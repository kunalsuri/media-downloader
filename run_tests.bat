@echo off
REM =========================================================================
REM  run_tests.bat — One-click test runner for Media Downloader (Windows)
REM
REM  Usage:
REM    Double-click this file  — runs all offline tests
REM    run_tests.bat --network — also runs PyPI + YouTube live tests
REM    run_tests.bat --cov     — adds coverage report
REM  =========================================================================
setlocal

echo.
echo ========================================
echo  Media Downloader ^| Test Suite
echo ========================================
echo.

REM ── Activate virtual environment if present ──────────────────────────────
if exist ".venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment (.venv) ...
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment (venv) ...
    call venv\Scripts\activate.bat
) else (
    echo [!] No .venv found — running with system Python.
    echo     For isolation: python -m venv .venv ^&^& .venv\Scripts\activate
    echo.
)

REM ── Install dev dependencies ─────────────────────────────────────────────
echo [*] Installing test dependencies (requirements-dev.txt) ...
pip install -r requirements-dev.txt -q
if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)
echo.

REM ── Resolve pytest arguments ─────────────────────────────────────────────
REM  Default: run all tests EXCEPT network/slow (fast, offline)
REM  Pass --network to include PyPI + YouTube live checks.

set PYTEST_ARGS=-m "not network and not slow" --tb=short -v
set "COV_ARGS="

for %%A in (%*) do (
    if /I "%%A"=="--network" (
        set "PYTEST_ARGS=--tb=short -v"
        echo [*] Network mode: PyPI + YouTube live tests INCLUDED.
        echo.
    )
    if /I "%%A"=="--cov" (
        set "COV_ARGS=--cov=downloader --cov-report=term-missing"
        echo [*] Coverage mode: HTML + terminal report enabled.
        echo.
    )
)

REM ── Run pytest ────────────────────────────────────────────────────────────
echo [*] Running tests ...
echo.
pytest %PYTEST_ARGS% %COV_ARGS%
set EXIT_CODE=%ERRORLEVEL%

REM ── Summary ───────────────────────────────────────────────────────────────
echo.
echo ========================================
if %EXIT_CODE% EQU 0 (
    echo  RESULT: ALL TESTS PASSED  ✓
) else (
    echo  RESULT: SOME TESTS FAILED  ✗
    echo  Review the output above for details.
)
echo ========================================
echo.

pause
exit /b %EXIT_CODE%
