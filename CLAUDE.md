# CLAUDE.md — Media Downloader Project Intelligence

This file gives Claude Code (and any AI assistant) fast, accurate context about
this codebase so it can assist efficiently without re-reading every file.

---

## What this project does

A Streamlit web app that downloads YouTube and Instagram media (MP4 video / MP3
audio) using `yt-dlp`. Users paste a URL, choose a format and quality, preview
metadata, and download the file directly to their browser. The app runs locally.

**Supported sources**
- YouTube: videos, Shorts, YouTube Music
- Instagram: Reels, Posts (`/p/`), IGTV (`/tv/`), Stories — public content only

---

## Architecture — layer map

```
app.py                          ← Streamlit UI (sidebar + main area)
    │
    ├── downloader/__init__.py  ← Package exports (all public symbols)
    ├── downloader/youtube.py   ← YoutubeDownloader class (yt-dlp wrapper)
    │       VideoInfo dataclass
    │       DownloadResult dataclass
    │       _friendly_error() — maps raw yt-dlp errors to user messages
    │       _make_progress_hook() — bridges yt-dlp hook → Streamlit progress bar
    ├── downloader/instagram.py ← InstagramDownloader(YoutubeDownloader)
    │       Overrides get_info() — Instagram field mapping, carousel flattening
    │       Overrides download() — Instagram format string + error mapping
    │       _friendly_instagram_error() — Instagram-specific error messages
    └── downloader/utils.py     ← Pure helpers (no Streamlit, no yt-dlp)
            validate_url()      — accepts YouTube OR Instagram URLs
            detect_platform()   — returns "youtube" | "instagram" | None
            sanitize_filename()
            build_output_path()
            format_filesize()
```

### Data flow

```
User pastes URL
  → detect_platform(url)                  # "youtube" | "instagram" | None
  → validate_url(url)                     # downloader/utils.py
  → active_downloader.get_info(url)       # YoutubeDownloader or InstagramDownloader
  → display metadata card in app.py

User clicks Download
  → active_downloader.download(url, mode, quality, progress_callback)
      ↓ yt-dlp writes to tempfile.TemporaryDirectory
      ↓ file moved to DOWNLOADS_DIR via shutil.move
      → DownloadResult(success, file_path, file_size_bytes)
  → st.download_button streams file to browser
```

---

## Key design decisions (with rationale)

### Instagram support (added in feat/instagram-download)
| Decision | Rationale |
|---|---|
| `InstagramDownloader` subclasses `YoutubeDownloader` | Reuses `__init__`, `ffmpeg_available`, `output_dir`, `_find_output` — no duplication |
| `quality` param accepted but ignored for Instagram | Keeps the caller interface uniform; Instagram has no user-selectable quality |
| `noplaylist=True` for Instagram | Carousels are yt-dlp "playlists" — first video item is returned; avoids downloading image albums |
| `detect_platform()` in `utils.py` | Sidebar reads `st.session_state.url_input` before the widget renders; always in sync |
| Two cached downloaders (`yt_downloader`, `ig_downloader`) | Each caches its own `ffmpeg` detection; platform switch is zero-cost |
| Instagram error hints cover login/private/checkpoint/rate-limit | Public Instagram content may still return 403 if rate-limited |

### Security (fixed in PR #4 — merged into main)
| Issue | Fix |
|---|---|
| XSS via metadata in `unsafe_allow_html` | `html.escape()` on all user-controlled fields (applies to Instagram too) |
| Relative `DOWNLOADS_DIR` | `Path(__file__).parent / "downloads"` — absolute, anchored to app.py |
| Hanging on slow network | `"socket_timeout": 30` in all yt-dlp option dicts |
| Disk/RAM exhaustion | `"max_filesize": 2 GiB` in download options |

### Performance (fixed in PR #4)
| Issue | Fix |
|---|---|
| Downloaders created on every click | Cached in `st.session_state.yt_downloader` / `ig_downloader` |
| Entire file in session state as bytes | Store `Path` only; open as stream for download button |
| Redundant `validate_url` call on download | Removed — Download button requires prior Fetch Info |
| Redundant `exists()` after `shutil.move` | Removed — `shutil.move` raises on failure |

### Session state keys
| Key | Type | Purpose |
|---|---|---|
| `yt_downloader` | `YoutubeDownloader` | Cached once per browser session |
| `ig_downloader` | `InstagramDownloader` | Cached once per browser session |
| `platform` | `str \| None` | `"youtube"` / `"instagram"` — set on Fetch Info |
| `video_info` | `VideoInfo \| None` | Metadata from last Fetch Info |
| `last_url` | `str` | Detects URL change → resets video_info |
| `download_result` | `DownloadResult \| None` | Last download outcome |
| `download_filepath` | `Path \| None` | Points to saved file on disk |
| `download_filename` | `str \| None` | Filename for the download button label |
| `format_radio` | `str` | Sidebar radio widget state (Streamlit-managed) |
| `quality_select` | `str` | Sidebar selectbox widget state (Streamlit-managed) |

