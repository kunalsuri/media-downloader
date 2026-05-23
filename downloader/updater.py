"""
updater.py — yt-dlp version checker and automatic updater.

Responsibilities
----------------
* Query PyPI for the latest yt-dlp release.
* Compare with the currently installed version.
* Install the new release (via pip) and update requirements.txt when called
  from the CLI / launch scripts (before the app starts).
* Provide a lightweight check-only function for use inside the running app
  (app.py uses this via @st.cache_resource to show an update banner).

Entry points
------------
CLI / launch scripts (install + update)::

    python -m downloader.updater          # auto-update, verbose output
    python -m downloader.updater --check  # check only, exits 2 if update available

Python API::

    from downloader.updater import get_version_info, run_full_update

    # Lightweight — just check (never raises, safe inside Streamlit)
    info = get_version_info()
    if info.update_available:
        print(f"Update available: {info.installed} → {info.latest}")

    # Full — check + install + update requirements.txt (use before app starts)
    result = run_full_update(verbose=True)
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent
_REQUIREMENTS_FILE = _ROOT / "requirements.txt"
_PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class VersionInfo:
    """
    Result of a version check against PyPI.

    Attributes
    ----------
    installed:
        The yt-dlp version currently installed in this Python environment.
    latest:
        The latest yt-dlp version on PyPI.  ``None`` when PyPI was unreachable.
    update_available:
        ``True`` when ``latest`` is newer than ``installed``.
    network_error:
        Human-readable error string when PyPI could not be reached.
        ``None`` on a successful check.
    """

    installed: str
    latest: Optional[str]
    update_available: bool
    network_error: Optional[str] = None


@dataclass
class UpdateResult:
    """
    Result of a full check-and-install pass (see :func:`run_full_update`).

    Attributes
    ----------
    version_info:
        The version comparison performed before any install attempt.
    was_updated:
        ``True`` when a newer version was successfully installed.
    requirements_updated:
        ``True`` when requirements.txt was rewritten with the new pin.
    error:
        Human-readable error when the install or requirements update failed.
    """

    version_info: VersionInfo
    was_updated: bool = False
    requirements_updated: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def get_installed_version() -> str:
    """Return the installed yt-dlp version string (e.g. ``'2026.3.17'``)."""
    return importlib.metadata.version("yt-dlp")


def get_pypi_version(timeout: int = 8) -> str:
    """
    Fetch the latest yt-dlp release version from PyPI.

    Parameters
    ----------
    timeout:
        HTTP request timeout in seconds.

    Raises
    ------
    urllib.error.URLError
        When PyPI is unreachable (e.g. no internet connection).
    """
    req = urllib.request.Request(
        _PYPI_URL,
        headers={"User-Agent": "media-downloader-updater/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())["info"]["version"]


def _version_tuple(v: str) -> tuple[int, ...]:
    """Convert ``'2026.3.17'`` → ``(2026, 3, 17)`` for comparison."""
    return tuple(int(x) for x in re.findall(r"\d+", v))


# ---------------------------------------------------------------------------
# Public API — version check (safe, never raises, usable inside Streamlit)
# ---------------------------------------------------------------------------


def get_version_info(timeout: int = 8) -> VersionInfo:
    """
    Compare the installed yt-dlp version against the latest on PyPI.

    This function **never raises** — network errors are captured in
    :attr:`VersionInfo.network_error`.  It is therefore safe to call from
    within a running Streamlit app.

    Parameters
    ----------
    timeout:
        HTTP request timeout in seconds.  Keep this short (≤ 8 s) to avoid
        blocking the Streamlit startup.

    Returns
    -------
    VersionInfo
        Always returns a populated object; ``latest`` is ``None`` when offline.
    """
    installed = get_installed_version()
    try:
        latest = get_pypi_version(timeout=timeout)
    except (urllib.error.URLError, OSError, Exception) as exc:
        return VersionInfo(
            installed=installed,
            latest=None,
            update_available=False,
            network_error=str(exc),
        )

    update_available = _version_tuple(latest) > _version_tuple(installed)
    return VersionInfo(
        installed=installed,
        latest=latest,
        update_available=update_available,
    )


# ---------------------------------------------------------------------------
# Public API — full update (install + requirements.txt, use before app starts)
# ---------------------------------------------------------------------------


def install_update(version: str) -> tuple[bool, str]:
    """
    Install a specific yt-dlp version via pip in a subprocess.

    Parameters
    ----------
    version:
        The exact version to install (e.g. ``'2026.3.17'``).

    Returns
    -------
    (success, error_message)
        ``success`` is ``True`` when pip exited 0.
        ``error_message`` is empty on success, or pip's stderr on failure.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", f"yt-dlp=={version}", "--quiet"],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return True, ""
    return False, proc.stderr.strip() or f"pip exited {proc.returncode}"


