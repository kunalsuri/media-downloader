"""
test_instagram.py — Tests for downloader/instagram.py.

yt-dlp is fully mocked; no network access is required.  Tests cover:
* Instagram-specific error message mapping
* Carousel / playlist flattening logic in get_info
* Image-only post detection
* download() success/failure paths
* _build_instagram_options key values
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yt_dlp

from downloader.instagram import (
    InstagramDownloader,
    _friendly_instagram_error,
)
from downloader.youtube import DownloadResult, VideoInfo
from tests.conftest import make_ydl_mock


# ===========================================================================
# _friendly_instagram_error
# ===========================================================================


class TestFriendlyInstagramError:
    """Error messages must be user-friendly and mention Instagram context."""

    @pytest.mark.parametrize("raw,must_contain", [
        ("login required to view this content",     "login"),
        ("Private account cannot be accessed",      "private"),
        ("Post not found or has been deleted",       "not found"),
        ("HTTP Error 401: Unauthorized",             "401"),
        ("HTTP Error 403: Forbidden",                "403"),
        # "not found" appears earlier in _INSTAGRAM_ERROR_HINTS than "HTTP Error 404",
        # so a raw string containing "Not Found" returns the generic "not found" message.
        # Test the 404 keyword independently to avoid the earlier-match short-circuit.
        ("HTTP Error 404: resource gone",           "404"),
        ("Unable to download JSON",                  "network"),
        ("No video formats found in this post",     "video"),
        ("larger than max-filesize restriction",    "GiB"),
        ("Incomplete data returned by server",       "incomplete"),
        ("checkpoint required for this action",     "verification"),
        ("rate-limit exceeded, slow down",           "rate"),
    ])
    def test_known_keywords(self, raw: str, must_contain: str) -> None:
        result = _friendly_instagram_error(raw)
        assert must_contain.lower() in result.lower(), (
            f"Expected '{must_contain}' in _friendly_instagram_error({raw!r}), "
            f"got: {result!r}"
        )

    def test_unknown_message_includes_original(self) -> None:
        result = _friendly_instagram_error("totally unknown error abc999")
        assert "abc999" in result

    def test_case_insensitive_matching(self) -> None:
        result = _friendly_instagram_error("LOGIN REQUIRED")
        assert "login" in result.lower()


# ===========================================================================
# InstagramDownloader — inherits from YoutubeDownloader
# ===========================================================================


class TestInstagramDownloaderInheritance:
    def test_is_subclass_of_youtube_downloader(self) -> None:
        from downloader.youtube import YoutubeDownloader
        assert issubclass(InstagramDownloader, YoutubeDownloader)

    def test_ffmpeg_available_property_inherited(self, tmp_path: Path) -> None:
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            d = InstagramDownloader(output_dir=tmp_path)
        assert d.ffmpeg_available is True

    def test_output_dir_created_on_init(self, tmp_path: Path) -> None:
        out = tmp_path / "ig_out"
        InstagramDownloader(output_dir=out)
        assert out.is_dir()


# ===========================================================================
# InstagramDownloader.get_info
# ===========================================================================


class TestInstagramDownloaderGetInfo:
    URL = "https://www.instagram.com/reel/TestReelID/"

    def _make_downloader(self, tmp_path: Path) -> InstagramDownloader:
        return InstagramDownloader(output_dir=tmp_path)

    def test_returns_video_info_on_success(
        self, tmp_path: Path, sample_ig_info: dict
    ) -> None:
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(sample_ig_info)):
            info = self._make_downloader(tmp_path).get_info(self.URL)

        assert isinstance(info, VideoInfo)
        assert info.title == sample_ig_info["title"]
        assert info.uploader == sample_ig_info["uploader"]
        assert info.duration_seconds == sample_ig_info["duration"]
        assert info.view_count == sample_ig_info["view_count"]
        assert info.thumbnail_url == sample_ig_info["thumbnail"]

    def test_formats_available_is_always_empty(
        self, tmp_path: Path, sample_ig_info: dict
    ) -> None:
        """Instagram has no user-selectable quality — formats_available must be []."""
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(sample_ig_info)):
            info = self._make_downloader(tmp_path).get_info(self.URL)
        assert info.formats_available == []

    def test_carousel_picks_first_video_entry(
        self, tmp_path: Path, sample_ig_carousel_info: dict
    ) -> None:
        """Carousel posts (playlist type) must resolve to the first video entry."""
        with patch(
            "yt_dlp.YoutubeDL",
            return_value=make_ydl_mock(sample_ig_carousel_info),
        ):
            info = self._make_downloader(tmp_path).get_info(self.URL)

        assert info.title == "Carousel Video Item"

    def test_image_only_carousel_raises_value_error(
        self, tmp_path: Path, sample_ig_image_only_carousel: dict
    ) -> None:
        """If a carousel has no video entries, a clear ValueError must be raised."""
        with patch(
            "yt_dlp.YoutubeDL",
            return_value=make_ydl_mock(sample_ig_image_only_carousel),
        ):
            with pytest.raises(ValueError, match="image"):
                self._make_downloader(tmp_path).get_info(self.URL)

    def test_raises_value_error_on_login_required(self, tmp_path: Path) -> None:
        err = yt_dlp.utils.DownloadError("login required")
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(side_effect=err)):
            with pytest.raises(ValueError, match="login"):
                self._make_downloader(tmp_path).get_info(self.URL)

    def test_raises_value_error_on_none_info(self, tmp_path: Path) -> None:
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(return_value=None)):
            with pytest.raises(ValueError, match="No information"):
                self._make_downloader(tmp_path).get_info(self.URL)

    def test_falls_back_to_description_when_no_title(self, tmp_path: Path) -> None:
        info_dict = {
            "title": None,
            "description": "Caption text #reel",
            "uploader": "user",
            "duration": 15, "view_count": 0,
            "thumbnail": "", "webpage_url": self.URL,
        }
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(info_dict)):
            info = self._make_downloader(tmp_path).get_info(self.URL)
        assert info.title == "Caption text #reel"

    def test_uses_like_count_when_no_view_count(self, tmp_path: Path) -> None:
        info_dict = {
            "title": "Post", "uploader": "user",
            "duration": 10, "view_count": None, "like_count": 999,
            "thumbnail": "", "description": "", "webpage_url": self.URL,
        }
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(info_dict)):
            info = self._make_downloader(tmp_path).get_info(self.URL)
        assert info.view_count == 999


# ===========================================================================
# InstagramDownloader.download
# ===========================================================================


class TestInstagramDownloaderDownload:
    URL = "https://www.instagram.com/reel/TestReelID/"
    FAKE_CONTENT = b"fake instagram video" * 50  # 1 000 bytes

    def _setup_fake_tmp(self, tmp_path: Path, filename: str) -> Path:
        fake_tmp = tmp_path / "fake_ig_tmp"
        fake_tmp.mkdir()
        (fake_tmp / filename).write_bytes(self.FAKE_CONTENT)
        return fake_tmp

    def test_invalid_mode_returns_failure(self, tmp_path: Path) -> None:
        result = InstagramDownloader(output_dir=tmp_path).download(
            self.URL, mode="webm"
        )
        assert result.success is False
        assert "webm" in result.error_message.lower()

    def test_mp4_download_success(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        fake_tmp = self._setup_fake_tmp(tmp_path, "reel_title.mp4")
        mock_info = {"title": "reel_title"}

        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(mock_info)), \
             patch("tempfile.TemporaryDirectory") as MockTmpDir:
            _configure_tmp_mock(MockTmpDir, str(fake_tmp))
            result = InstagramDownloader(output_dir=output_dir).download(
                self.URL, mode="mp4"
            )

        assert result.success is True
        assert result.file_path.suffix == ".mp4"
        assert result.file_size_bytes == len(self.FAKE_CONTENT)

    def test_mp3_download_success(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        fake_tmp = self._setup_fake_tmp(tmp_path, "reel_audio.mp3")
        mock_info = {"title": "reel_audio"}

        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(mock_info)), \
             patch("tempfile.TemporaryDirectory") as MockTmpDir:
            _configure_tmp_mock(MockTmpDir, str(fake_tmp))
            result = InstagramDownloader(output_dir=output_dir).download(
                self.URL, mode="mp3"
            )

        assert result.success is True
        assert result.file_path.suffix == ".mp3"

    def test_quality_param_is_accepted_and_ignored(self, tmp_path: Path) -> None:
        """Instagram ignores quality; the param must be accepted for API parity."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        fake_tmp = self._setup_fake_tmp(tmp_path, "vid.mp4")

        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock({"title": "vid"})), \
             patch("tempfile.TemporaryDirectory") as MockTmpDir:
            _configure_tmp_mock(MockTmpDir, str(fake_tmp))
            result = InstagramDownloader(output_dir=output_dir).download(
                self.URL, mode="mp4", quality="1080p"
            )

        assert result.success is True  # quality param must not break anything

    def test_login_required_returns_failure(self, tmp_path: Path) -> None:
        err = yt_dlp.utils.DownloadError("login required")
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(side_effect=err)):
            result = InstagramDownloader(output_dir=tmp_path).download(self.URL)
        assert result.success is False
        assert "login" in result.error_message.lower()

    def test_no_output_file_returns_failure(self, tmp_path: Path) -> None:
        empty_tmp = tmp_path / "empty"
        empty_tmp.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock({"title": "x"})), \
             patch("tempfile.TemporaryDirectory") as MockTmpDir:
            _configure_tmp_mock(MockTmpDir, str(empty_tmp))
            result = InstagramDownloader(output_dir=output_dir).download(self.URL)

        assert result.success is False


