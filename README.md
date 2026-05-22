# ⬇️ Media Downloader

> A modern, production-quality **YouTube media downloader** built with Streamlit and yt-dlp.

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)
![Streamlit](https://img.shields.io/badge/streamlit-1.35%2B-red?logo=streamlit)
![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-orange)
![License](https://img.shields.io/github/license/kunalsuri/media-downloader)

---

## ✨ Features

| Feature | Details |
|---|---|
| **MP4 video** | Best quality video + audio merged via ffmpeg |
| **MP3 audio** | Audio-only extraction at 192 kbps |
| **Quality selector** | best, 1080p, 720p, 480p, 360p |
| **Video metadata** | Thumbnail, title, uploader, duration, view count |
| **Progress bar** | Real-time download speed & ETA |
| **In-browser save** | One-click file download without exposing server paths |
| **Error handling** | Unavailable / private / geo-blocked / copyright errors |
| **Filename safety** | Unicode normalisation, illegal-char stripping, duplicate prevention |
| **Dark UI** | Polished dark theme with gradient accents |

---

## 🖥️ Screenshots

> Run the app locally to see the full UI.

---

## 🚀 Quick Start

### Option A — One-command macOS setup (recommended)

For **macOS** (Apple Silicon or Intel), a single script handles everything:
Homebrew, ffmpeg, Python virtual environment, all dependencies, and app launch.

```bash
# 1. Clone the repository
git clone https://github.com/kunalsuri/media-downloader.git
cd media-downloader

# 2. Make the script executable (first time only)
chmod +x setup_and_run.sh

# 3. Run — setup + launch in one step
./setup_and_run.sh
```

The script will:
- ✅ Detect Apple Silicon vs Intel architecture
- ✅ Install missing tools (Homebrew, ffmpeg) automatically
- ✅ Create a Python virtual environment at `.venv/`
- ✅ Install all dependencies from `requirements.txt`
- ✅ Verify imports and open the app at **http://localhost:8501**

**Advanced options** (pass as environment variables):

| Variable | Default | Description |
|---|---|---|
| `STREAMLIT_PORT` | `8501` | Change the server port |
| `SKIP_BREW` | `0` | Set to `1` to skip Homebrew/ffmpeg checks |
| `RECREATE_VENV` | `0` | Set to `1` to rebuild the virtual environment from scratch |

```bash
# Example: run on port 8888 and skip Homebrew checks
STREAMLIT_PORT=8888 SKIP_BREW=1 ./setup_and_run.sh
```

---

### Option B — Manual setup (any OS)

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | ≥ 3.10 | [python.org](https://www.python.org/downloads/) |
| ffmpeg | any | See below |

#### Install ffmpeg

**macOS (Homebrew)**
```bash
brew install ffmpeg
```

**Ubuntu / Debian**
```bash
sudo apt update && sudo apt install ffmpeg -y
```

**Windows (Chocolatey)**
```powershell
choco install ffmpeg
```

> ℹ️ ffmpeg is required for MP3 extraction and for merging best-quality video+audio streams.
> The app still works in degraded mode without it (MP4 only, lower quality).

### Install the app

```bash
# 1. Clone the repository
git clone https://github.com/kunalsuri/media-downloader.git
cd media-downloader

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows PowerShell

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Run the Streamlit app
streamlit run app.py
```

The app opens automatically at **http://localhost:8501**.

---

## 🗂️ Project Structure

```
media-downloader/
├── app.py                  # Streamlit UI entry point
├── setup_and_run.sh        # macOS one-command setup & launcher script
├── requirements.txt        # Python dependencies
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml         # Dark-theme Streamlit configuration
├── downloads/              # Downloaded media files (git-ignored, .gitkeep tracked)
└── downloader/             # Core downloader package
    ├── __init__.py
    ├── youtube.py          # YoutubeDownloader class (yt-dlp wrapper)
    └── utils.py            # URL validation, filename sanitisation, helpers
```

### Module overview

| File | Responsibility |
|---|---|
| `app.py` | Streamlit page, CSS, session state, UI components |
| `downloader/youtube.py` | `YoutubeDownloader` — info fetching, download orchestration, error mapping |
| `downloader/utils.py` | `validate_url`, `sanitize_filename`, `build_output_path`, `format_filesize` |

---

## ⚙️ Configuration

All configuration is handled through the Streamlit UI at runtime.  No `.env`
file is required.  If you want to hard-code a custom `downloads/` directory,
edit the `DOWNLOADS_DIR` constant at the top of `app.py`.

---

## 🔒 Security & Legal

* Downloaded files are saved to the local `downloads/` directory on the
  **server** running Streamlit and served to the browser via `st.download_button`.
  No file paths are ever exposed to the client.
* Invalid, private, geo-blocked, and copyright-restricted videos are rejected
  gracefully with clear error messages.
* This tool is intended for **personal use only**.  Always respect YouTube's
  [Terms of Service](https://www.youtube.com/t/terms) and applicable copyright
  laws before downloading any content.

---

## 🔭 Extending to Other Platforms

`yt-dlp` supports 1000+ sites out of the box (Instagram, TikTok, Twitter/X,
Vimeo, …).  To add a new platform:

1. Add a URL-validation regex to `downloader/utils.py` → `_YOUTUBE_PATTERNS`
   (or create a separate validator per platform).
2. Optionally subclass `YoutubeDownloader` in a new `downloader/<platform>.py`
   file if platform-specific post-processing is needed.
3. Wire the new validator and downloader into `app.py`.

---

## 🤝 Contributing

Pull requests are welcome!  Please open an issue first to discuss major changes.

```bash
# Run a quick syntax / import check
python -c "import app; import downloader"
```

---

## 📄 License

[MIT](LICENSE) © Kunal Suri
