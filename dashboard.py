"""
dashboard.py
Streamlit control panel for MR INDIA COMPUTER HUB's automation pipeline.

Flow:
  1. Click "Find Trending Topics" -> LLM suggests 5 topic ideas (buttons).
  2. Click a suggestion -> it fills the input bar. OR type your own topic directly.
  3. Click "Generate Video" -> runs the full pipeline (script -> title ->
     Hindi voiceover -> render -> upload) and streams live status/logs.

Run with:
    streamlit run dashboard.py
"""
import requests
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import io
import uuid
import base64
import contextlib
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import database as db
from agents import trend_agent
from main import run_one_topic, OUTPUT_DIR

db.init_local_cache()
db.start_background_sync(interval_seconds=5)

st.set_page_config(page_title="MR India Computer Hub — Content Dashboard", page_icon="🛠️", layout="centered")

LOGO_PATH = "assets/logo.png"


def _logo_b64():
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --ec-orange: #FF9800;
    --ec-orange-dark: #F57C00;
    --ec-blue: #2874F0;
    --ec-blue-dark: #1957C2;
    --ec-green: #2E7D32;
    --ec-bg: #F1F3F6;
    --ec-surface: #FFFFFF;
    --ec-border: #E3E6EA;
    --ec-text: #1A1A1A;
    --ec-text-dim: #6B7280;
}

* { font-family: 'Inter', sans-serif !important; }

/* Restore Streamlit's icon font so expander arrows render as icons, not text */
[data-testid="stExpanderToggleIcon"],
[data-testid="stIconMaterial"],
span[class*="material-icons"],
i[class*="material-icons"] {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}

[data-testid="stAppViewContainer"], [data-testid="stApp"], body {
    background: var(--ec-bg) !important;
}
[data-testid="stHeader"] { background: transparent !important; }

h1, h2, h3 { font-family: 'Poppins', sans-serif !important; font-weight: 700 !important; letter-spacing: -0.01em; color: var(--ec-text) !important; }
p, span, div, label { color: var(--ec-text); }

.panel {
    background: var(--ec-surface);
    border: 1px solid var(--ec-border);
    border-radius: 12px;
    padding: 22px 24px;
    margin-bottom: 14px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}
