"""
youtube.py – YouTube download logic powered by yt-dlp.

Key features
------------
* Supports MP4 (best-quality video + audio merged) and MP3 (audio-only) modes.
* Real-time progress reporting via a callback hook.
* Automatic ffmpeg detection and graceful fallback messages.
* Handles unavailable videos, geo-restrictions, copyright blocks, network
  errors, and invalid URLs with clear, user-friendly messages.
* Filename sanitisation + duplicate prevention via utils.build_output_path.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yt_dlp  # type: ignore[import]

from .utils import build_output_path, sanitize_filename

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# FIX: Hard cap on download size (2 GiB) to prevent disk exhaustion and
# avoid loading enormous files into memory.  Users who genuinely need larger
# files can raise this constant or remove the limit.
_MAX_FILESIZE_BYTES: int = 2 * 1024 * 1024 * 1024  # 2 GiB

# FIX: Network socket timeout (seconds) for all yt-dlp operations.  Without
# this, a slow or unresponsive server will hang the Streamlit process
# indefinitely, making the entire app unresponsive.
_SOCKET_TIMEOUT_SECONDS: int = 30


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class VideoInfo:
    """Metadata returned by :meth:`YoutubeDownloader.get_info`."""

    title: str
    uploader: str
    duration_seconds: int
    view_count: int
    thumbnail_url: str
    description: str
    webpage_url: str
    formats_available: list[str] = field(default_factory=list)

    @property
    def duration_str(self) -> str:
        """Return duration as ``HH:MM:SS`` or ``MM:SS``."""
        total = int(self.duration_seconds or 0)
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


@dataclass
class DownloadResult:
    """Outcome of a :meth:`YoutubeDownloader.download` call."""

    success: bool
    file_path: Path | None = None
    error_message: str = ""
    file_size_bytes: int | None = None


# ---------------------------------------------------------------------------
# Progress hook
# ---------------------------------------------------------------------------


def _make_progress_hook(callback: Callable[[dict], None] | None):
    """Wrap *callback* in a yt-dlp progress hook."""

    def hook(d: dict) -> None:
        if callback is not None:
            callback(d)

    return hook


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

_ERROR_HINTS: list[tuple[str, str]] = [
    ("Video unavailable", "This video is unavailable (it may have been removed or made private)."),
    ("Private video", "This video is private and cannot be downloaded."),
    ("This video has been removed", "The video has been removed by the uploader."),
    ("copyright", "This video is blocked due to a copyright claim."),
    ("geo", "This video is not available in your region."),
    ("Sign in", "This video requires authentication and cannot be downloaded."),
    ("HTTP Error 403", "Access was denied (HTTP 403). The video may be restricted."),
    ("HTTP Error 404", "The video was not found (HTTP 404). Please check the URL."),
    ("Unable to download", "Network error: unable to reach YouTube. Please check your connection."),
    ("No video formats found", "No downloadable formats were found for this video."),
    ("larger than max-filesize", f"The file exceeds the maximum allowed size of {_MAX_FILESIZE_BYTES // (1024 ** 3)} GiB."),
]


def _friendly_error(raw: str) -> str:
    """Map a raw yt-dlp exception message to a user-friendly string."""
    for keyword, message in _ERROR_HINTS:
        if keyword.lower() in raw.lower():
            return message
    return f"Download failed: {raw}"


# ---------------------------------------------------------------------------
# Downloader class
# ---------------------------------------------------------------------------


class YoutubeDownloader:
    """
    High-level wrapper around *yt-dlp* for downloading YouTube content.

    Parameters
    ----------
    output_dir:
        Directory where finished files are saved.  Defaults to ``downloads/``
        in the current working directory.
    ffmpeg_location:
        Optional path to the ffmpeg binary.  If *None* the system PATH is
        searched automatically.
    """

    def __init__(
        self,
        output_dir: str | Path = "downloads",
        ffmpeg_location: str | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Detect ffmpeg once at construction time
        self._ffmpeg_path: str | None = ffmpeg_location or shutil.which("ffmpeg")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def ffmpeg_available(self) -> bool:
        """``True`` when ffmpeg is found on the system."""
        return self._ffmpeg_path is not None

    def get_info(self, url: str) -> VideoInfo:
        """
        Fetch metadata for *url* without downloading any media.

        Raises
        ------
        ValueError
            When the video is unavailable, geo-restricted, or the URL is
            otherwise unresolvable.
        """
        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            # FIX: Enforce a socket-level timeout so a slow/hung server
            # cannot block the Streamlit process indefinitely.
            "socket_timeout": _SOCKET_TIMEOUT_SECONDS,
        }
        if self._ffmpeg_path:
            opts["ffmpeg_location"] = self._ffmpeg_path

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as exc:
            raise ValueError(_friendly_error(str(exc))) from exc
        except Exception as exc:
            raise ValueError(f"Could not retrieve video information: {exc}") from exc

        if info is None:
            raise ValueError("No information returned for this URL.")

        formats = [
            f.get("format_note") or f.get("ext") or "?"
            for f in (info.get("formats") or [])
            if f.get("vcodec") != "none"
        ]

        return VideoInfo(
            title=info.get("title") or "Untitled",
            uploader=info.get("uploader") or info.get("channel") or "Unknown",
            duration_seconds=int(info.get("duration") or 0),
            view_count=int(info.get("view_count") or 0),
            thumbnail_url=info.get("thumbnail") or "",
            description=info.get("description") or "",
            webpage_url=info.get("webpage_url") or url,
            formats_available=list(dict.fromkeys(formats)),  # deduplicate, preserve order
        )

    def download(
        self,
        url: str,
        mode: str = "mp4",
        quality: str = "best",
        progress_callback: Callable[[dict], None] | None = None,
    ) -> DownloadResult:
        """
        Download *url* as MP4 or MP3.

        Parameters
        ----------
        url:
            YouTube video URL.
        mode:
            ``"mp4"`` for video+audio, ``"mp3"`` for audio-only.
        quality:
            One of ``"best"``, ``"1080p"``, ``"720p"``, ``"480p"``,
            ``"360p"``, ``"audio_best"``.
        progress_callback:
            Optional callable receiving yt-dlp progress-hook dicts.

        Returns
        -------
        DownloadResult
        """
        mode = mode.lower().strip()
        if mode not in ("mp4", "mp3"):
            return DownloadResult(success=False, error_message=f"Unsupported mode: '{mode}'.")

        # yt-dlp writes to a temporary directory; we move the file afterwards
        # so that the final filename is deterministic and sanitised.
        with tempfile.TemporaryDirectory(prefix="yt_tmp_") as tmp_dir:
            tmp_template = os.path.join(tmp_dir, "%(title)s.%(ext)s")
            opts = self._build_options(mode, quality, tmp_template, progress_callback)

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
            except yt_dlp.utils.DownloadError as exc:
                return DownloadResult(success=False, error_message=_friendly_error(str(exc)))
            except Exception as exc:
                return DownloadResult(success=False, error_message=f"Unexpected error: {exc}")

            if info is None:
                return DownloadResult(success=False, error_message="Download returned no data.")

            title = info.get("title") or "download"
            expected_ext = "mp3" if mode == "mp3" else "mp4"

            # Find the downloaded file in the temp directory
            tmp_file = self._find_output(tmp_dir, expected_ext)
            if tmp_file is None:
                # Fallback: any file in the temp dir
                all_files = list(Path(tmp_dir).iterdir())
                tmp_file = all_files[0] if all_files else None

            if tmp_file is None or not tmp_file.exists():
                return DownloadResult(
                    success=False,
                    error_message="The download completed but no output file was found.",
                )

            # Move to final output path with a sanitised, collision-free name
            final_path = build_output_path(self.output_dir, title, expected_ext)
            shutil.move(str(tmp_file), str(final_path))

        # FIX: Remove the redundant .exists() guard — shutil.move() above
        # would have raised OSError if the move failed, so final_path is
        # guaranteed to exist at this point.
        file_size = final_path.stat().st_size
        return DownloadResult(
            success=True,
            file_path=final_path,
            file_size_bytes=file_size,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_options(
        self,
        mode: str,
        quality: str,
        outtmpl: str,
        progress_callback: Callable[[dict], None] | None,
    ) -> dict:
        """Build yt-dlp option dict for the requested mode and quality."""
        opts: dict = {
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [_make_progress_hook(progress_callback)],
            # FIX: Enforce socket timeout to prevent indefinite hangs during
            # the actual download (separate from the get_info timeout).
            "socket_timeout": _SOCKET_TIMEOUT_SECONDS,
            # FIX: Reject files larger than _MAX_FILESIZE_BYTES before
            # downloading them, preventing disk exhaustion and the subsequent
            # attempt to read the entire file into RAM.
            "max_filesize": _MAX_FILESIZE_BYTES,
        }

        if self._ffmpeg_path:
            opts["ffmpeg_location"] = self._ffmpeg_path

        if mode == "mp3":
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        else:
            # Video mode – pick format string based on quality preference
            fmt = self._video_format_string(quality)
            opts["format"] = fmt
            opts["merge_output_format"] = "mp4"
            if self._ffmpeg_path:
                opts["postprocessors"] = [
                    {
                        "key": "FFmpegVideoConvertor",
                        "preferedformat": "mp4",
                    }
                ]

        return opts

    @staticmethod
    def _video_format_string(quality: str) -> str:
        """Translate a friendly quality label to a yt-dlp format selector."""
        mapping = {
            "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best",
            "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best",
            "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best",
            "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best",
        }
        return mapping.get(quality, mapping["best"])

    @staticmethod
    def _find_output(directory: str, preferred_ext: str) -> Path | None:
        """
        Search *directory* for a file with *preferred_ext*, then any file.
        Returns ``None`` when the directory is empty.

        FIX: Single-pass implementation — collects all files in one iteration,
        preferring the exact extension match, falling back to the first file
        found.  The original two-pass approach iterated the directory twice.
        """
        dir_path = Path(directory)
        fallback: Path | None = None
        for p in dir_path.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lstrip(".").lower() == preferred_ext.lower():
                return p          # exact match — return immediately
            if fallback is None:
                fallback = p      # remember first non-matching file
        return fallback