def update_requirements_file(new_version: str) -> bool:
    """
    Rewrite the ``yt-dlp>=X.Y.Z`` pin in requirements.txt.

    Parameters
    ----------
    new_version:
        The new minimum version string (e.g. ``'2026.3.17'``).

    Returns
    -------
    bool
        ``True`` when the file was actually changed; ``False`` when the pin
        was already up to date or the file does not exist.
    """
    if not _REQUIREMENTS_FILE.exists():
        return False

    original = _REQUIREMENTS_FILE.read_text(encoding="utf-8")
    updated = re.sub(
        r"(yt[-_]dlp\s*>=\s*)[\d.]+",
        rf"\g<1>{new_version}",
        original,
        flags=re.IGNORECASE,
    )
    if updated == original:
        return False

    _REQUIREMENTS_FILE.write_text(updated, encoding="utf-8")
    return True


def run_full_update(verbose: bool = False) -> UpdateResult:
    """
    Full check-and-update pass: query PyPI → install if newer → update requirements.txt.

    This is intended to be called **before** the Streamlit server starts
    (e.g. from ``launch.bat`` / ``launch.sh``) so the updated yt-dlp is
    active for the entire session.

    Parameters
    ----------
    verbose:
        When ``True``, prints progress to stdout — useful for terminal launchers.

    Returns
    -------
    UpdateResult
    """
    def _log(msg: str) -> None:
        if verbose:
            print(msg)

    _log("[yt-dlp] Checking for updates ...")

    info = get_version_info(timeout=10)
    result = UpdateResult(version_info=info)

    if info.network_error:
        _log(f"[yt-dlp] Could not reach PyPI: {info.network_error}")
        _log("[yt-dlp] Skipping update — using installed version.")
        return result

    _log(f"[yt-dlp] Installed : {info.installed}")
    _log(f"[yt-dlp] Latest    : {info.latest}")

    if not info.update_available:
        _log("[yt-dlp] Already up to date. ✓")
        return result

    # ── A newer version is available — install it ──────────────────────────
    _log(f"[yt-dlp] Updating {info.installed} → {info.latest} ...")

    assert info.latest is not None  # guaranteed when update_available is True
    success, err = install_update(info.latest)

    if not success:
        result.error = f"pip install failed: {err}"
        _log(f"[yt-dlp] Update FAILED. {err}")
        return result

    _log(f"[yt-dlp] ✓ yt-dlp updated to {info.latest}")

    # ── Rewrite requirements.txt ───────────────────────────────────────────
    changed = update_requirements_file(info.latest)
    result.was_updated = True
    result.requirements_updated = changed

    if changed:
        _log(f"[yt-dlp] ✓ requirements.txt updated  (yt-dlp>={info.latest})")
    else:
        _log("[yt-dlp]   (requirements.txt pin unchanged — no '>=' pattern found)")

    return result


# ---------------------------------------------------------------------------
# CLI entry point — called by launch.bat / launch.sh
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys as _sys

    check_only = "--check" in _sys.argv

    if check_only:
        # Exit 0 = up to date, Exit 2 = update available, Exit 1 = error
        _info = get_version_info()
        if _info.network_error:
            print(f"[yt-dlp] Offline / error: {_info.network_error}")
            _sys.exit(0)  # treat as "no update needed" when offline
        if _info.update_available:
            print(
                f"[yt-dlp] Update available: {_info.installed} → {_info.latest}"
            )
            _sys.exit(2)
        print(f"[yt-dlp] Up to date ({_info.installed}).")
        _sys.exit(0)
    else:
        _result = run_full_update(verbose=True)
        _sys.exit(0 if _result.error is None else 1)
