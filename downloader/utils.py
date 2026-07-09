"""
utils.py – shared helper functions for the media-downloader package.

Responsibilities
----------------
* URL validation (YouTube + Instagram patterns + generic HTTP check)
* Platform detection from a URL
* Filename sanitisation to prevent path-traversal and filesystem errors
* Human-readable file-size formatting
* Determining a safe, unique output path (prevents duplicate overwrites)
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

# Patterns that indicate a URL is likely a valid YouTube resource
_YOUTUBE_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=[\w-]+",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+",
    r"(?:https?://)?youtu\.be/[\w-]+",
    r"(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+",
    r"(?:https?://)?(?:www\.)?youtube\.com/v/[\w-]+",
    r"(?:https?://)?(?:music\.)?youtube\.com/watch\?.*v=[\w-]+",
]

# Patterns that indicate a URL is likely a valid Instagram resource.
# Covers: Posts (/p/), Reels (/reel/), IGTV (/tv/), Stories (/stories/).
# The optional (?:[?#]\S*)? suffix accepts tracking/sharing query strings
# such as ?igsh=… or ?utm_source=… that appear in links copied from Instagram.
_INSTAGRAM_PATTERNS = [
    r"(?:https?://)?(?:www\.)?instagram\.com/p/[\w-]+/?(?:[?#]\S*)?",
    r"(?:https?://)?(?:www\.)?instagram\.com/reel/[\w-]+/?(?:[?#]\S*)?",
    r"(?:https?://)?(?:www\.)?instagram\.com/tv/[\w-]+/?(?:[?#]\S*)?",
    r"(?:https?://)?(?:www\.)?instagram\.com/stories/[\w.\-]+/\d+/?(?:[?#]\S*)?",
]

_COMPILED_YOUTUBE = [re.compile(p, re.IGNORECASE) for p in _YOUTUBE_PATTERNS]
_COMPILED_INSTAGRAM = [re.compile(p, re.IGNORECASE) for p in _INSTAGRAM_PATTERNS]


def detect_platform(url: str) -> str | None:
    """
    Identify the platform from *url*.

    Returns
    -------
    ``"youtube"``, ``"instagram"``, or ``None`` when the URL is not
    recognised as either platform.
    """
    if not url or not url.strip():
        return None
    url = url.strip()
    for pattern in _COMPILED_YOUTUBE:
        if pattern.match(url):
            return "youtube"
    for pattern in _COMPILED_INSTAGRAM:
        if pattern.match(url):
            return "instagram"
    return None


def validate_url(url: str) -> tuple[bool, str]:
    """
    Validate that *url* is a well-formed YouTube or Instagram URL.

    Returns
    -------
    (is_valid: bool, message: str)
        ``is_valid`` is True when the URL passes all checks.
        ``message`` carries a human-readable description of the problem when
        ``is_valid`` is False, or an empty string when valid.
    """
    if not url or not url.strip():
        return False, "Please enter a URL."

    url = url.strip()

    # Basic scheme / netloc check
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        if not parsed.netloc:
            return False, "The URL does not appear to be valid (missing host)."
    except ValueError:
        return False, "The URL could not be parsed."

    # Reject obviously non-HTTP schemes (file://, ftp://, …)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https", ""):
        return False, (
            f"Unsupported URL scheme: '{scheme}'. "
            "Only HTTP/HTTPS URLs are accepted."
        )

    # Must match a known YouTube or Instagram pattern
    if detect_platform(url) is not None:
        return True, ""

    return False, (
        "The URL does not appear to be a supported YouTube or Instagram link. "
        "Paste a youtube.com/watch?v=…, youtu.be/…, "
        "instagram.com/p/…, or instagram.com/reel/… URL."
    )


# ---------------------------------------------------------------------------
# Filename sanitisation
# ---------------------------------------------------------------------------

# Characters that are illegal on Windows, macOS, or Linux filesystems
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Collapse runs of whitespace / underscores / hyphens
_WHITESPACE = re.compile(r"[\s_]+")


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """
    Return a filesystem-safe version of *name*.

    Steps
    -----
    1. Normalise Unicode to NFC form.
    2. Strip illegal characters.
    3. Replace whitespace runs with a single space.
    4. Strip leading/trailing dots and spaces (Windows reserved).
    5. Truncate to *max_length* characters.
    6. Fall back to ``"download"`` when the result is empty.
    """
    # Normalise Unicode (keeps accented characters)
    name = unicodedata.normalize("NFC", name)

    # Remove illegal characters
    name = _ILLEGAL_CHARS.sub("", name)

    # Collapse whitespace
    name = _WHITESPACE.sub(" ", name).strip()

    # Remove leading/trailing dots and spaces
    name = name.strip(". ")

    # Truncate
    name = name[:max_length]

    return name or "download"


# ---------------------------------------------------------------------------
# Output path helpers
# ---------------------------------------------------------------------------

def build_output_path(directory: str | Path, title: str, extension: str) -> Path:
    """
    Return a :class:`~pathlib.Path` for the output file that does not already
    exist in *directory*.

    If ``<title>.<extension>`` already exists, a numeric suffix is appended:
    ``<title> (2).<extension>``, ``<title> (3).<extension>``, …
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    base = sanitize_filename(title)
    ext = extension.lstrip(".")
    candidate = directory / f"{base}.{ext}" if ext else directory / base

    counter = 2
    while candidate.exists():
        candidate = directory / f"{base} ({counter}).{ext}" if ext else directory / f"{base} ({counter})"
        counter += 1

    return candidate


# ---------------------------------------------------------------------------
# Human-readable helpers
# ---------------------------------------------------------------------------

def format_filesize(size_bytes: int | None) -> str:
    """Return *size_bytes* as a human-readable string (e.g. ``"12.4 MB"``)."""
    if size_bytes is None or size_bytes < 0:
        return "Unknown size"
    # FIX: Use a separate float variable instead of reassigning the typed
    # parameter.  Dividing an int by 1024 produces a float in Python 3, so
    # the original code silently mutated the type of size_bytes each iteration,
    # requiring a '# type: ignore' suppression.
    size: float = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
