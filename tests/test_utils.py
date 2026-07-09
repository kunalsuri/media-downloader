"""
test_utils.py — Unit tests for downloader/utils.py.

All functions here are pure (no I/O, no network), so no mocking is required.
Every test runs in milliseconds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from downloader.utils import (
    build_output_path,
    detect_platform,
    format_filesize,
    sanitize_filename,
    validate_url,
)


# ===========================================================================
# detect_platform
# ===========================================================================


class TestDetectPlatform:
    """detect_platform returns 'youtube', 'instagram', or None."""

    # ── YouTube variants ────────────────────────────────────────────────────

    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/abcDEF123-_",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/v/dQw4w9WgXcQ",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
    ])
    def test_youtube_urls(self, url: str) -> None:
        assert detect_platform(url) == "youtube", f"Expected 'youtube' for {url}"

    # ── Instagram variants ──────────────────────────────────────────────────

    @pytest.mark.parametrize("url", [
        "https://www.instagram.com/p/ABC123/",
        "https://www.instagram.com/reel/ABC123/",
        "https://www.instagram.com/tv/ABC123/",
        "https://www.instagram.com/stories/username/1234567890/",
        # Tracking query strings that Instagram adds to shared links
        "https://www.instagram.com/reel/ABC123/?igsh=xyz",
        "https://www.instagram.com/p/ABC123/?utm_source=ig_web_copy_link",
    ])
    def test_instagram_urls(self, url: str) -> None:
        assert detect_platform(url) == "instagram", f"Expected 'instagram' for {url}"

    # ── Unrecognised / edge cases ───────────────────────────────────────────

    @pytest.mark.parametrize("url", [
        "https://vimeo.com/123456789",
        "https://tiktok.com/@user/video/123",
        "https://example.com/video.mp4",
        "not-a-url-at-all",
    ])
    def test_unknown_urls_return_none(self, url: str) -> None:
        assert detect_platform(url) is None

    def test_empty_string_returns_none(self) -> None:
        assert detect_platform("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert detect_platform("   ") is None


# ===========================================================================
# validate_url
# ===========================================================================


class TestValidateUrl:
    """validate_url returns (bool, str) — True for supported URLs."""

    def test_valid_youtube_url(self) -> None:
        ok, msg = validate_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert ok is True
        assert msg == ""

    def test_valid_instagram_reel(self) -> None:
        ok, msg = validate_url("https://www.instagram.com/reel/ABC123/")
        assert ok is True
        assert msg == ""

    def test_valid_youtu_be_shortlink(self) -> None:
        ok, msg = validate_url("https://youtu.be/dQw4w9WgXcQ")
        assert ok is True

    def test_empty_string_invalid(self) -> None:
        ok, msg = validate_url("")
        assert ok is False
        assert "Please enter" in msg

    def test_whitespace_only_invalid(self) -> None:
        ok, msg = validate_url("   ")
        assert ok is False

    def test_unsupported_scheme_ftp(self) -> None:
        ok, msg = validate_url("ftp://example.com/video.mp4")
        assert ok is False
        assert "ftp" in msg.lower() or "scheme" in msg.lower()

    def test_unsupported_scheme_file(self) -> None:
        ok, msg = validate_url("file:///C:/Users/video.mp4")
        assert ok is False

    def test_unknown_domain_invalid(self) -> None:
        ok, msg = validate_url("https://vimeo.com/123456789")
        assert ok is False
        assert "youtube" in msg.lower() or "instagram" in msg.lower()

    def test_no_host_invalid(self) -> None:
        ok, msg = validate_url("just-some-text")
        assert ok is False

    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.instagram.com/p/ABC123/",
        "https://www.instagram.com/reel/TestReel/",
    ])
    def test_valid_urls_return_empty_message(self, url: str) -> None:
        ok, msg = validate_url(url)
        assert ok is True
        assert msg == ""


# ===========================================================================
# sanitize_filename
# ===========================================================================


class TestSanitizeFilename:
    """sanitize_filename strips illegal characters and normalises the result."""

    def test_normal_string_unchanged(self) -> None:
        assert sanitize_filename("My Cool Video") == "My Cool Video"

    def test_strips_windows_illegal_chars(self) -> None:
        result = sanitize_filename('video:<>:"/\\|?*title')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_collapses_whitespace_runs(self) -> None:
        result = sanitize_filename("My   Video   Title")
        assert "  " not in result  # no double spaces

    def test_strips_leading_trailing_dots(self) -> None:
        result = sanitize_filename("...video title...")
        assert not result.startswith(".")
        assert not result.endswith(".")

    def test_truncates_at_max_length(self) -> None:
        long_name = "A" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_empty_string_returns_download(self) -> None:
        assert sanitize_filename("") == "download"

    def test_only_illegal_chars_returns_download(self) -> None:
        # All illegal chars stripped → empty → falls back to "download"
        assert sanitize_filename('<>:"/\\|?*') == "download"

    def test_unicode_preserved(self) -> None:
        # Accented characters must survive sanitisation
        result = sanitize_filename("Ünkodéd Títle")
        assert "nkod" in result  # core characters survive

    def test_custom_max_length(self) -> None:
        result = sanitize_filename("A" * 50, max_length=20)
        assert len(result) <= 20

    def test_control_chars_stripped(self) -> None:
        result = sanitize_filename("video\x00title\x1f")
        assert "\x00" not in result
        assert "\x1f" not in result


# ===========================================================================
# build_output_path
# ===========================================================================


class TestBuildOutputPath:
    """build_output_path returns a unique, sanitised path under the directory."""

    def test_returns_path_in_directory(self, tmp_path: Path) -> None:
        p = build_output_path(tmp_path, "My Video", "mp4")
        assert p.parent == tmp_path

    def test_correct_extension(self, tmp_path: Path) -> None:
        p = build_output_path(tmp_path, "My Video", "mp4")
        assert p.suffix == ".mp4"

    def test_extension_leading_dot_stripped(self, tmp_path: Path) -> None:
        p = build_output_path(tmp_path, "My Video", ".mp4")
        assert p.suffix == ".mp4"
        assert not p.stem.endswith(".")  # no double dot in stem

    def test_no_collision_fresh_directory(self, tmp_path: Path) -> None:
        p = build_output_path(tmp_path, "My Video", "mp4")
        assert p.name == "My Video.mp4"

    def test_collision_appends_counter(self, tmp_path: Path) -> None:
        # Create the first file so a collision exists
        (tmp_path / "My Video.mp4").write_bytes(b"")
        second = build_output_path(tmp_path, "My Video", "mp4")
        assert second.name == "My Video (2).mp4"

    def test_multiple_collisions(self, tmp_path: Path) -> None:
        (tmp_path / "clip.mp4").write_bytes(b"")
        (tmp_path / "clip (2).mp4").write_bytes(b"")
        third = build_output_path(tmp_path, "clip", "mp4")
        assert third.name == "clip (3).mp4"

    def test_creates_missing_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested"
        p = build_output_path(nested, "file", "mp3")
        assert nested.exists()
        assert p.parent == nested

    def test_empty_extension_no_trailing_dot(self, tmp_path: Path) -> None:
        p1 = build_output_path(tmp_path, "My Dir", "")
        assert p1.name == "My Dir"
        p1.mkdir()
        
        p2 = build_output_path(tmp_path, "My Dir", "")
        assert p2.name == "My Dir (2)"


# ===========================================================================
# format_filesize
# ===========================================================================


class TestFormatFilesize:
    """format_filesize converts raw byte counts to human-readable strings."""

    def test_none_returns_unknown(self) -> None:
        assert format_filesize(None) == "Unknown size"

    def test_negative_returns_unknown(self) -> None:
        assert format_filesize(-1) == "Unknown size"

    def test_zero_bytes(self) -> None:
        assert format_filesize(0) == "0.0 B"

    def test_bytes(self) -> None:
        assert format_filesize(512) == "512.0 B"

    def test_kilobytes(self) -> None:
        assert format_filesize(1024) == "1.0 KB"

    def test_megabytes(self) -> None:
        result = format_filesize(1024 * 1024)
        assert result == "1.0 MB"

    def test_fractional_megabytes(self) -> None:
        result = format_filesize(int(1.5 * 1024 * 1024))
        assert result == "1.5 MB"

    def test_gigabytes(self) -> None:
        result = format_filesize(1024 ** 3)
        assert result == "1.0 GB"

    def test_two_gib(self) -> None:
        result = format_filesize(2 * 1024 ** 3)
        assert result == "2.0 GB"
