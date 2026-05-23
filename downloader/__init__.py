"""
media-downloader – downloader package

Public surface
--------------
YoutubeDownloader   – download YouTube videos/audio
InstagramDownloader – download Instagram posts/reels/IGTV/stories
validate_url        – validate a YouTube or Instagram URL
sanitize_filename   – make a string safe for use as a filename
detect_platform     – identify "youtube" or "instagram" from a URL
"""

from .instagram import InstagramDownloader
from .youtube import YoutubeDownloader
from .utils import detect_platform, sanitize_filename, validate_url

__all__ = [
    "YoutubeDownloader",
    "InstagramDownloader",
    "validate_url",
    "sanitize_filename",
    "detect_platform",
    # Note: downloader.updater is intentionally NOT imported here.
    # It is infrastructure (not a user-facing download class) and importing it
    # at package load time would cause a RuntimeWarning when the module is also
    # invoked as a script via  python -m downloader.updater.
    # Import it directly:  from downloader.updater import get_version_info
]
