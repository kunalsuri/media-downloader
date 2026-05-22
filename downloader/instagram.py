"""
instagram.py – Instagram download logic powered by yt-dlp.

Key features
------------
* Subclasses YoutubeDownloader — inherits ffmpeg detection, output_dir setup,
  _find_output, and DownloadResult/VideoInfo data structures.
* Supports MP4 (video) and MP3 (audio-only) modes.
* Handles public Posts, Reels, IGTV, and Stories.
* Carousel/album posts: first video item is extracted via noplaylist=True.
* Friendly error messages for private accounts, login walls, image-only posts.
* Enforces the same socket timeout and file-size cap as YoutubeDownloader.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable

import yt_dlp  # type: ignore[import]

from .utils import build_output_path
from .youtube import DownloadResult, VideoInfo, YoutubeDownloader

# ---------------------------------------------------------------------------
# Constants  (same values as in youtube.py — kept local to avoid importing
# private module-level names from a peer module)
# ---------------------------------------------------------------------------

_MAX_FILESIZE_BYTES: int = 2 * 1024 * 1024 * 1024   # 2 GiB
_SOCKET_TIMEOUT_SECONDS: int = 30


# ---------------------------------------------------------------------------
# Progress hook  (trivial wrapper; kept local for the same reason as above)
# ---------------------------------------------------------------------------

def _make_progress_hook(callback: Callable[[dict], None] | None):
    """Wrap *callback* in a yt-dlp progress hook."""

    def hook(d: dict) -> None:
        if callback is not None:
            callback(d)

    return hook


# ---------------------------------------------------------------------------
# Error mapping — Instagram-specific messages
# ---------------------------------------------------------------------------

_INSTAGRAM_ERROR_HINTS: list[tuple[str, str]] = [
    (
        "login required",
        "This content requires Instagram login — only public posts can be downloaded.",
    ),
    ("Private", "This Instagram account is private."),
    (
        "not found",
        "The Instagram post was not found — it may have been deleted or made private.",
    ),
    (
        "HTTP Error 401",
        "Authentication required (HTTP 401). The content may be private.",
    ),
    (
        "HTTP Error 403",
        "Access was denied (HTTP 403). The post may be age-restricted or private.",
    ),
    (
        "HTTP Error 404",
        "Post not found (HTTP 404). Please check the URL.",
    ),
    (
        "Unable to download",
        "Network error: unable to reach Instagram. Please check your connection.",
    ),
    (
        "No video formats found",
        "No downloadable video found — this post may contain images only.",
    ),
    (
        "larger than max-filesize",
        f"The file exceeds the maximum allowed size of "
        f"{_MAX_FILESIZE_BYTES // (1024 ** 3)} GiB.",
    ),
    (
        "Incomplete data",
        "Instagram returned incomplete data — the post may be temporarily unavailable.",
    ),
    (
        "checkpoint",
        "Instagram requires account verification to access this content.",
    ),
    (
        "rate-limit",
        "Instagram has temporarily rate-limited this request. Try again later.",
    ),
]


def _friendly_instagram_error(raw: str) -> str:
    """Map a raw yt-dlp exception message to a user-friendly Instagram string."""
    for keyword, message in _INSTAGRAM_ERROR_HINTS:
        if keyword.lower() in raw.lower():
            return message
    return f"Download failed: {raw}"


# ---------------------------------------------------------------------------
# Downloader class
# ---------------------------------------------------------------------------


class InstagramDownloader(YoutubeDownloader):
    """
    Instagram media downloader.

    Extends :class:`YoutubeDownloader` with Instagram-specific metadata
    extraction, download options, and error messages.  All other
    infrastructure — ``output_dir``, ``ffmpeg_available``, ``_find_output``,
    and the ``VideoInfo`` / ``DownloadResult`` data classes — is inherited.

    Parameters
    ----------
    output_dir :
        Directory where finished files are saved.
    ffmpeg_location :
        Optional explicit path to the ffmpeg binary.  System PATH is used
        if *None*.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_info(self, url: str) -> VideoInfo:
        """
        Fetch metadata for an Instagram *url* without downloading media.

        For carousel posts (multiple images/videos), only the first video
        item's metadata is returned.

        Raises
        ------
        ValueError
            When the content is unavailable, private, or the URL is
            otherwise unresolvable.
        """
        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            # noplaylist=True so carousels yield a single representative item
            "noplaylist": True,
            "socket_timeout": _SOCKET_TIMEOUT_SECONDS,
        }
        if self._ffmpeg_path:
            opts["ffmpeg_location"] = self._ffmpeg_path

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as exc:
            raise ValueError(_friendly_instagram_error(str(exc))) from exc
        except Exception as exc:
            raise ValueError(
                f"Could not retrieve Instagram content: {exc}"
            ) from exc

        if info is None:
            raise ValueError("No information returned for this URL.")

        # Flatten playlist/carousel — use the first concrete entry
        if info.get("_type") == "playlist":
            entries = [e for e in (info.get("entries") or []) if e]
            if entries:
                info = entries[0]

        return VideoInfo(
            title=(
                info.get("title")
                or info.get("description")
                or "Instagram Post"
            ),
            uploader=(
                info.get("uploader")
                or info.get("channel")
                or info.get("creator")
                or "Instagram"
            ),
            duration_seconds=int(info.get("duration") or 0),
            # Instagram Reels expose view_count; image posts expose like_count
            view_count=int(
                info.get("view_count") or info.get("like_count") or 0
            ),
            thumbnail_url=info.get("thumbnail") or "",
            description=info.get("description") or "",
            webpage_url=info.get("webpage_url") or url,
            formats_available=[],  # Instagram offers no user-selectable quality
        )

    def download(
        self,
        url: str,
        mode: str = "mp4",
        quality: str = "best",  # noqa: ARG002  — accepted for API parity, unused
        progress_callback: Callable[[dict], None] | None = None,
    ) -> DownloadResult:
        """
        Download Instagram content as MP4 or MP3.

        Parameters
        ----------
        url :
            Instagram post / reel / IGTV / story URL.
        mode :
            ``"mp4"`` for video, ``"mp3"`` for audio-only extraction.
        quality :
            Accepted for API parity with :class:`YoutubeDownloader` but
            ignored — Instagram serves a single native quality stream.
        progress_callback :
            Optional callable receiving yt-dlp progress-hook dicts.

        Returns
        -------
        DownloadResult
        """
        mode = mode.lower().strip()
        if mode not in ("mp4", "mp3"):
            return DownloadResult(
                success=False,
                error_message=f"Unsupported mode: '{mode}'.",
            )

        with tempfile.TemporaryDirectory(prefix="ig_tmp_") as tmp_dir:
            tmp_template = os.path.join(tmp_dir, "%(title)s.%(ext)s")
            opts = self._build_instagram_options(
                mode, tmp_template, progress_callback
            )

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
            except yt_dlp.utils.DownloadError as exc:
                return DownloadResult(
                    success=False,
                    error_message=_friendly_instagram_error(str(exc)),
                )
            except Exception as exc:
                return DownloadResult(
                    success=False,
                    error_message=f"Unexpected error: {exc}",
                )

            if info is None:
                return DownloadResult(
                    success=False,
                    error_message="Download returned no data.",
                )

            # Resolve a usable title for the output filename
            if info.get("_type") == "playlist":
                entries = [e for e in (info.get("entries") or []) if e]
                title_info = entries[0] if entries else info
            else:
                title_info = info

            title = (
                title_info.get("title")
                or title_info.get("description")
                or "instagram_download"
            )
            expected_ext = "mp3" if mode == "mp3" else "mp4"

            # Locate the downloaded file in the temp directory
            tmp_file = self._find_output(tmp_dir, expected_ext)
            if tmp_file is None:
                all_files = list(Path(tmp_dir).iterdir())
                tmp_file = all_files[0] if all_files else None

            if tmp_file is None or not tmp_file.exists():
                return DownloadResult(
                    success=False,
                    error_message=(
                        "Download completed but no output file was found."
                    ),
                )

            # Move to final sanitised, collision-free path
            final_path = build_output_path(self.output_dir, title, expected_ext)
            shutil.move(str(tmp_file), str(final_path))

        file_size = final_path.stat().st_size
        return DownloadResult(
            success=True,
            file_path=final_path,
            file_size_bytes=file_size,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_instagram_options(
        self,
        mode: str,
        outtmpl: str,
        progress_callback: Callable[[dict], None] | None,
    ) -> dict:
        """Build yt-dlp option dict for Instagram downloads."""
        opts: dict = {
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [_make_progress_hook(progress_callback)],
            "socket_timeout": _SOCKET_TIMEOUT_SECONDS,
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
            # Prefer native MP4; fall back through merge → any best stream
            opts["format"] = (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                "/bestvideo+bestaudio"
                "/best[ext=mp4]"
                "/best"
            )
            opts["merge_output_format"] = "mp4"
            if self._ffmpeg_path:
                opts["postprocessors"] = [
                    {
                        "key": "FFmpegVideoConvertor",
                        "preferedformat": "mp4",
                    }
                ]

        return opts
