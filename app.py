"""
app.py – Main Streamlit application for the media-downloader.

Run with:
    streamlit run app.py
    — or double-click launch.bat on Windows.

Architecture
------------
* Sidebar  : format (MP4/MP3), quality, ffmpeg status, about
* Main     : hero, URL input, fetch/download actions, video card, progress
* Backend  : downloader.YoutubeDownloader cached in st.session_state
"""

from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

from downloader import YoutubeDownloader, validate_url
from downloader.utils import format_filesize

# ---------------------------------------------------------------------------
# Page configuration  (must be the very first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Media Downloader",
    page_icon="⬇️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS  — modern dark design system
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Base ─────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: #0d1117;
    color: #c9d1d9;
}

/* ── Sidebar shell ────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(170deg, #0d1117 0%, #131920 55%, #0d1117 100%);
    border-right: 1px solid rgba(255, 75, 110, 0.14);
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0; }

/* Sidebar brand block */
.sidebar-brand {
    padding: 1.8rem 1rem 1.4rem;
    text-align: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    margin-bottom: 0.25rem;
}
.sidebar-brand .brand-icon {
    font-size: 2.6rem;
    line-height: 1;
    display: block;
    margin-bottom: 0.55rem;
    filter: drop-shadow(0 0 18px rgba(255, 75, 110, 0.45));
}
.sidebar-brand h1 {
    font-size: 1.2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #ff4b6e, #ff8c42);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.2rem;
    letter-spacing: -0.01em;
}
.sidebar-brand p {
    font-size: 0.7rem;
    color: #5b6370;
    margin: 0;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

/* Sidebar section label */
.section-label {
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.13em;
    text-transform: uppercase;
    color: #5b6370;
    margin: 0 0 0.55rem;
    padding: 0;
}

/* Status badges (ffmpeg indicator) */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.28rem 0.7rem;
    border-radius: 100px;
    font-size: 0.73rem;
    font-weight: 500;
    line-height: 1.4;
}
.badge-ok {
    background: rgba(63, 185, 80, 0.1);
    color: #3fb950;
    border: 1px solid rgba(63, 185, 80, 0.28);
}
.badge-warn {
    background: rgba(210, 153, 34, 0.1);
    color: #d29922;
    border: 1px solid rgba(210, 153, 34, 0.28);
}

/* ── Hero ─────────────────────────────────────────────────────── */
.hero {
    text-align: center;
    padding: 2.2rem 0 1.8rem;
}
.hero h1 {
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #ff4b6e 0%, #ff8c42 55%, #fbbf24 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.45rem;
    letter-spacing: -0.02em;
    line-height: 1.2;
}
.hero p {
    color: #6b7280;
    font-size: 0.93rem;
    margin: 0;
}