---

## File inventory

| File | Role |
|---|---|
| `app.py` | Streamlit entry point — UI only, no business logic |
| `downloader/youtube.py` | `YoutubeDownloader`, `VideoInfo`, `DownloadResult` |
| `downloader/instagram.py` | `InstagramDownloader(YoutubeDownloader)` — Instagram-specific logic |
| `downloader/utils.py` | URL validation, platform detection, filename sanitisation, filesize formatting |
| `downloader/__init__.py` | Package surface: all five public symbols |
| `requirements.txt` | Python dependencies (streamlit, yt-dlp, requests, certifi) |
| `.streamlit/config.toml` | Dark theme: primaryColor #ff4b6e, background #0d1117 |
| `launch.bat` | Windows double-click launcher — creates venv, installs deps, starts app |
| `setup_windows.ps1` | Full Windows setup via winget/choco/scoop (system-level deps) |
| `setup_macos.sh` | macOS setup via Homebrew |
| `setup_linux.sh` | Linux setup via apt/dnf/pacman |
| `CLAUDE.md` | This file |

---

## Running locally (any platform)

```bash
# Python 3.10+ required
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows PowerShell

pip install -r requirements.txt
streamlit run app.py
# Opens at http://localhost:8501
```

**Windows shortcut:** double-click `launch.bat` — handles venv, deps, and browser.

---

## Common development tasks

### Add a new video quality option (YouTube only)
1. Add the label to `QUALITY_OPTIONS` in `app.py`
2. Add the yt-dlp format string to `_video_format_string()` in `downloader/youtube.py`

### Change the download size cap
Edit `_MAX_FILESIZE_BYTES` in **both** `downloader/youtube.py` and
`downloader/instagram.py` (currently `2 * 1024 * 1024 * 1024`).

### Change the network timeout
Edit `_SOCKET_TIMEOUT_SECONDS` in **both** `downloader/youtube.py` and
`downloader/instagram.py`.

### Add support for another platform (TikTok, Vimeo, etc.)
yt-dlp already handles 1000+ sites. Steps to wire in the UI:
1. Add URL-validation patterns to `utils.py` (new `_<PLATFORM>_PATTERNS` list)
2. Update `detect_platform()` in `utils.py` to return the new platform name
3. Update `validate_url()` error message to mention the new platform
4. Subclass `YoutubeDownloader` in `downloader/<platform>.py`
5. Add a new `<platform>_downloader` to `_init_state()` in `app.py`
6. Update `active_downloader` selection logic in `app.py`

### Update the brand colours
Edit `CUSTOM_CSS` in `app.py` (search for `#ff4b6e`) and `.streamlit/config.toml`.

### Instagram-specific notes
- **Login-gated content**: yt-dlp cannot bypass Instagram login walls.
  Private accounts and login-required stories will return a friendly error.
- **Image-only posts**: yt-dlp returns "No video formats found" — mapped to a
  user-friendly message.
- **Carousel posts**: `noplaylist=True` returns the first video item only.

---

## yt-dlp option reference (key options used)

| Option | Value | Why |
|---|---|---|
| `socket_timeout` | 30 | Prevents indefinite hangs on slow/unresponsive servers |
| `max_filesize` | 2 GiB | Guards against disk exhaustion and RAM exhaustion |
| `noplaylist` | True | Never download a whole playlist / carousel from a single URL |
| `quiet` | True | Suppresses yt-dlp console noise in the Streamlit process |
| `merge_output_format` | `"mp4"` | Forces MP4 container after video+audio merge |
| `format` (YT MP4) | `bestvideo[ext=mp4]+bestaudio[ext=m4a]/…` | Quality-aware format selector |
| `format` (IG MP4) | `bestvideo[ext=mp4]+bestaudio[ext=m4a]/…/best` | Instagram best-available selector |
| `format` (MP3) | `bestaudio/best` | Picks best audio stream for extraction |

---

## Quick syntax check (no test framework required)

```bash
python -m py_compile app.py downloader/youtube.py downloader/instagram.py downloader/utils.py
echo "OK"
```

---

## PR history (for context on what's already been fixed)

| PR | Branch | What changed |
|---|---|---|
| #3 | `copilot/create-cross-platform-setup-launcher` | Added setup_linux.sh, setup_macos.sh, setup_windows.ps1 |
| #4 | `fix/security-and-performance-audit` | 9 security + performance fixes (see Security section above) |
| #5 | `feat/windows-launch-bat` | Added launch.bat double-click launcher |
| #6 | `feat/modern-ui-and-docs` | Modern sidebar UI, CLAUDE.md, updated README |
| #7 | `feat/instagram-download` | Instagram Reels/Posts/IGTV/Stories download support, multi-platform UI |
