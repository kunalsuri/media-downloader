"""
conftest.py — shared pytest fixtures for the media-downloader test suite.

Fixtures are automatically available in every test module without an explicit
import — pytest discovers them via this file's location in the tests/ package.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """A fresh temporary directory used as the downloader output directory."""
    d = tmp_path / "downloads"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Canonical mock yt-dlp info dicts
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_yt_info() -> dict:
    """Minimal yt-dlp ``info`` dict that looks like a YouTube video response."""
    return {
        "title": "Test YouTube Video",
        "uploader": "Test Channel",
        "channel": "Test Channel",
        "duration": 180,
        "view_count": 50_000,
        "thumbnail": "https://img.youtube.com/vi/testID/maxresdefault.jpg",
        "description": "A test video description.",
        "webpage_url": "https://www.youtube.com/watch?v=testID",
        "formats": [
            {"vcodec": "avc1", "format_note": "1080p", "ext": "mp4"},
            {"vcodec": "avc1", "format_note": "720p",  "ext": "mp4"},
            {"vcodec": "none", "format_note": "audio", "ext": "m4a"},  # audio-only
        ],
    }


@pytest.fixture
def sample_ig_info() -> dict:
    """Minimal yt-dlp ``info`` dict that looks like an Instagram Reel response."""
    return {
        "title": "Instagram Reel Title",
        "uploader": "instagram_user",
        "channel": "instagram_user",
        "creator": "instagram_user",
        "duration": 30,
        "view_count": 10_000,
        "like_count": 500,
        "thumbnail": "https://cdninstagram.com/test_thumb.jpg",
        "description": "A test reel. #test",
        "webpage_url": "https://www.instagram.com/reel/TestReelID/",
        "formats": [{"vcodec": "avc1", "ext": "mp4"}],
    }


@pytest.fixture
def sample_ig_carousel_info() -> dict:
    """yt-dlp ``info`` dict for an Instagram carousel (playlist type)."""
    return {
        "_type": "playlist",
        "title": "Carousel Post",
        "entries": [
            {
                "title": "Carousel Video Item",
                "uploader": "carousel_user",
                "duration": 15,
                "view_count": 2_000,
                "thumbnail": "https://cdninstagram.com/1.jpg",
                "description": "First carousel item",
                "webpage_url": "https://www.instagram.com/p/TestCarousel/",
                "vcodec": "avc1",
                "formats": [{"vcodec": "avc1", "ext": "mp4"}],
            },
            {
                "title": "Carousel Image Item",
                "uploader": "carousel_user",
                "vcodec": "none",  # image-only entry
                "formats": [],
            },
        ],
    }


@pytest.fixture
def sample_ig_image_only_carousel() -> dict:
    """yt-dlp playlist where ALL entries are images (no video stream)."""
    return {
        "_type": "playlist",
        "title": "Image-Only Carousel",
        "entries": [
            {"title": "Image 1", "vcodec": "none"},
            {"title": "Image 2", "vcodec": None},
        ],
    }


# ---------------------------------------------------------------------------
# YoutubeDL context-manager mock helper
# ---------------------------------------------------------------------------


def make_ydl_mock(return_value: dict | None = None, side_effect=None) -> MagicMock:
    """
    Return a MagicMock that behaves like ``yt_dlp.YoutubeDL`` used as a
    context manager::

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

    Pass ``return_value`` to control what ``extract_info`` returns.
    Pass ``side_effect`` (an exception class or instance) to make it raise.
    """
    instance = MagicMock()
    if side_effect is not None:
        instance.extract_info.side_effect = side_effect
    else:
        instance.extract_info.return_value = return_value

    # Context manager protocol
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=instance)
    cm.__exit__ = MagicMock(return_value=False)
    return cm
