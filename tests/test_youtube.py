"""
test_youtube.py — Tests for downloader/youtube.py.

yt-dlp is fully mocked; no network access is required.  Temporary files are
created on disk via pytest's tmp_path fixture to exercise the file-move logic
realistically.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yt_dlp

from downloader.youtube import (
    DownloadResult,
    VideoInfo,
    YoutubeDownloader,
    _friendly_error,
    _make_progress_hook,
)
from tests.conftest import make_ydl_mock


# ===========================================================================
# VideoInfo dataclass
# ===========================================================================


class TestVideoInfo:
    """VideoInfo.duration_str formats seconds into HH:MM:SS / MM:SS."""

    @pytest.mark.parametrize("seconds,expected", [
        (0,     "0:00"),
        (59,    "0:59"),
        (60,    "1:00"),
        (90,    "1:30"),
        (3599,  "59:59"),
        (3600,  "1:00:00"),
        (3661,  "1:01:01"),
        (36_000, "10:00:00"),
    ])
    def test_duration_str(self, seconds: int, expected: str) -> None:
        info = VideoInfo(
            title="t", uploader="u", duration_seconds=seconds,
            view_count=0, thumbnail_url="", description="", webpage_url="",
        )
        assert info.duration_str == expected

    def test_duration_str_none_treated_as_zero(self) -> None:
        info = VideoInfo(
            title="t", uploader="u", duration_seconds=None,  # type: ignore[arg-type]
            view_count=0, thumbnail_url="", description="", webpage_url="",
        )
        # Should not raise; treats None as 0
        assert info.duration_str == "0:00"

    def test_formats_available_defaults_to_empty_list(self) -> None:
        info = VideoInfo(
            title="t", uploader="u", duration_seconds=10,
            view_count=0, thumbnail_url="", description="", webpage_url="",
        )
        assert info.formats_available == []


# ===========================================================================
# DownloadResult dataclass
# ===========================================================================


class TestDownloadResult:
    def test_failure_result_defaults(self) -> None:
        r = DownloadResult(success=False, error_message="oops")
        assert r.file_path is None
        assert r.file_size_bytes is None

    def test_success_result(self, tmp_path: Path) -> None:
        p = tmp_path / "video.mp4"
        r = DownloadResult(success=True, file_path=p, file_size_bytes=1024)
        assert r.success is True
        assert r.file_path == p
        assert r.file_size_bytes == 1024


# ===========================================================================
# _friendly_error
# ===========================================================================


class TestFriendlyError:
    """_friendly_error maps raw yt-dlp messages to user-friendly strings."""

    @pytest.mark.parametrize("raw,must_contain", [
        ("Video unavailable: this was deleted",    "unavailable"),
        ("Private video",                          "private"),
        ("This video has been removed",            "removed"),
        ("copyright claim made by XYZ",            "copyright"),
        ("geo restriction applies in your country","region"),
        ("Sign in to confirm your age",            "authentication"),
        ("HTTP Error 403: Forbidden",              "403"),
        ("HTTP Error 404: Not Found",              "404"),
        ("Unable to download webpage",             "network"),
        ("No video formats found",                 "format"),
        ("larger than max-filesize limit",         "GiB"),
    ])
    def test_known_keywords_produce_friendly_message(
        self, raw: str, must_contain: str
    ) -> None:
        result = _friendly_error(raw)
        assert must_contain.lower() in result.lower(), (
            f"Expected '{must_contain}' in _friendly_error({raw!r}), got: {result!r}"
        )

    def test_unknown_message_includes_original(self) -> None:
        result = _friendly_error("Some completely unknown yt-dlp error xyz999")
        assert "xyz999" in result

    def test_case_insensitive_matching(self) -> None:
        result = _friendly_error("VIDEO UNAVAILABLE")
        assert "unavailable" in result.lower()


# ===========================================================================
# _make_progress_hook
# ===========================================================================


class TestMakeProgressHook:
    def test_callback_is_called_with_event(self) -> None:
        events: list[dict] = []
        hook = _make_progress_hook(events.append)
        hook({"status": "downloading", "downloaded_bytes": 512})
        assert events == [{"status": "downloading", "downloaded_bytes": 512}]

    def test_none_callback_does_not_raise(self) -> None:
        hook = _make_progress_hook(None)
        hook({"status": "finished"})  # must not raise


# ===========================================================================
# YoutubeDownloader._find_output  (static method)
# ===========================================================================


class TestFindOutput:
    """_find_output scans a directory for a file with the preferred extension."""

    def test_finds_preferred_extension(self, tmp_path: Path) -> None:
        (tmp_path / "video.mp4").write_bytes(b"data")
        (tmp_path / "video.webm").write_bytes(b"data")
        result = YoutubeDownloader._find_output(str(tmp_path), "mp4")
        assert result is not None
        assert result.suffix == ".mp4"

    def test_falls_back_to_any_file_when_no_match(self, tmp_path: Path) -> None:
        (tmp_path / "video.webm").write_bytes(b"data")
        result = YoutubeDownloader._find_output(str(tmp_path), "mp4")
        assert result is not None
        assert result.name == "video.webm"

    def test_returns_none_on_empty_directory(self, tmp_path: Path) -> None:
        assert YoutubeDownloader._find_output(str(tmp_path), "mp4") is None

    def test_ignores_subdirectories(self, tmp_path: Path) -> None:
        (tmp_path / "subdir").mkdir()
        (tmp_path / "video.mp4").write_bytes(b"data")
        result = YoutubeDownloader._find_output(str(tmp_path), "mp4")
        assert result is not None
        assert result.is_file()

    def test_case_insensitive_extension_match(self, tmp_path: Path) -> None:
        (tmp_path / "video.MP4").write_bytes(b"data")
        result = YoutubeDownloader._find_output(str(tmp_path), "mp4")
        assert result is not None


# ===========================================================================
# YoutubeDownloader._video_format_string  (static method)
# ===========================================================================


class TestVideoFormatString:
    @pytest.mark.parametrize("quality", ["best", "1080p", "720p", "480p", "360p"])
    def test_known_quality_labels(self, quality: str) -> None:
        fmt = YoutubeDownloader._video_format_string(quality)
        assert isinstance(fmt, str)
        assert len(fmt) > 0

    def test_unknown_quality_falls_back_to_best(self) -> None:
        best = YoutubeDownloader._video_format_string("best")
        unknown = YoutubeDownloader._video_format_string("999p")
        assert unknown == best

    def test_1080p_contains_height_filter(self) -> None:
        fmt = YoutubeDownloader._video_format_string("1080p")
        assert "1080" in fmt

    def test_360p_contains_height_filter(self) -> None:
        fmt = YoutubeDownloader._video_format_string("360p")
        assert "360" in fmt


# ===========================================================================
# YoutubeDownloader — initialisation
# ===========================================================================


class TestYoutubeDownloaderInit:
    def test_creates_output_directory(self, tmp_path: Path) -> None:
        out = tmp_path / "new_dir"
        assert not out.exists()
        YoutubeDownloader(output_dir=out)
        assert out.is_dir()

    def test_ffmpeg_available_when_found(self, tmp_path: Path) -> None:
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            d = YoutubeDownloader(output_dir=tmp_path)
        assert d.ffmpeg_available is True

    def test_ffmpeg_not_available_when_missing(self, tmp_path: Path) -> None:
        with patch("shutil.which", return_value=None):
            d = YoutubeDownloader(output_dir=tmp_path, ffmpeg_location=None)
        assert d.ffmpeg_available is False


# ===========================================================================
# YoutubeDownloader.get_info
# ===========================================================================


class TestYoutubeDownloaderGetInfo:
    """get_info fetches metadata without downloading any media."""

    URL = "https://www.youtube.com/watch?v=testID"

    def _make_downloader(self, tmp_path: Path) -> YoutubeDownloader:
        return YoutubeDownloader(output_dir=tmp_path)

    def test_returns_video_info_on_success(
        self, tmp_path: Path, sample_yt_info: dict
    ) -> None:
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(sample_yt_info)):
            info = self._make_downloader(tmp_path).get_info(self.URL)

        assert isinstance(info, VideoInfo)
        assert info.title == sample_yt_info["title"]
        assert info.uploader == sample_yt_info["uploader"]
        assert info.duration_seconds == sample_yt_info["duration"]
        assert info.view_count == sample_yt_info["view_count"]
        assert info.thumbnail_url == sample_yt_info["thumbnail"]
        assert info.webpage_url == sample_yt_info["webpage_url"]

    def test_filters_audio_only_formats(
        self, tmp_path: Path, sample_yt_info: dict
    ) -> None:
        """Formats where vcodec is 'none' (audio-only) must be excluded."""
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(sample_yt_info)):
            info = self._make_downloader(tmp_path).get_info(self.URL)

        # sample_yt_info has two video formats and one audio-only; only 2 survive
        assert len(info.formats_available) == 2

    def test_raises_value_error_on_download_error(self, tmp_path: Path) -> None:
        err = yt_dlp.utils.DownloadError("Video unavailable")
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(side_effect=err)):
            with pytest.raises(ValueError, match="unavailable"):
                self._make_downloader(tmp_path).get_info(self.URL)

    def test_raises_value_error_on_none_info(self, tmp_path: Path) -> None:
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(return_value=None)):
            with pytest.raises(ValueError, match="No information"):
                self._make_downloader(tmp_path).get_info(self.URL)

    def test_raises_value_error_on_unexpected_exception(self, tmp_path: Path) -> None:
        with patch(
            "yt_dlp.YoutubeDL",
            return_value=make_ydl_mock(side_effect=RuntimeError("weird error")),
        ):
            with pytest.raises(ValueError, match="Could not retrieve"):
                self._make_downloader(tmp_path).get_info(self.URL)

    def test_falls_back_to_channel_when_uploader_missing(self, tmp_path: Path) -> None:
        info_dict = {
            "title": "Video", "uploader": None, "channel": "My Channel",
            "duration": 60, "view_count": 0, "thumbnail": "",
            "description": "", "webpage_url": self.URL, "formats": [],
        }
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(info_dict)):
            info = self._make_downloader(tmp_path).get_info(self.URL)
        assert info.uploader == "My Channel"


# ===========================================================================
# YoutubeDownloader.download
# ===========================================================================


class TestYoutubeDownloaderDownload:
    """download() handles success paths, invalid modes, and yt-dlp errors."""

    URL = "https://www.youtube.com/watch?v=testID"
    FAKE_CONTENT = b"fake video content" * 100  # 1 800 bytes

    def _setup_fake_tmp(self, tmp_path: Path, filename: str) -> Path:
        """Create a fake downloaded file in a temp sub-directory."""
        fake_tmp = tmp_path / "fake_yt_tmp"
        fake_tmp.mkdir()
        (fake_tmp / filename).write_bytes(self.FAKE_CONTENT)
        return fake_tmp

    def test_invalid_mode_returns_failure(self, tmp_path: Path) -> None:
        d = YoutubeDownloader(output_dir=tmp_path)
        result = d.download(self.URL, mode="avi")
        assert result.success is False
        assert "avi" in result.error_message.lower()

    def test_mp4_download_success(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        fake_tmp = self._setup_fake_tmp(tmp_path, "Test Video.mp4")
        mock_info = {"title": "Test Video"}

        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(mock_info)), \
             patch("tempfile.TemporaryDirectory") as MockTmpDir:
            _configure_tmp_mock(MockTmpDir, str(fake_tmp))
            result = YoutubeDownloader(output_dir=output_dir).download(
                self.URL, mode="mp4"
            )

        assert result.success is True
        assert result.file_path is not None
        assert result.file_path.suffix == ".mp4"
        assert result.file_size_bytes == len(self.FAKE_CONTENT)

    def test_mp3_download_success(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        fake_tmp = self._setup_fake_tmp(tmp_path, "Test Audio.mp3")
        mock_info = {"title": "Test Audio"}

        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(mock_info)), \
             patch("tempfile.TemporaryDirectory") as MockTmpDir:
            _configure_tmp_mock(MockTmpDir, str(fake_tmp))
            result = YoutubeDownloader(output_dir=output_dir).download(
                self.URL, mode="mp3"
            )

        assert result.success is True
        assert result.file_path.suffix == ".mp3"

    def test_download_error_returns_failure(self, tmp_path: Path) -> None:
        err = yt_dlp.utils.DownloadError("HTTP Error 403: Forbidden")
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(side_effect=err)):
            result = YoutubeDownloader(output_dir=tmp_path).download(self.URL)
        assert result.success is False
        assert "403" in result.error_message or "denied" in result.error_message.lower()

    def test_unexpected_exception_returns_failure(self, tmp_path: Path) -> None:
        err = RuntimeError("disk full")
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(side_effect=err)):
            result = YoutubeDownloader(output_dir=tmp_path).download(self.URL)
        assert result.success is False
        assert "disk full" in result.error_message

    def test_none_info_returns_failure(self, tmp_path: Path) -> None:
        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(return_value=None)):
            result = YoutubeDownloader(output_dir=tmp_path).download(self.URL)
        assert result.success is False
        assert "no data" in result.error_message.lower()

    def test_no_output_file_returns_failure(self, tmp_path: Path) -> None:
        """When yt-dlp claims success but leaves no file, we get a clear failure."""
        empty_tmp = tmp_path / "empty_tmp"
        empty_tmp.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        mock_info = {"title": "Ghost Video"}

        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(mock_info)), \
             patch("tempfile.TemporaryDirectory") as MockTmpDir:
            _configure_tmp_mock(MockTmpDir, str(empty_tmp))
            result = YoutubeDownloader(output_dir=output_dir).download(self.URL)

        assert result.success is False
        assert "no output file" in result.error_message.lower()

    def test_mode_is_case_insensitive(self, tmp_path: Path) -> None:
        """Mode should be normalised to lowercase before checking."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        fake_tmp = self._setup_fake_tmp(tmp_path, "Video.mp4")
        mock_info = {"title": "Video"}

        with patch("yt_dlp.YoutubeDL", return_value=make_ydl_mock(mock_info)), \
             patch("tempfile.TemporaryDirectory") as MockTmpDir:
            _configure_tmp_mock(MockTmpDir, str(fake_tmp))
            result = YoutubeDownloader(output_dir=output_dir).download(
                self.URL, mode="MP4"
            )

        assert result.success is True


# ===========================================================================
# Private helper for TemporaryDirectory mocking
# ===========================================================================


def _configure_tmp_mock(mock_cls: MagicMock, path: str) -> None:
    """Configure a patched TemporaryDirectory to return *path* from __enter__."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=path)
    ctx.__exit__ = MagicMock(return_value=False)
    mock_cls.return_value = ctx
