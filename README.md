# ⬇️ Media Downloader

> A modern, production-quality **YouTube media downloader** built with Streamlit and yt-dlp.
> Supports **macOS** (Apple Silicon & Intel), **Linux** (Ubuntu, Debian, Fedora, Arch), and **Windows 10/11**.

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)
![Streamlit](https://img.shields.io/badge/streamlit-1.35%2B-red?logo=streamlit)
![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-orange)
![macOS](https://img.shields.io/badge/macOS-12%2B-lightgrey?logo=apple)
![Linux](https://img.shields.io/badge/Linux-Ubuntu%20%7C%20Debian%20%7C%20Fedora%20%7C%20Arch-gold?logo=linux)
![Windows](https://img.shields.io/badge/Windows-10%2F11-blue?logo=windows)
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
| **Cross-platform** | Dedicated setup scripts for macOS, Linux, and Windows |

---

## 🖥️ Screenshots

> Run the app locally to see the full UI.

---

## 🚀 Quick Start — One Command Per Platform

Clone the repository first, then run the setup script for your operating system.

```bash
git clone https://github.com/kunalsuri/media-downloader.git
cd media-downloader
```

---

### 🍎 macOS (Apple Silicon & Intel)

```bash
chmod +x setup_macos.sh
./setup_macos.sh
```

**What it does automatically:**
- ✅ Detects Apple Silicon (arm64) vs Intel (x86_64) architecture
- ✅ Installs Homebrew if missing (no sudo required)
- ✅ Installs ffmpeg via Homebrew
- ✅ Creates a Python virtual environment at `.venv/`
- ✅ Installs all Python dependencies from `requirements.txt`
- ✅ Verifies imports and opens the app at **http://localhost:8501**

**Environment variable options:**

| Variable | Default | Description |
|---|---|---|
| `STREAMLIT_PORT` | `8501` | Change the server port |
| `SKIP_BREW` | `0` | Set to `1` to skip Homebrew/ffmpeg checks |
| `RECREATE_VENV` | `0` | Set to `1` to rebuild the virtual environment from scratch |

```bash
# Examples
STREAMLIT_PORT=8888 ./setup_macos.sh
SKIP_BREW=1 ./setup_macos.sh
RECREATE_VENV=1 ./setup_macos.sh
```

> **Note:** `setup_and_run.sh` (legacy macOS script) is still available and works identically.

---

### 🐧 Linux (Ubuntu, Debian, Fedora, Arch, and more)

```bash
chmod +x setup_linux.sh
./setup_linux.sh
```

**What it does automatically:**
- ✅ Detects the Linux distribution (Ubuntu/Debian/Fedora/Arch/Manjaro/…)
- ✅ Selects the correct package manager: `apt`, `dnf`, `yum`, or `pacman`
- ✅ Installs Python 3, pip, venv support, git, and ffmpeg via the native package manager
- ✅ Creates a Python virtual environment at `.venv/`
- ✅ Installs all Python dependencies from `requirements.txt`
- ✅ Verifies imports and opens the app at **http://localhost:8501**

**Environment variable options:**

| Variable | Default | Description |
|---|---|---|
| `STREAMLIT_PORT` | `8501` | Change the server port |
| `SKIP_PKG_MANAGER` | `0` | Set to `1` to skip `apt`/`dnf`/`pacman` checks |
| `RECREATE_VENV` | `0` | Set to `1` to rebuild the virtual environment from scratch |

```bash
# Examples
STREAMLIT_PORT=8888 ./setup_linux.sh
SKIP_PKG_MANAGER=1 ./setup_linux.sh
RECREATE_VENV=1 ./setup_linux.sh
```

**Supported distributions:**

| Family | Distributions | Package Manager |
|---|---|---|
| Debian-based | Ubuntu 20.04+, Debian 11+, Mint, Pop!_OS | `apt` |
| RPM-based | Fedora 36+, RHEL 8+, CentOS Stream, Rocky, Alma | `dnf` / `yum` |
| Arch-based | Arch Linux, Manjaro, EndeavourOS, Garuda | `pacman` |

> **Tip:** On distributions where ffmpeg requires additional repositories
> (e.g., RPM Fusion on Fedora), the script attempts to enable them automatically.

---

### 🪟 Windows 10 / 11

Open **PowerShell** (search for "PowerShell" in the Start menu), then run:

```powershell
# Allow local scripts to run (one-time, current user only — safe)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Navigate to the project directory
cd C:\path\to\media-downloader

# Run setup and launch
.\setup_windows.ps1
```

**What it does automatically:**
- ✅ Detects Windows architecture (x86_64 / ARM64)
- ✅ Detects the best available package manager: `winget` → `choco` → `scoop`
- ✅ Installs Python 3, git, and ffmpeg if missing
- ✅ Creates a Python virtual environment at `.venv\`
- ✅ Installs all Python dependencies from `requirements.txt`
- ✅ Verifies imports and opens the app at **http://localhost:8501**

**Environment variable options (PowerShell syntax):**

```powershell
# Change port
$env:STREAMLIT_PORT="8888"; .\setup_windows.ps1

# Skip package manager checks
$env:SKIP_PKG_MANAGER="1"; .\setup_windows.ps1

# Rebuild virtual environment
$env:RECREATE_VENV="1"; .\setup_windows.ps1
```

**Supported package managers (auto-detected in priority order):**

| Package Manager | Availability | Notes |
|---|---|---|
| **winget** | Built into Windows 10 1809+ and Windows 11 | Recommended; no extra install needed |
| **Chocolatey** | Manual install required | [chocolatey.org/install](https://chocolatey.org/install) |
| **Scoop** | Manual install required | [scoop.sh](https://scoop.sh) |

> **Note:** If no package manager is detected, the script will warn you and skip
> automatic installation. In that case, install Python, git, and ffmpeg manually
> and then re-run the script with `$env:SKIP_PKG_MANAGER="1"`.

---

### 🔧 Manual Setup (any OS)

If you prefer to install dependencies yourself:

```bash
# 1. Prerequisites: Python ≥ 3.10 and ffmpeg must be installed and on PATH

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\Activate.ps1       # Windows PowerShell

# 3. Install Python dependencies
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
```

The app opens at **http://localhost:8501**.

---

## ⚙️ Environment Variables Reference

See [`.env.example`](.env.example) for a full annotated list of all supported
environment variables. Copy it to `.env` for your own reference — the setup
scripts read variables from the shell environment, not from `.env` directly.

---

## 🗂️ Project Structure

```
media-downloader/
├── app.py                  # Streamlit UI entry point
├── setup_macos.sh          # macOS one-command setup & launcher (Apple Silicon + Intel)
├── setup_linux.sh          # Linux one-command setup & launcher (apt / dnf / pacman)
├── setup_windows.ps1       # Windows one-command setup & launcher (winget / choco / scoop)
├── setup_and_run.sh        # Legacy macOS script (kept for backward compatibility)
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment variable reference template
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
| `setup_macos.sh` | macOS setup: Homebrew, ffmpeg, venv, pip, launch |
| `setup_linux.sh` | Linux setup: apt/dnf/pacman, venv, pip, launch |
| `setup_windows.ps1` | Windows setup: winget/choco/scoop, venv, pip, launch |

---

## ⚙️ Configuration

All media-downloader settings are handled through the Streamlit UI at runtime.
No `.env` file is required for basic usage.

To hard-code a custom `downloads/` directory, edit the `DOWNLOADS_DIR`
constant at the top of `app.py`.

---

## 🔒 Security & Legal

* Downloaded files are saved to the local `downloads/` directory on the
  **server** running Streamlit and served to the browser via `st.download_button`.
  No file paths are ever exposed to the client.
* Invalid, private, geo-blocked, and copyright-restricted videos are rejected
  gracefully with clear error messages.
* The setup scripts never store credentials and only install packages from
  official sources (Homebrew formulae, official Linux repos, winget/choco sources).
* This tool is intended for **personal use only**.  Always respect YouTube's
  [Terms of Service](https://www.youtube.com/t/terms) and applicable copyright
  laws before downloading any content.

---

## 🔭 Extending to Other Platforms

`yt-dlp` supports 1000+ sites out of the box (Instagram, TikTok, Twitter/X,
Vimeo, Facebook, …).  To add a new platform:

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
python -m py_compile app.py downloader/youtube.py downloader/utils.py
```

---

## 📄 License

[MIT](LICENSE) © Kunal Suri
