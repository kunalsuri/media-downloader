"""
test_version_compat.py — Version and API-compatibility tests for yt-dlp.

Why this file exists
--------------------
YouTube periodically changes its internal API (JS player, signature ciphers,
etc.).  When that happens, yt-dlp releases a fix, but projects that pin an
old minimum version in requirements.txt can silently break.

These tests detect that situation in three layers:

Layer 1 – Static / always runs (no network)
    * yt-dlp is importable.
    * All classes and yt-dlp options used by *this project* still exist.
    * The installed version satisfies the requirements.txt minimum.
    * downloader.updater public API is intact.

Layer 2 – Network (auto-skipped when offline)
    * A newer yt-dlp is available on PyPI → emits a warning so the
      requirements.txt pin can be updated.
    * requirements.txt minimum is compared to the PyPI latest.

Layer 3 – Network + slow
    * A live YouTube extraction smoke-test confirms that yt-dlp can
      actually talk to YouTube right now.

Usage
-----
Run everything (including network tests when online):
    pytest tests/test_version_compat.py

Run static-only (guaranteed offline):
    pytest tests/test_version_compat.py -m "not network"

Run just the smoke test:
    pytest tests/test_version_compat.py -m slow
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest
import yt_dlp

# ---------------------------------------------------------------------------
# Use downloader.updater for all version logic — keeps test code DRY and
# validates the updater module itself.
# ---------------------------------------------------------------------------
from downloader.updater import (
    UpdateResult,
    VersionInfo,
    get_installed_version,
    get_pypi_version,
    get_version_info,
    install_update,
    run_full_update,
    update_requirements_file,
)

ROOT = Path(__file__).parent.parent
REQUIREMENTS_FILE = ROOT / "requirements.txt"


# ---------------------------------------------------------------------------
# Private helper shared by tests
# ---------------------------------------------------------------------------

def _parse_requirements_min_version() -> str | None:
    """Return the yt-dlp minimum version from requirements.txt, or None."""
    if not REQUIREMENTS_FILE.exists():
        return None
    for line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        m = re.search(r"yt[-_]dlp\s*>=\s*([\d.]+)", line, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v))


# ===========================================================================
# Layer 1 — Static checks (no network required)
# ===========================================================================


class TestYtDlpInstallation:
    """yt-dlp must be importable and expose well-formed version metadata."""

    def test_package_is_importable(self) -> None:
        import yt_dlp as _  # noqa: F401

    def test_installed_version_format(self) -> None:
        """Version must follow yt-dlp's YYYY.M.D date-based scheme."""
        version = get_installed_version()
        assert re.match(r"\d{4}\.\d+\.\d+", version), (
            f"Unexpected yt-dlp version format: {version!r}. "
            "Expected YYYY.M.D (e.g. '2026.3.17')."
        )


class TestUpdaterModule:
    """downloader.updater public API must be intact and behave correctly."""

    def test_get_installed_version_returns_string(self) -> None:
        v = get_installed_version()
        assert isinstance(v, str) and len(v) > 0

    def test_get_version_info_never_raises(self) -> None:
        """get_version_info() must not raise even when the network is mocked away."""
        import urllib.error
        with patch("downloader.updater.get_pypi_version",
                   side_effect=urllib.error.URLError("no network")):
            info = get_version_info()
        assert isinstance(info, VersionInfo)
        assert info.installed == get_installed_version()
        assert info.latest is None
        assert info.network_error is not None

    def test_get_version_info_up_to_date(self) -> None:
        """When PyPI returns the same version, update_available must be False."""
        current = get_installed_version()
        with patch("downloader.updater.get_pypi_version", return_value=current):
            info = get_version_info()
        assert info.update_available is False
        assert info.latest == current

    def test_get_version_info_update_detected(self) -> None:
        """When PyPI returns a newer version, update_available must be True."""
        with patch("downloader.updater.get_pypi_version",
                   return_value="9999.12.31"):
            info = get_version_info()
        assert info.update_available is True
        assert info.latest == "9999.12.31"

    def test_update_requirements_file_rewrites_pin(self, tmp_path: Path) -> None:
        """update_requirements_file must rewrite the yt-dlp>= pin."""
        req = tmp_path / "requirements.txt"
        req.write_text("streamlit>=1.35.0\nyt-dlp>=2024.5.1\nrequests>=2.31.0\n")

        # Monkey-patch the module-level path
        import downloader.updater as _updater
        original = _updater._REQUIREMENTS_FILE
        _updater._REQUIREMENTS_FILE = req
        try:
            changed = update_requirements_file("2026.3.17")
        finally:
            _updater._REQUIREMENTS_FILE = original

        assert changed is True
        content = req.read_text()
        assert "yt-dlp>=2026.3.17" in content
        assert "2024.5.1" not in content

    def test_update_requirements_file_no_change_when_already_current(
        self, tmp_path: Path
    ) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("yt-dlp>=2026.3.17\n")

        import downloader.updater as _updater
        original = _updater._REQUIREMENTS_FILE
        _updater._REQUIREMENTS_FILE = req
        try:
            changed = update_requirements_file("2026.3.17")
        finally:
            _updater._REQUIREMENTS_FILE = original

        assert changed is False

    def test_run_full_update_skips_when_up_to_date(self) -> None:
        current = get_installed_version()
        with patch("downloader.updater.get_pypi_version", return_value=current):
            result = run_full_update(verbose=False)
        assert result.was_updated is False
        assert result.error is None
        assert result.version_info.update_available is False

    def test_run_full_update_skips_gracefully_when_offline(self) -> None:
        import urllib.error
        with patch("downloader.updater.get_pypi_version",
                   side_effect=urllib.error.URLError("offline")):
            result = run_full_update(verbose=False)
        assert result.was_updated is False
        assert result.error is None
        assert result.version_info.network_error is not None


