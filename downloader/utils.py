"""
utils.py – shared helper functions for the media-downloader package.

Responsibilities
----------------
* URL validation (YouTube-specific patterns + generic HTTP check)
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

_COMPILED_YOUTUBE = [re.compile(p, re.IGNORECASE) for p in _YOUTUBE_PATTERNS]


def validate_url(url: str) -> tuple[bool, str]:
    """
    Validate that *url* is a well-formed YouTube URL.

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
        return False, f"Unsupported URL scheme: '{scheme}'. Only HTTP/HTTPS URLs are accepted."

    # Must match at least one YouTube pattern
    for pattern in _COMPILED_YOUTUBE:
        if pattern.match(url):
            return True, ""

    return False, (
        "The URL does not appear to be a supported YouTube link. "
        "Please paste a youtube.com/watch?v=… or youtu.be/… URL."
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
    candidate = directory / f"{base}.{ext}"

    counter = 2
    while candidate.exists():
        candidate = directory / f"{base} ({counter}).{ext}"
        counter += 1

    return candidate


# ---------------------------------------------------------------------------
# Human-readable helpers
# ---------------------------------------------------------------------------

def format_filesize(size_bytes: int | None) -> str:
    """Return *size_bytes* as a human-readable string (e.g. ``"12.4 MB"``)."""
    if size_bytes is None or size_bytes < 0:
        return "Unknown size"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} PB"