.panel-title {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.8rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ec-text-dim);
    margin-bottom: 14px;
}
.led-row { display: flex; gap: 28px; flex-wrap: wrap; margin-bottom: 16px; }
.led-item { display: flex; flex-direction: column; gap: 6px; min-width: 120px; }
.led-label {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.72rem;
    color: var(--ec-text-dim);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.led-value {
    font-family: 'Poppins', sans-serif !important;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--ec-text);
    display: flex;
    align-items: center;
    gap: 8px;
}
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.dot-on { background: var(--ec-green); box-shadow: 0 0 8px rgba(46,125,50,0.5); animation: pulse 2s infinite; }
.dot-off { background: #D32F2F; box-shadow: 0 0 6px rgba(211,47,47,0.4); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

.quota-bar-track {
    width: 100%; height: 8px; background: #EDEFF2; border-radius: 4px;
    overflow: hidden; border: 1px solid var(--ec-border); margin-top: 4px;
}
.quota-bar-fill { height: 100%; background: linear-gradient(90deg, var(--ec-orange), #FFB84D); border-radius: 4px; transition: width 0.4s ease; }
.quota-bar-fill.over { background: linear-gradient(90deg, #E53935, #FF7043); }

.hour-pills { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
.pill {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.8rem;
    padding: 5px 12px;
    border-radius: 20px;
    border: 1px solid var(--ec-border);
    color: var(--ec-text-dim);
    background: #F7F8FA;
}
.pill.top { border-color: var(--ec-orange); color: var(--ec-orange-dark); background: #FFF3E0; }

.term {
    background: #0f172a;
    border: 1px solid var(--ec-border);
    border-radius: 8px;
    padding: 14px 16px;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.8rem;
    line-height: 1.65;
    max-height: 260px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
}
.term .tag { color: #6EE7A8; font-weight: 600; }
.term .err { color: #FDBA74; font-weight: 600; }
.term .line { color: #CBD5E1; }

div[data-testid="stTabs"] button[data-baseweb="tab"] {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    color: var(--ec-text-dim) !important;
}
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] { color: var(--ec-blue) !important; }
div[data-testid="stTabs"] div[data-baseweb="tab-highlight"] {
    background: var(--ec-blue) !important;
    height: 3px !important;
}
div[data-testid="stTabs"] div[data-baseweb="tab-border"] { background: var(--ec-border) !important; }

div[data-testid="stMetric"] {
    background: var(--ec-surface);
    border: 1px solid var(--ec-border);
    border-top: 3px solid var(--ec-orange);
    border-radius: 10px;
    padding: 12px 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
div[data-testid="stMetricLabel"] { color: var(--ec-text-dim) !important; font-weight: 600 !important; }
div[data-testid="stMetricValue"] { color: var(--ec-blue-dark) !important; font-family: 'Poppins', sans-serif !important; font-weight: 700 !important; }

div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] div[data-baseweb="select"] {
    background: var(--ec-surface) !important;
    border: 1px solid var(--ec-border) !important;
    border-radius: 8px !important;
    color: var(--ec-text) !important;
    font-family: 'Inter', sans-serif !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: var(--ec-blue) !important;
    box-shadow: 0 0 0 1px var(--ec-blue) !important;
}
div[data-testid="stTextInput"] label,
div[data-testid="stSelectbox"] label {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 600 !important;
    color: var(--ec-text) !important;
}

div[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, var(--ec-orange), var(--ec-orange-dark)) !important;
    border: none !important;
    color: #FFFFFF !important;
    font-family: 'Poppins', sans-serif !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(245,124,0,0.35);
    transition: box-shadow 0.15s ease, transform 0.1s ease;
}
div[data-testid="stButton"] button[kind="primary"]:hover { box-shadow: 0 4px 14px rgba(245,124,0,0.5); transform: translateY(-1px); }
div[data-testid="stButton"] button[kind="primary"]:disabled { background: #FFCC80 !important; color: #FFF !important; box-shadow: none; }

div[data-testid="stButton"] button:not([kind="primary"]) {
    background: var(--ec-surface) !important;
    border: 1px solid var(--ec-blue) !important;
    color: var(--ec-blue) !important;
    border-radius: 8px !important;
    font-family: 'Poppins', sans-serif !important;
    font-weight: 600 !important;
}
div[data-testid="stButton"] button:not([kind="primary"]):hover { background: #EAF1FE !important; box-shadow: 0 2px 8px rgba(40,116,240,0.2); }

div[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--ec-border) !important;
    border-radius: 10px !important;
    background: var(--ec-surface) !important;
}

.section-eyebrow {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.8rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ec-text-dim);
    margin-bottom: 10px;
}

.brand-header { display: flex; align-items: center; gap: 16px; margin-bottom: 2px; }
.brand-header img { width: 56px; height: 56px; border-radius: 50%; border: 1px solid var(--ec-border); }
.brand-header .name {
    font-family: 'Poppins', sans-serif !important;
    font-size: 2.1rem;
    font-weight: 800;
    background: linear-gradient(90deg, var(--ec-blue) 0%, var(--ec-orange) 120%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}

.badge-row { display: flex; gap: 10px; flex-wrap: wrap; margin: 10px 0 16px; }
.badge {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.78rem;
    padding: 5px 12px;
    border-radius: 20px;
    border: 1px solid var(--ec-green);
    color: var(--ec-green);
    background: #E8F5E9;
}
.badge.muted { border-color: var(--ec-border); color: var(--ec-text-dim); background: #F7F8FA; }

.contact-btn-row { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 4px; }
.contact-btn {
    display: flex; flex-direction: column; gap: 2px;
    text-decoration: none !important;
    background: #FAFBFC;
    border: 1px solid var(--ec-border);
    border-radius: 10px;
    padding: 10px 16px;
    min-width: 170px;
    transition: all 0.15s ease;
}
.contact-btn:hover { border-color: var(--ec-orange); box-shadow: 0 4px 12px rgba(245,124,0,0.15); transform: translateY(-1px); }
.contact-btn .label {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.68rem;
    color: var(--ec-text-dim);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.contact-btn .value {
    font-family: 'Poppins', sans-serif !important;
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--ec-blue-dark);
}

div[data-testid="stExpander"] {
    background: var(--ec-surface) !important;
    border: 1px solid var(--ec-border) !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    overflow: hidden;
}
div[data-testid="stExpander"] summary { color: var(--ec-text) !important; font-family: 'Poppins', sans-serif !important; font-weight: 600 !important; }

/* Selectbox dropdown popup — fix low-contrast option text (broad catch-all) */
div[data-baseweb="popover"],
div[data-baseweb="menu"],
ul[role="listbox"] {
    background: #1E293B !important;
    border: 1px solid var(--ec-blue) !important;
    border-radius: 8px !important;
}
div[data-baseweb="popover"] *,
div[data-baseweb="menu"] *,
ul[role="listbox"] *,
li[role="option"],
li[role="option"] * {
    color: #F5F7FA !important;
    background: transparent !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
}
li[role="option"]:hover,
li[role="option"][aria-selected="true"],
li[role="option"]:hover *,
li[role="option"][aria-selected="true"] * {
    background: var(--ec-blue) !important;
    color: #FFFFFF !important;
}
</style>
""", unsafe_allow_html=True)

if "topic_input" not in st.session_state:
    st.session_state.topic_input = ""
if "suggestions" not in st.session_state:
    st.session_state.suggestions = []
if "selected_category" not in st.session_state:
    st.session_state.selected_category = "General"
if "selected_angle" not in st.session_state:
    st.session_state.selected_angle = "tip"

_logo64 = _logo_b64()
if _logo64:
    st.markdown(
        f"""
        <div class="brand-header">
          <img src="data:image/png;base64,{_logo64}" />
          <span class="name">MR India Computer Hub</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.title("MR India Computer Hub")

st.caption("Generate a topic, then create and auto-upload a Hindi voiceover Short.")

import subprocess
import html as _html


def is_scheduler_running():
    try:
        out = subprocess.run(["pgrep", "-f", "scheduler.py"], capture_output=True, text=True)
        return bool(out.stdout.strip())
    except Exception:
        return False


@st.cache_data(ttl=15)
def _cached_today_count():
    return db.videos_created_today()


@st.cache_data(ttl=15)
def _cached_velocities():
    return db.velocity_by_upload_hour()


running = is_scheduler_running()
daily_target = int(os.getenv("VIDEOS_PER_DAY", 3))
today_count = _cached_today_count()
velocities = _cached_velocities()
quota_pct = min(100, int(100 * today_count / max(daily_target, 1)))
over_quota = today_count >= daily_target

SERVICE_CATEGORIES = {
    "Computer & Laptop Services": [
        "Laptop Repair", "Desktop Computer Repair", "Windows Installation", "Windows Activation",
        "Microsoft Office Installation", "Software Installation", "Driver Installation",
        "Virus & Malware Removal", "Data Recovery", "SSD Upgrade", "RAM Upgrade",
        "Hard Disk Replacement", "Laptop Screen Replacement", "Laptop Keyboard Replacement",
        "Laptop Battery Replacement", "Laptop Charger Replacement", "Motherboard Repair",
        "BIOS Update", "Password Unlock", "PC Health Check", "Custom PC Assembly",
    ],
    "Printer Services": [
        "Printer Installation", "Printer Driver Installation", "Printer Setup",
        "Wi-Fi Printer Setup", "Printer Troubleshooting", "Ink Tank Printer Service",
        "Laser Printer Service", "Scanner Setup",
    ],
    "CCTV Services": [
        "CCTV Camera Installation", "CCTV Camera Maintenance", "DVR/NVR Setup",
        "Remote Mobile Viewing Setup", "CCTV Repair",
    ],
    "Cyber Café & Online Services": [
        "Online Form Filling", "PAN Card Services", "Aadhaar Update Assistance",
        "Passport Application", "Voter ID Services", "Driving Licence Services",
        "Income Tax Return (ITR) Filing", "GST Registration", "GST Return Filing",
        "MSME Registration", "Printout & Photocopy", "Color Printing",
        "Document Scanning", "Lamination", "Passport Size Photo", "Resume Creation",
    ],
    "Computer Accessories": [
        "Keyboard Sales", "Mouse Sales", "Laptop Charger Sales", "SSD & HDD Sales",
        "Pendrive Sales", "HDMI Cable Sales", "VGA Cable Sales", "LAN Cable Sales",
        "USB Hub Sales", "Webcam Sales", "Headphone & Speaker Sales",
    ],
    "Photography Services": [
        "Wedding Photography Booking", "Wedding Videography", "Drone Photography",
        "Event Photography", "Pre-Wedding Shoot", "Cinematic Wedding Video",
        "Birthday Event Photography", "Engagement Photography", "Album Design",
    ],
    "Networking Services": [
        "LAN Network Installation", "Wi-Fi Network Setup", "Router Configuration",
        "Network Troubleshooting", "Office Network Setup", "Home Network Installation",
        "NAS Storage Setup", "Wireless Network Security", "VPN Setup",
    ],
    "Digital Marketing Services": [
        "Search Engine Optimization (SEO)", "Local SEO", "Google Business Profile Optimization",
        "Google Maps SEO", "Social Media Marketing", "Facebook Marketing",
        "Instagram Marketing", "YouTube Marketing", "Website SEO", "Google Ads Management",
    ],
}

tab_about, tab_perf, tab_sched, tab_create, tab_customers = st.tabs([
    "About", "Upload Performance", "Adaptive Scheduler", "Create Video", "Customer History",
])

# --- TAB 0: About / Services (default landing tab) ---
with tab_about:
    address_q = "Jagannathpur, Nearby R.C. School, Biraul, Darbhanga, Bihar 848209".replace(" ", "+")
    st.markdown(
        f"""
        <div class="panel">
          <div class="panel-title">Mister India Computer Hub</div>
          <div class="led-label" style="font-size:0.9rem; color:#374151; line-height:1.7; text-transform:none; letter-spacing:normal;">
            A complete digital solution — computer &amp; laptop repair, computer accessories,
            cyber café &amp; online services, CCTV installation, printer setup &amp; support.
          </div>
          <div class="badge-row">
            <span class="badge">Verified &amp; Trusted Local Business</span>
            <span class="badge muted">Darbhanga, Bihar</span>
          </div>
          <div class="contact-btn-row">
            <a class="contact-btn" href="tel:+919311019135">
              <span class="label">Call</span>
              <span class="value">9311019135</span>
            </a>
            <a class="contact-btn" href="mailto:misterindiacomputerhub@gmail.com">
              <span class="label">Email</span>
              <span class="value">misterindiacomputerhub@gmail.com</span>
            </a>
            <a class="contact-btn" href="https://www.instagram.com/misterindiacomputerhub?igsh=MWJoNmVsaG5oa2lpaw==" target="_blank">
              <span class="label">Website</span>
              <span class="value">www.pcitinfra.com</span>
            </a>
            <a class="contact-btn" href="https://www.google.com/maps/search/?api=1&query={address_q}" target="_blank">
              <span class="label">Address</span>
              <span class="value" style="font-size:0.85rem;">Jagannathpur, Biraul, Darbhanga</span>
            </a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="panel-title" style="margin-top:4px;">Services We Provide</div>', unsafe_allow_html=True)

    CATEGORY_COLORS = ["#2874F0", "#FF9800", "#2E7D32", "#8E24AA", "#00897B", "#D81B60", "#5E35B1", "#EF6C00"]
    for (category, items), color in zip(SERVICE_CATEGORIES.items(), CATEGORY_COLORS):
        st.markdown(
            f'<div style="border-left:4px solid {color}; border-radius:4px; margin-bottom:2px;">',
            unsafe_allow_html=True,
        )
        with st.expander(f"{category}  ·  {len(items)} services"):
            cols = st.columns(2)
            for i, item in enumerate(items):
                cols[i % 2].markdown(f"- {item}")
        st.markdown("</div>", unsafe_allow_html=True)

# --- TAB 1: Upload Performance ---
with tab_perf:
    @st.cache_data(ttl=15)
    def _cached_perf_rows():
        return db.recent_video_performance(limit=10)

    perf_rows = _cached_perf_rows()

    if perf_rows:
        df = pd.DataFrame(perf_rows)
        df["label"] = df["title"].str.slice(0, 22) + df["title"].str.len().gt(22).map({True: "…", False: ""})
        df = df.sort_values("uploaded_at")

        total_views = int(df["views"].sum())
        total_likes = int(df["likes"].sum())
        total_comments = int(df["comments"].sum())
        best_video = df.loc[df["views"].idxmax()]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total views", f"{total_views:,}")
        c2.metric("Total likes", f"{total_likes:,}")
        c3.metric("Comments", f"{total_comments:,}")
        c4.metric("Top video", f"{int(best_video['views'])} views")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="panel-title">Views per upload</div>', unsafe_allow_html=True)
        chart_df = df.set_index("label")[["views"]]
        st.bar_chart(chart_df, color="#FF9800", height=280)
    else:
        st.markdown(
            '<div class="panel"><div class="led-label">No uploaded videos with performance data yet. '
            'Once the scheduler uploads and tracks a video, its stats will show up here.</div></div>',
            unsafe_allow_html=True,
        )

# --- TAB 2: Adaptive Scheduler ---
with tab_sched:
    led_html = f"""
    <div class="panel">
      <div class="panel-title">Live status</div>
      <div class="led-row">
        <div class="led-item">
          <span class="led-label">Process</span>
          <span class="led-value">
            <span class="dot {'dot-on' if running else 'dot-off'}"></span>
            {'Running' if running else 'Not running'}
          </span>
        </div>
        <div class="led-item">
          <span class="led-label">Today's quota</span>
          <span class="led-value">{today_count} / {daily_target}</span>
          <div class="quota-bar-track">
            <div class="quota-bar-fill {'over' if over_quota else ''}" style="width:{quota_pct}%;"></div>
          </div>
        </div>
        <div class="led-item">
          <span class="led-label">Mode</span>
          <span class="led-value" style="color: {'var(--ec-orange-dark)' if velocities else '#D32F2F'}; font-size:1.1rem;">
            {'Adaptive' if velocities else 'Learning (default hours)'}
          </span>
        </div>
      </div>
    """

    if velocities:
        ranked = sorted(velocities.items(), key=lambda kv: kv[1], reverse=True)
        pills = "".join(
            f'<span class="pill {"top" if i == 0 else ""}">{h:02d}:00 · {v:.1f}/hr</span>'
            for i, (h, v) in enumerate(ranked)
        )
        led_html += f'<div class="led-label" style="margin-top:4px;">Learned best posting hours (local)</div><div class="hour-pills">{pills}</div>'
    else:
        default_hours = os.getenv("DEFAULT_POST_HOURS", "9,14,19").split(",")
        pills = "".join(f'<span class="pill">{int(h):02d}:00</span>' for h in default_hours)
        led_html += f'<div class="led-label" style="margin-top:4px;">Default hours (gathering data to adapt)</div><div class="hour-pills">{pills}</div>'

    led_html += "</div>"
    st.markdown(led_html, unsafe_allow_html=True)

    if not running:
        st.warning(
            "Scheduler isn't running. Start it from your terminal with:\n\n"
            "`nohup python3 -u scheduler.py > scheduler.log 2>&1 &`"
        )

    if st.button("Refresh status"):
        st.rerun()

    log_path = "scheduler.log"
    term_lines = ""
    if os.path.exists(log_path):
        with open(log_path) as f:
            lines = f.readlines()[-15:]
        for line in lines:
            escaped = _html.escape(line.rstrip("\n"))
            if "failed" in line.lower() or "403" in line or "error" in line.lower():
                css_class = "err"
            elif escaped.startswith("[scheduler]"):
                css_class = "tag"
            else:
                css_class = "line"
            if escaped.startswith("[scheduler]"):
                escaped = escaped.replace(
                    "[scheduler]", '<span class="tag">[scheduler]</span>', 1
                )
                term_lines += f'<div class="{css_class if css_class == "err" else "line"}">{escaped}</div>'
            else:
                term_lines += f'<div class="{css_class}">{escaped}</div>'
    else:
        term_lines = '<div class="line" style="color:#94A3B8;">No scheduler.log yet.</div>'

    with st.expander("Debug log (raw scheduler.log)"):
        st.markdown(f'<div class="term">{term_lines}</div>', unsafe_allow_html=True)

# --- TAB 3: Create Video ---
with tab_create:
    if st.button("Find Trending Topic", use_container_width=True):
        with st.spinner("Asking for topic ideas..."):
            try:
                st.session_state.suggestions = trend_agent.suggest_trending_topics(n=5)
            except Exception as e:
                st.error(f"Couldn't fetch suggestions: {e}")
                st.session_state.suggestions = []

    if st.session_state.suggestions:
        st.write("**Suggested topics** — click one to use it:")
        for s in st.session_state.suggestions:
            label = f"{s['title_seed']}  ·  _{s['category']}_"
            if st.button(label, key=f"sugg_{s['title_seed']}", use_container_width=True):
                st.session_state.topic_input = s["title_seed"]
                st.session_state.selected_category = s.get("category", "General")
                st.session_state.selected_angle = s.get("angle", "tip")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="section-eyebrow">Create Video</div>', unsafe_allow_html=True)

        topic_text = st.text_input(
            "Topic",
            placeholder="e.g. Monsoon laptop moisture damage prevention",
            key="topic_input",
        )

        col1, col2 = st.columns(2)
        with col1:
            category = st.text_input("Category", key="selected_category")
        with col2:
            angle = st.selectbox(
                "Angle",
                ["tip", "explainer", "govt_guide", "product_review", "showcase"],
                key="selected_angle",
            )

        generate_clicked = st.button("Generate Video", type="primary", use_container_width=True, disabled=not topic_text.strip())

    if generate_clicked:
        topic_id = f"dashboard_{uuid.uuid4().hex[:8]}"
        topic = {
            "id": topic_id,
            "title_seed": topic_text.strip(),
            "category": category.strip() or "General",
            "angle": angle,
        }

        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO content_queue (id, category, title_seed, angle)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (id) DO NOTHING""",
            (topic["id"], topic["category"], topic["title_seed"], topic["angle"]),
        )

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        db.init_db()

        log_box = st.empty()
        log_buffer = io.StringIO()

        with st.status("Generating video — this can take a few minutes...", expanded=True) as status:
            try:
                with contextlib.redirect_stdout(log_buffer), contextlib.redirect_stderr(log_buffer):
                    youtube_id = run_one_topic(topic)
                log_box.code(log_buffer.getvalue() or "(no log output)")

                if youtube_id:
                    status.update(label="Done!", state="complete")
                    st.success("Video uploaded successfully.")
                    st.markdown(f"**Watch it here:** https://youtube.com/watch?v={youtube_id}")
                    st.session_state.suggestions = []
                    del st.session_state["topic_input"]
                else:
                    status.update(label="Failed", state="error")
                    st.error("Pipeline failed or was blocked by the compliance filter. Check the log above.")
            except Exception as e:
                log_box.code(log_buffer.getvalue() or "(no log output)")
                status.update(label="Failed", state="error")
                st.error(f"Unexpected error: {e}")

# --- TAB 4: Customer History ---
    # Trend Clip Studio
    # ---------------------------------------------------------------------------
    from agents.youtube_trend_agent import find_trending_topics
    from agents.seo_agent import generate_seo_checked as generate_seo
    from agents.clip_prompt_agent import generate_clip_prompts_checked as generate_clip_prompts
    from agents.video_merge_agent import merge_clips
    from agents.upload_agent import upload_video

    st.header("🎬 Trend Clip Studio")

    force_refresh = st.checkbox("🔄 Force fresh search (uses YouTube quota)", value=False,
                                 help="Off = reuse results from the last 3 hours if available, saving API quota. On = always hit YouTube fresh.")

    if st.button("🔍 Find Trending Topics (last 24h)"):
        with st.spinner("Searching..."):
            try:
                st.session_state["trend_results"] = find_trending_topics(hours=24, force_refresh=force_refresh)
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status == 429:
                    st.error("⚠️ YouTube search quota used up for today. It resets around midday (India time). Try again later, or pick a topic manually below.")
                else:
                    st.error(f"⚠️ Trending search failed (status {status}). Try again in a moment.")
                st.session_state["trend_results"] = st.session_state.get("trend_results", [])

    if "trend_results" in st.session_state and st.session_state["trend_results"]:
        options = {
            f"[{r['keyword']}] {r['topic_title']} ({r['views']} views)": r
            for r in st.session_state["trend_results"]
        }
        choice = st.selectbox("Pick a topic to base your video on:", list(options.keys()))
        selected = options[choice]

        if st.button("✅ Use this topic"):
            topic_id = str(uuid.uuid4())[:8]
            db.create_clip_job(topic_id, selected["topic_title"], selected["keyword"])

            from agents.seo_agent import match_real_service

            seo = generate_seo(selected["topic_title"], selected["keyword"])
            matched_service = match_real_service(selected["topic_title"], selected["keyword"])
            prompts = generate_clip_prompts(selected["topic_title"], matched_service)

            db.update_clip_job(
                topic_id,
                seo_title=seo["title"],
                seo_description=seo["description"],
                seo_tags=",".join(seo["tags"]),
                prompt_hook=prompts[0]["prompt"],
                prompt_demo=prompts[1]["prompt"],
                prompt_cta=prompts[2]["prompt"],
                status="seo_ready",
            )
            st.session_state["active_topic_id"] = topic_id
            st.rerun()

    if "active_topic_id" in st.session_state:
        job = db.get_clip_job(st.session_state["active_topic_id"])

        st.subheader("SEO Metadata")
        st.text_input("Title", job["seo_title"], key="seo_title_display")
        st.text_area("Description", job["seo_description"], key="seo_desc_display")
        st.text_input("Tags", job["seo_tags"], key="seo_tags_display")

        st.subheader("Copy these into Gemini / Veo")
        st.code(job["prompt_hook"], language=None)
        st.code(job["prompt_demo"], language=None)
        st.code(job["prompt_cta"], language=None)

        st.subheader("Upload your 3 generated clips")
        c1 = st.file_uploader("Clip 1 — Hook", type=["mp4"], key="c1")
        c2 = st.file_uploader("Clip 2 — Demo", type=["mp4"], key="c2")
        c3 = st.file_uploader("Clip 3 — CTA", type=["mp4"], key="c3")

        if c1 and c2 and c3 and st.button("🎬 Merge & Upload to YouTube"):
            with st.spinner("Merging clips..."):
                topic_id = job["topic_id"]
                tmp_dir = os.path.join(OUTPUT_DIR, f"{topic_id}_raw")
                os.makedirs(tmp_dir, exist_ok=True)
                paths = []
                for i, f in enumerate([c1, c2, c3], start=1):
                    p = os.path.join(tmp_dir, f"clip{i}.mp4")
                    with open(p, "wb") as out:
                        out.write(f.read())
                    paths.append(p)

                final_path = merge_clips(paths, topic_id)
                db.update_clip_job(
                    topic_id,
                    clip1_path=paths[0], clip2_path=paths[1], clip3_path=paths[2],
                    final_video_path=final_path, status="merged",
                )

            with st.spinner("Uploading to YouTube..."):
                video_id = upload_video(
                    final_path, job["seo_title"], job["seo_description"],
                    job["seo_tags"].split(","),
                )
                db.update_clip_job(topic_id, youtube_video_id=video_id, status="uploaded")

            st.success(f"Uploaded! https://youtube.com/watch?v={video_id}")
            del st.session_state["active_topic_id"]

with tab_customers:
    # customer_services table is created by database.py's init_db() on Postgres

    ALL_SERVICES = sorted({item for items in SERVICE_CATEGORIES.values() for item in items})

    st.markdown('<div class="section-eyebrow">Add Service Record</div>', unsafe_allow_html=True)

    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            cust_name = st.text_input("Customer Name", key="cust_name", placeholder="e.g. Ravi Kumar")
            cust_mobile = st.text_input("Mobile Number", key="cust_mobile", placeholder="e.g. 9876543210")
        with c2:
            service_choice = st.selectbox("Service Provided", ALL_SERVICES + ["Other"], key="service_choice")
            other_service = ""
            if service_choice == "Other":
                other_service = st.text_input("Specify Service", key="other_service", placeholder="e.g. Custom repair job")

        cust_detail = st.text_area(
            "Customer Detail / Address (optional)", key="cust_detail",
            placeholder="Address, landmark, or any note about the customer", height=70,
        )

        c3, c4, c5 = st.columns(3)
        with c3:
            amount = st.number_input("Amount (Rs.)", min_value=0.0, step=50.0, key="service_amount")
        with c4:
            payment_status = st.selectbox("Payment Status", ["Paid", "Pending", "Partial"], key="payment_status")
        with c5:
            payment_method = st.selectbox("Payment Method", ["Cash", "UPI", "Card", "Other"], key="payment_method")

        service_notes = st.text_area(
            "Service Notes (optional)", key="service_notes",
            placeholder="Any extra details about the work done", height=70,
        )
        service_date = st.date_input("Service Date", key="service_date")

        final_service_name = other_service.strip() if service_choice == "Other" else service_choice

        save_clicked = st.button(
            "Save Service Record",
            type="primary",
            use_container_width=True,
            disabled=not (cust_name.strip() and cust_mobile.strip() and final_service_name),
        )

    if save_clicked:
        db.save_customer_service_local(
            cust_name.strip(), cust_mobile.strip(), cust_detail.strip(),
            final_service_name, amount, payment_status, payment_method,
            service_notes.strip(), str(service_date),
        )
        st.success(f"Saved service record for {cust_name.strip()}.")
        st.rerun()

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-eyebrow">Customer History</div>', unsafe_allow_html=True)

    hist_rows = db.get_customer_history_local()

    if hist_rows:
        hist_df = pd.DataFrame(hist_rows)
        hist_df = hist_df.rename(columns={
            "local_id": "ID", "customer_name": "Customer", "mobile_number": "Mobile",
            "customer_detail": "Detail", "service_name": "Service", "amount": "Amount",
            "payment_status": "Payment Status", "payment_method": "Method",
            "notes": "Notes", "service_date": "Date",
        })
        hist_df = hist_df[["ID", "Customer", "Mobile", "Detail", "Service", "Amount",
                            "Payment Status", "Method", "Notes", "Date"]]

        total_customers = hist_df["Mobile"].nunique()
        total_revenue = hist_df.loc[hist_df["Payment Status"] == "Paid", "Amount"].sum()
        total_pending = hist_df.loc[hist_df["Payment Status"].isin(["Pending", "Partial"]), "Amount"].sum()
        total_jobs = len(hist_df)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Customers", f"{total_customers}")
        m2.metric("Total Services", f"{total_jobs}")
        m3.metric("Revenue Collected", f"Rs.{total_revenue:,.0f}")
        m4.metric("Pending Amount", f"Rs.{total_pending:,.0f}")

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        search = st.text_input(
            "Search by customer name or mobile number", key="cust_search",
            placeholder="Type a name or number...",
        )

        filtered_df = hist_df
        if search.strip():
            q = search.strip().lower()
            filtered_df = hist_df[
                hist_df["Customer"].str.lower().str.contains(q)
                | hist_df["Mobile"].str.contains(q)
            ]

        display_df = filtered_df.drop(columns=["ID"]).copy()
        status_emoji = {"Paid": "\U0001F7E2 Paid", "Pending": "\U0001F534 Pending", "Partial": "\U0001F7E1 Partial"}
        display_df["Payment Status"] = display_df["Payment Status"].map(status_emoji).fillna(display_df["Payment Status"])

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Amount": st.column_config.NumberColumn("Amount", format="Rs.%.0f"),
            },
        )
    else:
        st.markdown(
            '<div class="panel"><div class="led-label">No customer service records yet. '
            'Add the first one above once you complete a service for a customer.</div></div>',
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