class TestYtDlpApiSurface:
    """
    Verify every yt-dlp symbol used by this project still exists.

    When yt-dlp removes or renames a class/exception, these tests fail
    immediately — before any user-facing code runs.
    """

    def test_YoutubeDL_class_exists(self) -> None:
        assert hasattr(yt_dlp, "YoutubeDL"), (
            "yt_dlp.YoutubeDL is missing — check the yt-dlp changelog."
        )

    def test_DownloadError_exists(self) -> None:
        assert hasattr(yt_dlp.utils, "DownloadError"), (
            "yt_dlp.utils.DownloadError is missing."
        )

    def test_ExtractorError_exists(self) -> None:
        assert hasattr(yt_dlp.utils, "ExtractorError"), (
            "yt_dlp.utils.ExtractorError is missing."
        )

    def test_YoutubeDL_accepts_project_options(self) -> None:
        """Instantiate YoutubeDL with every option this project passes."""
        info_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 30,
        }
        download_opts = {
            **info_opts,
            "outtmpl": "/tmp/%(title)s.%(ext)s",
            "max_filesize": 2 * 1024 * 1024 * 1024,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "progress_hooks": [],
        }
        with yt_dlp.YoutubeDL(info_opts):
            pass
        with yt_dlp.YoutubeDL(download_opts):
            pass

    def test_youtube_extractor_is_registered(self) -> None:
        try:
            from yt_dlp.extractor import _ALL_CLASSES  # type: ignore[import]
        except ImportError:
            pytest.skip("yt_dlp.extractor._ALL_CLASSES not available in this version")

        ie_names = {
            cls.IE_NAME
            for cls in _ALL_CLASSES
            if hasattr(cls, "IE_NAME") and cls.IE_NAME
        }
        assert "youtube" in ie_names, (
            f"YouTube extractor not found. Sample names: {sorted(ie_names)[:10]}"
        )

    def test_instagram_extractor_is_registered(self) -> None:
        try:
            from yt_dlp.extractor import _ALL_CLASSES  # type: ignore[import]
        except ImportError:
            pytest.skip("yt_dlp.extractor._ALL_CLASSES not available in this version")

        ie_names = {
            cls.IE_NAME.lower()
            for cls in _ALL_CLASSES
            if hasattr(cls, "IE_NAME") and cls.IE_NAME
        }
        assert any("instagram" in n for n in ie_names), (
            "Instagram extractor not found — yt-dlp may have removed Instagram support."
        )


class TestRequirementsFile:
    """requirements.txt must be present and correctly pin yt-dlp."""

    def test_requirements_file_exists(self) -> None:
        assert REQUIREMENTS_FILE.exists()

    def test_ytdlp_is_pinned_with_minimum_version(self) -> None:
        content = REQUIREMENTS_FILE.read_text(encoding="utf-8")
        assert re.search(r"yt[-_]dlp\s*>=\s*\d", content, re.IGNORECASE), (
            "requirements.txt must contain a 'yt-dlp>=<version>' pin."
        )

    def test_installed_version_satisfies_minimum(self) -> None:
        min_ver = _parse_requirements_min_version()
        if min_ver is None:
            pytest.skip("Could not parse yt-dlp minimum version from requirements.txt")

        installed = get_installed_version()
        assert _version_tuple(installed) >= _version_tuple(min_ver), (
            f"\n  Installed yt-dlp : {installed}\n"
            f"  Required minimum : {min_ver}\n"
            f"Fix: pip install 'yt-dlp>={min_ver}'"
        )