# ===========================================================================
# InstagramDownloader._build_instagram_options
# ===========================================================================


class TestBuildInstagramOptions:
    def test_mp4_options_include_format_selector(self, tmp_path: Path) -> None:
        d = InstagramDownloader(output_dir=tmp_path)
        opts = d._build_instagram_options("mp4", "/tmp/%(title)s.%(ext)s", None)
        assert "format" in opts
        assert "mp4" in opts["format"].lower() or "best" in opts["format"].lower()

    def test_mp3_options_include_postprocessor(self, tmp_path: Path) -> None:
        d = InstagramDownloader(output_dir=tmp_path)
        opts = d._build_instagram_options("mp3", "/tmp/%(title)s.%(ext)s", None)
        assert opts.get("format") == "bestaudio/best"
        pp_keys = [p["key"] for p in opts.get("postprocessors", [])]
        assert "FFmpegExtractAudio" in pp_keys

    def test_socket_timeout_and_max_filesize_present(self, tmp_path: Path) -> None:
        d = InstagramDownloader(output_dir=tmp_path)
        opts = d._build_instagram_options("mp4", "/tmp/%(title)s.%(ext)s", None)
        assert "socket_timeout" in opts
        assert "max_filesize" in opts
        assert opts["socket_timeout"] > 0
        assert opts["max_filesize"] > 0

    def test_noplaylist_is_true(self, tmp_path: Path) -> None:
        d = InstagramDownloader(output_dir=tmp_path)
        opts = d._build_instagram_options("mp4", "/tmp/%(title)s.%(ext)s", None)
        assert opts.get("noplaylist") is True


# ===========================================================================
# Private helper for TemporaryDirectory mocking  (same pattern as test_youtube)
# ===========================================================================


def _configure_tmp_mock(mock_cls: MagicMock, path: str) -> None:
    """Configure a patched TemporaryDirectory to return *path* from __enter__."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=path)
    ctx.__exit__ = MagicMock(return_value=False)
    mock_cls.return_value = ctx
