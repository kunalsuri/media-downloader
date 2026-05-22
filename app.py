"""
app.py – Main Streamlit application for the media-downloader.

Run with:
    streamlit run app.py

Features
--------
* Dark-themed, polished UI with custom CSS
* YouTube URL input with real-time validation
* Format selection: MP4 (video) or MP3 (audio)
* Quality selection via expandable settings panel
* Thumbnail preview and video metadata display
* Live progress bar + status messages during download
* Secure, in-browser file download button for the result
* Clear error feedback for all failure modes
"""

from __future__ import annotations

import io
import time
from pathlib import Path

import streamlit as st

from downloader import YoutubeDownloader, validate_url
from downloader.utils import format_filesize

# ---------------------------------------------------------------------------
# Page configuration (must be the very first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Media Downloader",
    page_icon="⬇️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS – dark, modern aesthetic
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
/* ── Global ──────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0e1117;
    color: #e0e0e0;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

/* ── Header ──────────────────────────────────────────────────── */
.app-header {
    text-align: center;
    padding: 2rem 0 1rem;
}
.app-header h1 {
    font-size: 2.6rem;
    font-weight: 700;
    background: linear-gradient(135deg, #ff4b6e, #ff8c42);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.app-header p {
    color: #8a8d93;
    font-size: 1rem;
    margin-top: 0;
}

/* ── Card ─────────────────────────────────────────────────────── */
.card {
    background: #1a1d26;
    border: 1px solid #2c2f3e;
    border-radius: 12px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.2rem;
}

/* ── Format buttons ──────────────────────────────────────────── */
div[data-testid="stHorizontalBlock"] .format-btn button {
    border-radius: 8px !important;
    border: 2px solid #2c2f3e !important;
    background: #1a1d26 !important;
    color: #e0e0e0 !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stHorizontalBlock"] .format-btn button:hover {
    border-color: #ff4b6e !important;
    color: #ff4b6e !important;
}

/* ── Primary action button ───────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #ff4b6e, #ff8c42) !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 2rem !important;
    transition: opacity 0.2s ease !important;
    width: 100%;
}
.stButton > button[kind="primary"]:hover {
    opacity: 0.88 !important;
}

/* ── Input field ─────────────────────────────────────────────── */
.stTextInput > div > div > input {
    background-color: #1a1d26 !important;
    border: 1px solid #2c2f3e !important;
    border-radius: 8px !important;
    color: #e0e0e0 !important;
    font-size: 0.95rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: #ff4b6e !important;
    box-shadow: 0 0 0 2px rgba(255, 75, 110, 0.25) !important;
}

/* ── Radio buttons ───────────────────────────────────────────── */
.stRadio > div { gap: 0.8rem; }
.stRadio label { font-size: 0.95rem !important; }

/* ── Progress bar ────────────────────────────────────────────── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #ff4b6e, #ff8c42) !important;
}

/* ── Expander ────────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background-color: #1a1d26 !important;
    border-radius: 8px !important;
    color: #8a8d93 !important;
    font-size: 0.9rem !important;
}

/* ── Info / success / error messages ────────────────────────── */
.stAlert {
    border-radius: 8px !important;
}

/* ── Metadata row ────────────────────────────────────────────── */
.meta-row {
    display: flex;
    gap: 1.2rem;
    flex-wrap: wrap;
    margin-top: 0.6rem;
}
.meta-chip {
    background: #22263a;
    border-radius: 20px;
    padding: 0.25rem 0.75rem;
    font-size: 0.8rem;
    color: #8a8d93;
}

/* ── Footer ──────────────────────────────────────────────────── */
.footer {
    text-align: center;
    color: #3e4250;
    font-size: 0.78rem;
    padding: 2rem 0 1rem;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DOWNLOADS_DIR = Path("downloads")
QUALITY_OPTIONS = ["best", "1080p", "720p", "480p", "360p"]

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
def _init_state() -> None:
    defaults = {
        "format_choice": "MP4 📹",
        "quality": "best",
        "video_info": None,
        "last_url": "",
        "download_result": None,
        "download_bytes": None,
        "download_filename": None,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


_init_state()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <h1>⬇️ Media Downloader</h1>
        <p>Download YouTube videos and audio in the highest quality — fast &amp; free.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# URL input
# ---------------------------------------------------------------------------
url_input = st.text_input(
    label="YouTube URL",
    placeholder="https://www.youtube.com/watch?v=…  or  https://youtu.be/…",
    help="Paste any YouTube video, Shorts, or Music link.",
    label_visibility="collapsed",
)

# ---------------------------------------------------------------------------
# Format selector (MP4 / MP3)
# ---------------------------------------------------------------------------
st.markdown("#### Choose Format")
col_mp4, col_mp3, _ = st.columns([1, 1, 3])
with col_mp4:
    if st.button("📹 MP4 — Video", use_container_width=True, key="btn_mp4"):
        st.session_state.format_choice = "MP4 📹"
        st.session_state.download_result = None
with col_mp3:
    if st.button("🎵 MP3 — Audio", use_container_width=True, key="btn_mp3"):
        st.session_state.format_choice = "MP3 🎵"
        st.session_state.download_result = None

# Show current selection badge
_badge_color = "#ff4b6e" if "MP4" in st.session_state.format_choice else "#ff8c42"
st.markdown(
    f'<p style="margin:0.2rem 0 0.8rem; color:{_badge_color}; font-weight:600;">'
    f"Selected: {st.session_state.format_choice}</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Advanced settings (expandable)
# ---------------------------------------------------------------------------
with st.expander("⚙️ Advanced Settings", expanded=False):
    st.session_state.quality = st.selectbox(
        "Video Quality",
        options=QUALITY_OPTIONS,
        index=QUALITY_OPTIONS.index(st.session_state.quality),
        disabled="MP3" in st.session_state.format_choice,
        help="Quality selector is only active for MP4 downloads.",
    )
    st.caption(
        "ℹ️ Higher qualities require ffmpeg to be installed on the server. "
        "If a format is unavailable, yt-dlp will automatically fall back to the next best option."
    )

# ---------------------------------------------------------------------------
# Fetch metadata button
# ---------------------------------------------------------------------------
st.markdown("---")

fetch_col, dl_col = st.columns([1, 1])

with fetch_col:
    fetch_clicked = st.button("🔍 Fetch Info", use_container_width=True)

with dl_col:
    download_clicked = st.button(
        "⬇️ Download",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.video_info is None,
    )

# ---------------------------------------------------------------------------
# Fetch video info
# ---------------------------------------------------------------------------
if fetch_clicked:
    is_valid, error_msg = validate_url(url_input)
    if not is_valid:
        st.error(f"🚫 {error_msg}")
        st.session_state.video_info = None
    else:
        with st.spinner("Fetching video information…"):
            downloader = YoutubeDownloader(output_dir=DOWNLOADS_DIR)
            try:
                info = downloader.get_info(url_input)
                st.session_state.video_info = info
                st.session_state.last_url = url_input
                st.session_state.download_result = None
                st.session_state.download_bytes = None
                st.session_state.download_filename = None
            except ValueError as exc:
                st.error(f"🚫 {exc}")
                st.session_state.video_info = None

# Reset info when URL changes
if url_input != st.session_state.last_url and st.session_state.video_info is not None:
    st.session_state.video_info = None
    st.session_state.download_result = None

# ---------------------------------------------------------------------------
# Video metadata card
# ---------------------------------------------------------------------------
if st.session_state.video_info is not None:
    info = st.session_state.video_info

    st.markdown(
        '<div class="card">',
        unsafe_allow_html=True,
    )

    thumb_col, meta_col = st.columns([1, 2])
    with thumb_col:
        if info.thumbnail_url:
            st.image(info.thumbnail_url, use_container_width=True)
    with meta_col:
        st.markdown(f"**{info.title}**")
        st.markdown(
            f'<div class="meta-row">'
            f'<span class="meta-chip">👤 {info.uploader}</span>'
            f'<span class="meta-chip">⏱ {info.duration_str}</span>'
            f'<span class="meta-chip">👁 {info.view_count:,} views</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
        if info.description:
            with st.expander("📄 Description", expanded=False):
                st.write(info.description[:800] + ("…" if len(info.description) > 800 else ""))

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
if download_clicked and st.session_state.video_info is not None:
    is_valid, error_msg = validate_url(url_input)
    if not is_valid:
        st.error(f"🚫 {error_msg}")
    else:
        mode = "mp3" if "MP3" in st.session_state.format_choice else "mp4"
        quality = st.session_state.quality

        progress_bar = st.progress(0, text="Starting download…")
        status_text = st.empty()

        def _progress_hook(d: dict) -> None:
            """Update Streamlit progress bar from yt-dlp hook data."""
            if d.get("status") == "downloading":
                downloaded = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                speed = d.get("speed")
                eta = d.get("eta")

                pct = int((downloaded / total) * 100) if total > 0 else 0
                pct = min(pct, 99)  # hold at 99 until post-processing done

                speed_str = (
                    format_filesize(int(speed)) + "/s" if speed else "calculating…"
                )
                eta_str = f"{eta}s" if eta is not None else "calculating…"

                progress_bar.progress(
                    pct,
                    text=f"Downloading… {pct}% | Speed: {speed_str} | ETA: {eta_str}",
                )
            elif d.get("status") == "finished":
                progress_bar.progress(99, text="Processing / converting…")

        downloader = YoutubeDownloader(output_dir=DOWNLOADS_DIR)
        result = downloader.download(
            url=url_input,
            mode=mode,
            quality=quality,
            progress_callback=_progress_hook,
        )

        if result.success and result.file_path and result.file_path.exists():
            progress_bar.progress(100, text="✅ Download complete!")
            st.success(
                f"✅ **{result.file_path.name}** — "
                f"{format_filesize(result.file_size_bytes)}"
            )
            st.session_state.download_result = result

            # Read file into memory for the in-browser download button
            file_bytes = result.file_path.read_bytes()
            st.session_state.download_bytes = file_bytes
            st.session_state.download_filename = result.file_path.name
        else:
            progress_bar.empty()
            st.error(f"🚫 {result.error_message}")
            st.session_state.download_result = None

# ---------------------------------------------------------------------------
# In-browser download button (persists across reruns)
# ---------------------------------------------------------------------------
if (
    st.session_state.download_bytes is not None
    and st.session_state.download_filename is not None
):
    file_ext = Path(st.session_state.download_filename).suffix.lower()
    mime = "audio/mpeg" if file_ext == ".mp3" else "video/mp4"

    st.download_button(
        label=f"💾 Save {st.session_state.download_filename}",
        data=st.session_state.download_bytes,
        file_name=st.session_state.download_filename,
        mime=mime,
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="footer">
        Built with ❤️ using <strong>Streamlit</strong> &amp; <strong>yt-dlp</strong>
        &nbsp;·&nbsp; For personal use only — respect copyright laws.
    </div>
    """,
    unsafe_allow_html=True,
)