/* ── URL input ────────────────────────────────────────────────── */
.stTextInput > div > div > input {
    background-color: #161b27 !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 12px !important;
    color: #e6edf3 !important;
    font-size: 0.94rem !important;
    padding: 0.7rem 1rem !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.stTextInput > div > div > input:focus {
    border-color: #ff4b6e !important;
    box-shadow: 0 0 0 3px rgba(255, 75, 110, 0.14) !important;
    outline: none !important;
}
.stTextInput > div > div > input::placeholder { color: #3d444d !important; }

/* ── Buttons ──────────────────────────────────────────────────── */
.stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    transition: all 0.18s ease !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    background: rgba(22, 27, 39, 0.8) !important;
    color: #c9d1d9 !important;
}
.stButton > button:hover {
    border-color: #ff4b6e !important;
    color: #ff4b6e !important;
    background: rgba(255, 75, 110, 0.06) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #ff4b6e, #ff8c42) !important;
    border: none !important;
    color: #fff !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 4px 18px rgba(255, 75, 110, 0.38) !important;
    transform: translateY(-1px) !important;
    color: #fff !important;
}

/* Download save button — distinct green */
.stDownloadButton > button {
    background: linear-gradient(135deg, #238636, #2ea043) !important;
    color: #fff !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
    border: none !important;
    border-radius: 12px !important;
    width: 100% !important;
    padding: 0.7rem 1.5rem !important;
    transition: all 0.18s ease !important;
    letter-spacing: 0.01em !important;
}
.stDownloadButton > button:hover {
    box-shadow: 0 4px 18px rgba(46, 160, 67, 0.38) !important;
    transform: translateY(-1px) !important;
}

/* ── Video info card ──────────────────────────────────────────── */
.video-card {
    position: relative;
    background: linear-gradient(135deg, rgba(22, 27, 39, 0.95), rgba(13, 17, 23, 0.9));
    border: 1px solid rgba(255, 75, 110, 0.2);
    border-radius: 16px;
    padding: 1.4rem 1.5rem;
    margin: 1.4rem 0;
    overflow: hidden;
}
/* Gradient accent line at top of card */
.video-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #ff4b6e, #ff8c42, transparent);
    border-radius: 16px 16px 0 0;
}
.video-title {
    font-size: 1rem;
    font-weight: 600;
    color: #e6edf3;
    line-height: 1.55;
    margin: 0.4rem 0 1.1rem;
}

/* ── Metrics ──────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid rgba(255, 255, 255, 0.07) !important;
    border-radius: 10px !important;
    padding: 0.6rem 0.75rem !important;
}
[data-testid="stMetricLabel"] p {
    font-size: 0.65rem !important;
    font-weight: 600 !important;
    color: #5b6370 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}
[data-testid="stMetricValue"] {
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    color: #c9d1d9 !important;
}
/* Hide delta arrow — no deltas in this app */
[data-testid="stMetricDelta"] { display: none !important; }

/* ── Progress bar ─────────────────────────────────────────────── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #ff4b6e, #ff8c42) !important;
    border-radius: 100px !important;
    transition: width 0.3s ease !important;
}

/* ── Status widget (download progress container) ──────────────── */
[data-testid="stStatusWidget"] {
    border-radius: 12px !important;
    border-color: rgba(255, 255, 255, 0.1) !important;
}

/* ── Expander ─────────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background-color: rgba(22, 27, 39, 0.5) !important;
    border-radius: 8px !important;
    font-size: 0.86rem !important;
    color: #7d8590 !important;
}

/* ── Alerts ───────────────────────────────────────────────────── */
.stAlert { border-radius: 10px !important; }

/* ── Radio (sidebar format selector) ─────────────────────────── */
.stRadio > div { gap: 0.4rem !important; }
.stRadio label {
    background: rgba(255, 255, 255, 0.025) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 10px !important;
    padding: 0.5rem 0.75rem !important;
    transition: all 0.18s ease !important;
    font-size: 0.86rem !important;
    cursor: pointer !important;
    width: 100% !important;
}
.stRadio label:hover {
    border-color: rgba(255, 75, 110, 0.45) !important;
    background: rgba(255, 75, 110, 0.06) !important;
}

/* ── Select / slider ──────────────────────────────────────────── */
.stSelectbox > div > div {
    background: rgba(22, 27, 39, 0.8) !important;
    border-radius: 10px !important;
    border-color: rgba(255, 255, 255, 0.1) !important;
}

/* ── Divider ──────────────────────────────────────────────────── */
hr { border-color: rgba(255, 255, 255, 0.06) !important; }

/* ── Footer ───────────────────────────────────────────────────── */
.footer {
    text-align: center;
    color: #3d444d;
    font-size: 0.73rem;
    padding: 2.5rem 0 1rem;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    margin-top: 2rem;
    line-height: 1.8;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DOWNLOADS_DIR = Path(__file__).parent / "downloads"
QUALITY_OPTIONS = ["best", "1080p", "720p", "480p", "360p"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fmt_views(n: int) -> str:
    """Format view counts compactly: 1_400_000 → '1.4M'."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
def _init_state() -> None:
    defaults: dict = {
        "video_info": None,
        "last_url": "",
        "download_result": None,
        "download_filepath": None,
        "download_filename": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # Cache the downloader so shutil.which("ffmpeg") runs only once per session.
    if "downloader" not in st.session_state:
        st.session_state.downloader = YoutubeDownloader(output_dir=DOWNLOADS_DIR)


_init_state()

# ===========================================================================
# SIDEBAR
# ===========================================================================
with st.sidebar:

    # ── Brand ────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="sidebar-brand">
            <span class="brand-icon">⬇️</span>
            <h1>Media Downloader</h1>
            <p>YouTube · MP4 &amp; MP3</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Format ───────────────────────────────────────────────────────────
    st.markdown('<p class="section-label">Output Format</p>', unsafe_allow_html=True)
    fmt = st.radio(
        "format",
        options=["📹  MP4 — Video", "🎵  MP3 — Audio only"],
        index=0,
        key="format_radio",
        label_visibility="collapsed",
    )
    is_mp3 = "MP3" in fmt

    st.divider()

    # ── Quality ──────────────────────────────────────────────────────────
    st.markdown('<p class="section-label">Video Quality</p>', unsafe_allow_html=True)
    if is_mp3:
        st.caption("Fixed at 192 kbps for MP3 downloads.")
        quality = "best"
    else:
        quality = st.selectbox(
            "Quality",
            options=QUALITY_OPTIONS,
            index=0,
            key="quality_select",
            label_visibility="collapsed",
            help="Higher qualities require ffmpeg. yt-dlp falls back automatically if unavailable.",
        )

    st.divider()

    # ── System status ────────────────────────────────────────────────────
    st.markdown('<p class="section-label">System</p>', unsafe_allow_html=True)
    ffmpeg_ok = st.session_state.downloader.ffmpeg_available
    if ffmpeg_ok:
        st.markdown(
            '<span class="badge badge-ok">✓&nbsp; ffmpeg ready</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="badge badge-warn">⚠&nbsp; ffmpeg not found</span>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Install [ffmpeg](https://ffmpeg.org/download.html) for MP3 extraction "
            "and quality-merged MP4 downloads."
        )

    st.divider()

    # ── About ────────────────────────────────────────────────────────────
    st.markdown('<p class="section-label">About</p>', unsafe_allow_html=True)
    st.caption(
        "Built with [Streamlit](https://streamlit.io) & "
        "[yt-dlp](https://github.com/yt-dlp/yt-dlp)."
    )
    st.caption("⚖️ Personal use only — respect copyright laws.")
    st.caption("Max download size: **2 GiB**.")

# ===========================================================================
# MAIN AREA
# ===========================================================================

# ── Hero ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero">
        <h1>⬇️ Media Downloader</h1>
        <p>Paste a YouTube URL, pick your format in the sidebar, then download.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── URL input ─────────────────────────────────────────────────────────────
url_input = st.text_input(
    label="YouTube URL",
    placeholder="https://www.youtube.com/watch?v=…   or   https://youtu.be/…",
    help="Supports videos, Shorts, and YouTube Music links.",
    label_visibility="collapsed",
    key="url_input",
)

# ── Reset state when URL changes ──────────────────────────────────────────
if url_input != st.session_state.last_url and st.session_state.video_info is not None:
    st.session_state.video_info = None
    st.session_state.download_result = None
    st.session_state.download_filepath = None

# ── Action buttons ────────────────────────────────────────────────────────
col_fetch, col_dl = st.columns(2)
with col_fetch:
    fetch_clicked = st.button(
        "🔍  Fetch Info",
        use_container_width=True,
        key="btn_fetch",
    )
with col_dl:
    download_clicked = st.button(
        "⬇️  Download",
        type="primary",
        use_container_width=True,
        disabled=(
            st.session_state.video_info is None
            or url_input != st.session_state.last_url
        ),
        key="btn_download",
    )

# ── Fetch video info ──────────────────────────────────────────────────────
if fetch_clicked:
    is_valid, error_msg = validate_url(url_input)
    if not is_valid:
        st.error(f"🚫 {error_msg}")
        st.session_state.video_info = None
    else:
        with st.spinner("Fetching video information…"):
            try:
                info = st.session_state.downloader.get_info(url_input)
                st.session_state.video_info = info
                st.session_state.last_url = url_input
                st.session_state.download_result = None
                st.session_state.download_filepath = None
                st.session_state.download_filename = None
            except ValueError as exc:
                st.error(f"🚫 {exc}")
                st.session_state.video_info = None

# ── Video info card ───────────────────────────────────────────────────────
if st.session_state.video_info is not None:
    info = st.session_state.video_info

    st.markdown('<div class="video-card">', unsafe_allow_html=True)

    thumb_col, meta_col = st.columns([1, 2])
    with thumb_col:
        if info.thumbnail_url:
            st.image(info.thumbnail_url, use_container_width=True)
    with meta_col:
        # Title — escaped to prevent HTML injection
        st.markdown(
            f'<p class="video-title">{html.escape(info.title)}</p>',
            unsafe_allow_html=True,
        )

        # Stats row
        c1, c2, c3 = st.columns(3)
        c1.metric("Duration", info.duration_str)
        c2.metric("Views", _fmt_views(info.view_count))
        # Truncate long channel names so the metric doesn't overflow
        uploader_display = info.uploader
        if len(uploader_display) > 20:
            uploader_display = uploader_display[:19] + "…"
        c3.metric("Channel", uploader_display)

        if info.description:
            with st.expander("📄 Description"):
                st.write(
                    info.description[:800]
                    + ("…" if len(info.description) > 800 else "")
                )

    st.markdown("</div>", unsafe_allow_html=True)

# ── Download ──────────────────────────────────────────────────────────────
if download_clicked and st.session_state.video_info is not None:
    mode = "mp3" if is_mp3 else "mp4"
    fmt_label = "MP3 · 192 kbps" if is_mp3 else f"MP4 · {quality}"

    with st.status(f"⬇️  Downloading as {fmt_label}…", expanded=True) as dl_status:

        progress_bar = st.progress(0, text="Connecting…")

        def _progress_hook(d: dict) -> None:
            """Feed yt-dlp progress data into the Streamlit progress bar."""
            if d.get("status") == "downloading":
                downloaded = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                speed = d.get("speed")
                eta = d.get("eta")

                pct = min(int((downloaded / total) * 100) if total > 0 else 0, 99)
                speed_str = (format_filesize(int(speed)) + "/s") if speed else "…"
                eta_str = f"{eta}s" if eta is not None else "…"

                progress_bar.progress(
                    pct,
                    text=f"{pct}%  ·  {speed_str}  ·  ETA {eta_str}",
                )
            elif d.get("status") == "finished":
                progress_bar.progress(99, text="Post-processing…")

        result = st.session_state.downloader.download(
            url=url_input,
            mode=mode,
            quality=quality,
            progress_callback=_progress_hook,
        )

        if result.success and result.file_path and result.file_path.exists():
            progress_bar.progress(100, text="Done!")
            dl_status.update(
                label=f"✅  Ready — {result.file_path.name}  ({format_filesize(result.file_size_bytes)})",
                state="complete",
                expanded=False,
            )
            st.session_state.download_result = result
            st.session_state.download_filepath = result.file_path
            st.session_state.download_filename = result.file_path.name
        else:
            dl_status.update(label="❌  Download failed", state="error")
            st.error(f"🚫 {result.error_message}")
            st.session_state.download_result = None

# ── Save-to-disk button (persists across reruns) ──────────────────────────
if (
    st.session_state.download_filepath is not None
    and st.session_state.download_filename is not None
    and st.session_state.download_filepath.exists()
):
    st.divider()
    file_ext = Path(st.session_state.download_filename).suffix.lower()
    mime = "audio/mpeg" if file_ext == ".mp3" else "video/mp4"

    with open(st.session_state.download_filepath, "rb") as fh:
        st.download_button(
            label=f"💾  Save  {st.session_state.download_filename}",
            data=fh,
            file_name=st.session_state.download_filename,
            mime=mime,
            use_container_width=True,
        )

# ── Footer ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="footer">
        Built with ❤️ using <strong>Streamlit</strong> &amp; <strong>yt-dlp</strong>
        &nbsp;·&nbsp; For personal use only — respect copyright laws.
    </div>
    """,
    unsafe_allow_html=True,
)
