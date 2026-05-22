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
| **Video metadata** | Thumbnail, title, channel, duration, view count |
| **Real-time progress** | Download speed & ETA inside a collapsible status panel |
| **In-browser save** | One-click file download without exposing server paths |
| **Modern sidebar UI** | Format, quality, and system status in a collapsible sidebar |
| **Error handling** | Unavailable / private / geo-blocked / copyright / size-limit errors |
| **Filename safety** | Unicode normalisation, illegal-char stripping, duplicate prevention |
| **Security hardened** | XSS prevention, socket timeouts, 2 GiB download cap |
| **Cross-platform** | One-click launcher for Windows; setup scripts for macOS & Linux |

---

## 🖥️ Screenshots

> Run the app locally to see the full UI.

---

## 🚀 Quick Start

Clone the repository first:

```bash
git clone https://github.com/kunalsuri/media-downloader.git
cd media-downloader
```

Then choose the launcher for your operating system:

---

### 🪟 Windows 10 / 11 — double-click launcher

The fastest way to get started on Windows:

1. Open the `media-downloader` folder in Explorer
2. **Double-click `launch.bat`**
3. A terminal window opens — watch setup progress, then the browser opens automatically

That's it. The script creates a virtual environment, installs dependencies, and launches the app. On later runs it skips setup and starts in ~5 seconds.

**Environment variable overrides (optional):**

```cmd
:: Change port (run in CMD before double-clicking, or set in System Properties)
set STREAMLIT_PORT=8888
launch.bat

:: Rebuild virtual environment from scratch
set RECREATE_VENV=1
launch.bat
```

> **Need system-level dependencies** (Python, git, ffmpeg) installed automatically?
> Use `setup_windows.ps1` instead — it installs everything via winget/Chocolatey/Scoop.

---

### 🪟 Windows — full setup via PowerShell

Open **PowerShell** and run:

```powershell
# Allow local scripts to run (one-time, current user only — safe)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Navigate to the project directory
cd C:\path\to\media-downloader

# Run full setup and launch
.\setup_windows.ps1
```

**What it does automatically:**
- ✅ Detects Windows architecture (x86_64 / ARM64)
- ✅ Detects best available package manager: `winget` → `choco` → `scoop`
- ✅ Installs Python 3, git, and ffmpeg if missing
- ✅ Creates `.venv\`, installs Python packages, verifies imports
- ✅ Opens the app at **http://localhost:8501**

**PowerShell environment options:**

```powershell
$env:STREAMLIT_PORT="8888"; .\setup_windows.ps1   # Custom port
$env:SKIP_PKG_MANAGER="1"; .\setup_windows.ps1    # Skip winget/choco/scoop checks
$env:RECREATE_VENV="1"; .\setup_windows.ps1       # Rebuild virtual environment
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
- ✅ Creates `.venv/`, installs packages, verifies imports
- ✅ Opens the app at **http://localhost:8501**

**Environment options:**

```bash
STREAMLIT_PORT=8888 ./setup_macos.sh
SKIP_BREW=1 ./setup_macos.sh       # Skip Homebrew/ffmpeg checks
RECREATE_VENV=1 ./setup_macos.sh   # Rebuild virtual environment
```

> `setup_and_run.sh` (legacy macOS script) still works identically.

---

### 🐧 Linux (Ubuntu, Debian, Fedora, Arch, and more)

```bash
chmod +x setup_linux.sh
./setup_linux.sh
```

**What it does automatically:**
- ✅ Detects distro and selects `apt`, `dnf`, `yum`, or `pacman`
- ✅ Installs Python 3, pip, venv, git, and ffmpeg
- ✅ Creates `.venv/`, installs packages, verifies imports
- ✅ Opens the app at **http://localhost:8501**

**Environment options:**

```bash
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

---

### 🔧 Manual Setup (any OS)

```bash
# Prerequisites: Python ≥ 3.10 and ffmpeg on PATH

python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\Activate.ps1       # Windows PowerShell
# .venv\Scripts\activate.bat       # Windows CMD

pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
streamlit run app.py
# Opens at http://localhost:8501
```

---

## 🗂️ Project Structure

```
media-downloader/
├── app.py                  # Streamlit UI — sidebar, main area, session state
├── CLAUDE.md               # AI assistant context file (architecture, decisions, tasks)
├── launch.bat              # Windows double-click launcher ← start here on Windows
├── setup_macos.sh          # macOS one-command setup & launcher
├── setup_linux.sh          # Linux one-command setup & launcher
├── setup_windows.ps1       # Windows full setup (installs Python, git, ffmpeg)
├── setup_and_run.sh        # Legacy macOS script (backward compat)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable reference
├── README.md
├── CLAUDE.md
├── .gitignore
├── .streamlit/
│   └── config.toml         # Dark theme configuration
├── downloads/              # Downloaded media files (git-ignored, .gitkeep tracked)
└── downloader/             # Core downloader package
    ├── __init__.py         # Exports: YoutubeDownloader, validate_url, sanitize_filename
    ├── youtube.py          # YoutubeDownloader, VideoInfo, DownloadResult
    └── utils.py            # URL validation, filename sanitisation, helpers
```

### Module overview

| File | Responsibility |
|---|---|
| `app.py` | Streamlit page, sidebar settings, session state, UI components |
| `downloader/youtube.py` | `YoutubeDownloader` — info fetching, download orchestration, error mapping |
| `downloader/utils.py` | `validate_url`, `sanitize_filename`, `build_output_path`, `format_filesize` |
| `launch.bat` | Windows double-click launcher with first-run / subsequent-run optimisation |
| `setup_windows.ps1` | Full Windows system setup via winget/choco/scoop |
| `setup_macos.sh` | macOS setup: Homebrew, ffmpeg, venv, pip, launch |
| `setup_linux.sh` | Linux setup: apt/dnf/pacman, venv, pip, launch |

---

## ⚙️ Configuration

All runtime settings live in the **sidebar** of the running app:

| Setting | Location | Options |
|---|---|---|
| Output format | Sidebar → Output Format | MP4 (Video), MP3 (Audio only) |
| Video quality | Sidebar → Video Quality | best, 1080p, 720p, 480p, 360p |
| ffmpeg status | Sidebar → System | Auto-detected at startup |

Server settings via environment variables:

| Variable | Default | Description |
|---|---|---|
| `STREAMLIT_PORT` | `8501` | Port the Streamlit server listens on |
| `RECREATE_VENV` | `0` | Set `1` to rebuild the virtual environment |
| `SKIP_PKG_MANAGER` | `0` | Set `1` to skip system package checks (Linux/Windows) |
| `SKIP_BREW` | `0` | Set `1` to skip Homebrew checks (macOS) |

---

## 🔒 Security

- **XSS prevention**: All YouTube metadata is HTML-escaped before rendering
- **Absolute download path**: Files always land in `<project>/downloads/` regardless of working directory
- **Network timeout**: 30-second socket timeout on all yt-dlp calls prevents UI hangs
- **Download cap**: Maximum file size is 2 GiB to prevent disk/RAM exhaustion
- **No credentials stored**: Setup scripts never save API keys or passwords
- **Official sources only**: All packages installed from PyPI, Homebrew, official Linux repos, or winget

> This tool is intended for **personal use only**. Always respect YouTube's
> [Terms of Service](https://www.youtube.com/t/terms) and applicable copyright laws.

---

## 🔭 Extending to Other Platforms

`yt-dlp` supports 1000+ sites out of the box (Instagram, TikTok, Twitter/X, Vimeo, …).
To add a new platform:

1. Add URL-validation patterns to `_YOUTUBE_PATTERNS` in `downloader/utils.py`
2. Optionally subclass `YoutubeDownloader` in `downloader/<platform>.py` for platform-specific options
3. Wire the new validator and downloader into `app.py`

See `CLAUDE.md` for a step-by-step guide.

---

## 🤝 Contributing

Pull requests are welcome! Please open an issue first to discuss major changes.

```bash
# Syntax / import check (no test framework required)
python -m py_compile app.py downloader/youtube.py downloader/utils.py && echo OK
```

---

## 📄 License

[MIT](LICENSE) © Kunal Suri