# ===========================================================================
# Layer 2 — Network: PyPI freshness (auto-skipped when offline)
# ===========================================================================


@pytest.mark.network
class TestVersionFreshness:
    """
    Compare installed yt-dlp against the latest PyPI release.

    These tests emit warnings (not failures) when a newer version is available
    — flagging a stale requirements.txt without breaking CI.
    """

    def _fetch_latest(self) -> str:
        try:
            return get_pypi_version(timeout=10)
        except Exception as exc:
            pytest.skip(f"PyPI unreachable: {exc}")

    def test_pypi_returns_valid_version_string(self) -> None:
        latest = self._fetch_latest()
        assert re.match(r"\d{4}\.\d+\.\d+", latest), (
            f"Unexpected PyPI version format: {latest!r}"
        )

    def test_warn_if_newer_version_available(self) -> None:
        """WARN (not fail) when a newer yt-dlp is on PyPI."""
        latest = self._fetch_latest()
        installed = get_installed_version()

        if _version_tuple(installed) < _version_tuple(latest):
            warnings.warn(
                f"\n\nyt-dlp version notice:\n"
                f"  Installed   : {installed}\n"
                f"  PyPI latest : {latest}\n"
                f"\n"
                f"Update via launch.bat / launch.sh (auto-installs on next launch),\n"
                f"or manually:  pip install --upgrade yt-dlp\n",
                UserWarning,
                stacklevel=2,
            )

    def test_requirements_minimum_not_far_behind_pypi(self) -> None:
        """WARN when requirements.txt minimum is 3+ months behind PyPI latest."""
        latest = self._fetch_latest()
        min_ver = _parse_requirements_min_version()
        if min_ver is None:
            pytest.skip("Could not parse yt-dlp minimum version from requirements.txt")

        latest_t = _version_tuple(latest)
        min_t = _version_tuple(min_ver)

        if min_t < latest_t:
            latest_year, latest_month = latest_t[0], latest_t[1]
            min_year, min_month = min_t[0], min_t[1]
            months_behind = (
                (latest_year - min_year) * 12 + (latest_month - min_month)
            )
            if months_behind >= 3:
                warnings.warn(
                    f"\n\nrequirements.txt pin is stale:\n"
                    f"  Current pin : yt-dlp>={min_ver}\n"
                    f"  PyPI latest : {latest}  (~{months_behind} months behind)\n"
                    f"\n"
                    f"launch.bat / launch.sh will auto-update yt-dlp on the next run.\n"
                    f"After that, update the pin: yt-dlp>={latest}\n",
                    UserWarning,
                    stacklevel=2,
                )


# ===========================================================================
# Layer 3 — Network + slow: live YouTube extraction smoke test
# ===========================================================================


@pytest.mark.network
@pytest.mark.slow
class TestYouTubeLiveSmoke:
    """
    Confirms yt-dlp can actually talk to YouTube right now.

    Catches the scenario where yt-dlp is installed but its extractor is
    broken by a recent YouTube API change.  If this test fails, updating
    yt-dlp (via launch.bat) is the first fix to try.

    Video: Rick Astley — Never Gonna Give You Up (dQw4w9WgXcQ)
    (Chosen as one of the most stable, least-likely-to-disappear videos.)
    """

    CANARY_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    CANARY_ID = "dQw4w9WgXcQ"

    def test_extract_info_from_youtube(self) -> None:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 20,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.CANARY_URL, download=False)
        except yt_dlp.utils.DownloadError as exc:
            installed = get_installed_version()
            pytest.fail(
                f"\n\nYouTube extraction FAILED — yt-dlp may be outdated.\n"
                f"  Installed yt-dlp : {installed}\n"
                f"  Error            : {exc}\n"
                f"\n"
                f"Fix: restart the app via launch.bat to auto-update yt-dlp.\n"
            )

        assert info is not None
        assert info.get("id") == self.CANARY_ID
        assert "title" in info
        assert "formats" in info
        assert len(info.get("formats", [])) > 0

    def test_youtube_format_dict_has_expected_keys(self) -> None:
        opts = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "noplaylist": True, "socket_timeout": 20,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.CANARY_URL, download=False)
        except Exception as exc:
            pytest.skip(f"Could not reach YouTube: {exc}")

        formats = info.get("formats", [])
        assert len(formats) > 0
        missing = {"ext", "vcodec"} - set(formats[0].keys())
        assert not missing, (
            f"Format dict missing keys: {missing}. "
            f"YouTube or yt-dlp may have changed the format dict structure."
        )
