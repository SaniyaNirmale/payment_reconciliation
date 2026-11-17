"""
PaySync — Payment Reconciliation Dashboard
==========================================
Modern, elegant fintech dashboard with soft minimal earthy aesthetic:
  - Pistachio green: #B7C99A, Light pista: #E3EBD7, Deep pista: #82966A
  - Faint warm brown: #B8A18A, Faint brown box: #7A624E, Header: #6B5644
  - Light beige: #F3EDE5, Cream: #FAF9F5, Dark brown text: #51483F
  - All dark boxes styled as faint warm brown with pure white text
  - Dataframe upper-right toolbar & tooltips styled with high-contrast visible icons
  - Dynamic period selection (2026-09, 2026-10, custom)
  - Strict separation of 'Upload My Files' vs 'Use Sample Data'
"""

import io
from decimal import Decimal
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Safe import with fallback to prevent ModuleNotFoundError
try:
    from config import COLORS, APP_NAME, APP_SUBTITLE, NAV_ITEMS, SAMPLE_PERIODS
except ImportError:
    COLORS = {
        "cream": "#FAF9F5",
        "beige_light": "#F3EDE5",
        "white": "#FFFFFF",
        "pista": "#B7C99A",
        "pista_light": "#E3EBD7",
        "pista_deep": "#82966A",
        "pista_border": "#A4B887",
        "brown_faint": "#B8A18A",
        "brown_border": "#D5C8B8",
        "brown_box": "#7A624E",
        "brown_header": "#6B5644",
        "brown_mid": "#8A715C",
        "text_dark": "#51483F",
        "text_muted": "#8A7F73",
        "amber_soft": "#D4A373",
        "red_soft": "#C97A7E",
        "blue_soft": "#7E99B7",
        "lavender": "#A89BB5",
    }
    APP_NAME = "PaySync"
    APP_SUBTITLE = "Payment Reconciliation"
    NAV_ITEMS = [
        ("overview", "Overview", "📊"),
        ("reconciliation", "Reconciliation", "⚖️"),
        ("exceptions", "Exceptions", "⚠️"),
        ("transactions", "Transactions", "📋"),
        ("reports", "Reports", "📥"),
    ]
    SAMPLE_PERIODS = ["2026-10", "2026-09", "2026-08", "2026-11"]

from reconciliation import ReconciliationEngine, format_inr, to_decimal, ReconciliationSummary
from data_generator import (
    generate_synthetic_data,
    get_sample_platform_template_csv,
    get_sample_bank_template_csv,
    get_data_issue_manifest,
)


# ═══════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title=f"{APP_NAME} · Payment Reconciliation",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ═══════════════════════════════════════════════════════════════════
# GLOBAL CSS (UI/UX POLISH & HIGH VISIBILITY)
# ═══════════════════════════════════════════════════════════════════
st.markdown(f"""
<style>
/* ── Reset & Base ─────────────────────────────────────────── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="block-container"] {{
    background-color: {COLORS["cream"]} !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}}

/* Base text color targeted specifically to avoid breaking child button/badge text */
p, label, h1, h2, h3, h4, h5, h6 {{
    color: {COLORS["text_dark"]};
}}

/* ── Streamlit chrome ─────────────────────────────────────── */
#MainMenu, footer {{ visibility: hidden; }}
[data-testid="stDecoration"] {{ display: none !important; }}

/* Header is transparent, but sidebar toggle controls remain fully visible */
header[data-testid="stHeader"] {{
    background: transparent !important;
    visibility: visible !important;
    height: 3rem !important;
    z-index: 999 !important;
}}

/* Sidebar Re-Open Button (>>) when sidebar is collapsed */
[data-testid="collapsedControl"] {{
    display: flex !important;
    visibility: visible !important;
    background-color: {COLORS["pista_light"]} !important;
    border: 1.5px solid {COLORS["pista_deep"]} !important;
    border-radius: 8px !important;
    padding: 6px 8px !important;
    margin: 8px 0 0 14px !important;
    box-shadow: 0 2px 8px rgba(81, 72, 63, 0.18) !important;
    cursor: pointer !important;
    transition: all 0.2s ease-in-out !important;
}}
[data-testid="collapsedControl"]:hover {{
    background-color: {COLORS["pista"]} !important;
    transform: scale(1.05) !important;
}}
[data-testid="collapsedControl"] svg {{
    fill: {COLORS["text_dark"]} !important;
    stroke: {COLORS["text_dark"]} !important;
    color: {COLORS["text_dark"]} !important;
    width: 20px !important;
    height: 20px !important;
}}

/* Sidebar Collapse Button (<<) inside the sidebar */
[data-testid="stSidebarCollapseButton"] button {{
    background-color: {COLORS["pista_light"]} !important;
    border: 1px solid {COLORS["pista_deep"]} !important;
    border-radius: 6px !important;
    color: {COLORS["text_dark"]} !important;
}}
[data-testid="stSidebarCollapseButton"] button:hover {{
    background-color: {COLORS["pista"]} !important;
}}
[data-testid="stSidebarCollapseButton"] svg {{
    fill: {COLORS["text_dark"]} !important;
    stroke: {COLORS["text_dark"]} !important;
}}

/* ── Top Header Bar (Faint warm brown with white text) ─────── */
.top-header-bar {{
    background: linear-gradient(135deg, {COLORS["brown_header"]} 0%, {COLORS["brown_box"]} 100%);
    border-radius: 12px;
    padding: 18px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    box-shadow: 0 4px 14px rgba(81, 72, 63, 0.12);
}}
.top-header-title {{
    font-size: 1.4rem;
    font-weight: 800;
    color: #FFFFFF !important;
    letter-spacing: -0.01em;
    margin: 0;
}}
.top-header-sub {{
    font-size: 0.85rem;
    color: {COLORS["pista_light"]} !important;
    margin-top: 4px;
}}
.top-header-badge {{
    font-size: 0.76rem;
    font-weight: 700;
    padding: 6px 14px;
    border-radius: 20px;
    letter-spacing: 0.05em;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}}
.badge-ok   {{ background: {COLORS["pista_light"]}; color: {COLORS["pista_deep"]} !important; border: 1px solid {COLORS["pista"]}; }}
.badge-warn {{ background: #FFF4E5; color: #8A5300 !important; border: 1px solid #FFD188; }}
.badge-err  {{ background: #FFE8E8; color: #9A2020 !important; border: 1px solid #FFA8A8; }}

/* ── Sidebar ──────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: {COLORS["white"]} !important;
    border-right: 1.5px solid {COLORS["brown_border"]} !important;
    padding: 0 !important;
}}
[data-testid="stSidebarContent"] {{
    padding: 0 !important;
}}

.brand-block {{
    padding: 22px 20px 16px 20px;
    border-bottom: 1px solid {COLORS["brown_border"]};
    margin-bottom: 6px;
}}
.brand-name {{
    font-size: 1.3rem;
    font-weight: 800;
    color: {COLORS["pista_deep"]} !important;
    letter-spacing: 0.02em;
}}
.brand-sub {{
    font-size: 0.72rem;
    color: {COLORS["brown_faint"]} !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-top: 2px;
}}

/* ── Nav buttons in Sidebar ──────────────────────────────── */
[data-testid="stSidebar"] .stButton > button {{
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 10px 20px !important;
    border: none !important;
    border-radius: 0 !important;
    background: transparent !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    color: {COLORS["text_dark"]} !important;
    box-shadow: none !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background-color: {COLORS["pista_light"]} !important;
}}

/* ── KPI cards ───────────────────────────────────────────── */
.kpi-card {{
    background: {COLORS["white"]};
    border: 1px solid {COLORS["brown_border"]};
    border-radius: 12px;
    padding: 16px 16px 14px 16px;
    box-shadow: 0 1px 6px rgba(81, 72, 63, 0.06);
    position: relative;
    overflow: hidden;
    min-height: 128px;
}}
.kpi-card::after {{
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 3.5px;
    border-radius: 0 0 12px 12px;
}}
.kpi-card-pista::after   {{ background: {COLORS["pista"]}; }}
.kpi-card-brown::after   {{ background: {COLORS["brown_faint"]}; }}
.kpi-card-deep::after    {{ background: {COLORS["pista_deep"]}; }}
.kpi-card-amber::after   {{ background: {COLORS["amber_soft"]}; }}
.kpi-card-red::after     {{ background: {COLORS["red_soft"]}; }}
.kpi-card-blue::after    {{ background: {COLORS["blue_soft"]}; }}

.kpi-icon {{
    font-size: 1.25rem;
    margin-bottom: 6px;
    display: block;
}}
.kpi-label {{
    font-size: 0.70rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {COLORS["brown_faint"]} !important;
    margin-bottom: 4px;
}}
.kpi-value {{
    font-size: 1.55rem;
    font-weight: 800;
    color: {COLORS["text_dark"]} !important;
    line-height: 1.1;
}}
.kpi-note {{
    font-size: 0.72rem;
    color: {COLORS["brown_faint"]} !important;
    margin-top: 5px;
}}

/* ── Section titles ──────────────────────────────────────── */
.sec-title {{
    font-size: 0.82rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {COLORS["text_dark"]} !important;
    padding-bottom: 6px;
    margin: 22px 0 12px 0;
    border-bottom: 2px solid {COLORS["pista_light"]};
}}

/* ── Chart cards ─────────────────────────────────────────── */
.chart-card {{
    background: {COLORS["white"]};
    border: 1px solid {COLORS["brown_border"]};
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 1px 6px rgba(81,72,63,0.05);
    margin-bottom: 16px;
}}

/* ── Notification Banners ────────────────────────────────── */
.banner {{
    border-radius: 8px;
    padding: 12px 16px;
    margin: 12px 0;
    font-size: 0.84rem;
    color: {COLORS["text_dark"]} !important;
    border-left: 4px solid;
}}
.banner-pista  {{ background: #EDF4E7; border-color: {COLORS["pista"]}; }}
.banner-amber  {{ background: #FFF7EB; border-color: #E2B258; }}
.banner-rose   {{ background: #FDEEEE; border-color: #D27878; }}
.banner-blue   {{ background: #EFF4FA; border-color: #7AA2C8; }}
.banner strong {{ color: {COLORS["text_dark"]} !important; font-weight: 700; }}

/* ── Insight card ─────────────────────────────────────────── */
.insight-card {{
    background: #FAF6F0;
    border: 1.5px solid {COLORS["brown_border"]};
    border-left: 5px solid {COLORS["pista_deep"]};
    border-radius: 10px;
    padding: 14px 18px;
    margin: 14px 0 20px 0;
    font-size: 0.84rem;
    line-height: 1.5;
    box-shadow: 0 1px 5px rgba(81, 72, 63, 0.05);
}}
.insight-title {{
    font-size: 0.86rem;
    font-weight: 800;
    color: {COLORS["pista_deep"]};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
}}

/* ── Side-by-side transaction inspector ──────────────────── */
.inspector-card {{
    background: {COLORS["white"]};
    border: 1.5px solid {COLORS["brown_border"]};
    border-radius: 12px;
    padding: 18px 20px;
    margin: 14px 0 20px 0;
    box-shadow: 0 2px 8px rgba(81, 72, 63, 0.06);
}}
.inspector-col {{
    background: #FAF8F5;
    border: 1px solid {COLORS["brown_border"]};
    border-radius: 8px;
    padding: 14px;
}}
.inspector-label {{
    font-size: 0.70rem;
    font-weight: 700;
    color: {COLORS["brown_faint"]};
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.inspector-val {{
    font-size: 0.88rem;
    font-weight: 700;
    color: {COLORS["text_dark"]};
    margin-bottom: 8px;
}}

/* ── Recon summary boxes ─────────────────────────────────── */
.recon-box {{
    background: {COLORS["white"]};
    border: 1px solid {COLORS["brown_border"]};
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
}}
.recon-box-label {{
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {COLORS["brown_faint"]} !important;
    margin-bottom: 4px;
}}
.recon-box-val {{
    font-size: 1.3rem;
    font-weight: 800;
    color: {COLORS["text_dark"]} !important;
}}

/* ── Primary & Secondary Buttons ─────────────────────────── */
.stButton > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button {{
    background-color: {COLORS["pista_deep"]} !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
    padding: 10px 26px !important;
    box-shadow: 0 2px 6px rgba(130, 150, 106, 0.3) !important;
}}
.stButton > button[kind="primary"]:hover {{
    background-color: {COLORS["pista"]} !important;
    color: {COLORS["text_dark"]} !important;
}}

.stDownloadButton > button {{
    background-color: {COLORS["pista_light"]} !important;
    color: {COLORS["pista_deep"]} !important;
    border: 1px solid {COLORS["pista_border"]} !important;
    border-radius: 7px !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
}}
.stDownloadButton > button:hover {{
    background-color: {COLORS["pista"]} !important;
    color: {COLORS["text_dark"]} !important;
}}

/* ── STREAMLIT DATAFRAME & TABLE OVERRIDES (HIGH CONTRAST) ── */
[data-testid="stDataFrame"] {{
    border: 1.5px solid {COLORS["brown_border"]} !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    background-color: {COLORS["white"]} !important;
}}

/* Glide Data Grid header background in faint brown with white text */
[data-testid="stDataFrame"] th,
.dvn-scroller th,
.dvn-header-cell {{
    background-color: {COLORS["brown_box"]} !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
}}

/* Dataframe Floating Toolbar (Upper Right Corner) */
div[data-testid="stElementToolbar"],
div[data-testid="stDataFrameToolbar"],
div[class*="toolbar"] {{
    background-color: {COLORS["brown_box"]} !important;
    border: 1px solid {COLORS["brown_header"]} !important;
    border-radius: 8px !important;
    padding: 3px 6px !important;
    box-shadow: 0 3px 10px rgba(81, 72, 63, 0.28) !important;
    opacity: 1 !important;
    visibility: visible !important;
}}

div[data-testid="stElementToolbar"] button,
div[data-testid="stDataFrameToolbar"] button,
div[class*="toolbar"] button {{
    background-color: {COLORS["brown_mid"]} !important;
    border: 1px solid rgba(255, 255, 255, 0.25) !important;
    border-radius: 6px !important;
    margin: 0 2px !important;
}}

div[data-testid="stElementToolbar"] button:hover,
div[data-testid="stDataFrameToolbar"] button:hover,
div[class*="toolbar"] button:hover {{
    background-color: {COLORS["pista"]} !important;
}}

/* High visibility icons inside toolbar (eye, download, search, expand) */
div[data-testid="stElementToolbar"] svg,
div[data-testid="stDataFrameToolbar"] svg,
div[data-testid="stElementToolbar"] svg *,
div[data-testid="stDataFrameToolbar"] svg * {{
    fill: #FFFFFF !important;
    stroke: #FFFFFF !important;
    color: #FFFFFF !important;
}}

div[data-testid="stElementToolbar"] button:hover svg,
div[data-testid="stDataFrameToolbar"] button:hover svg,
div[data-testid="stElementToolbar"] button:hover svg *,
div[data-testid="stDataFrameToolbar"] button:hover svg * {{
    fill: {COLORS["text_dark"]} !important;
    stroke: {COLORS["text_dark"]} !important;
    color: {COLORS["text_dark"]} !important;
}}

/* Tooltip Popups (e.g. "Download as CSV", "Show/hide columns") - WHITE TEXT ON DARK BROWN */
div[data-baseweb="tooltip"],
div[role="tooltip"],
div[data-testid="stTooltipContent"],
div[class*="StyledTooltip"],
div[class*="tooltip"] {{
    background-color: {COLORS["brown_header"]} !important;
    color: #FFFFFF !important;
    border: 1px solid {COLORS["brown_border"]} !important;
    border-radius: 6px !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(81, 72, 63, 0.35) !important;
    padding: 5px 10px !important;
}}

div[data-baseweb="tooltip"] *,
div[role="tooltip"] *,
div[data-testid="stTooltipContent"] *,
div[class*="StyledTooltip"] * {{
    background-color: transparent !important;
    color: #FFFFFF !important;
}}

/* ── Selectboxes & Inputs ────────────────────────────────── */
[data-baseweb="select"] > div {{
    background-color: {COLORS["white"]} !important;
    border: 1px solid {COLORS["brown_border"]} !important;
    border-radius: 7px !important;
}}
[data-baseweb="popover"],
[data-baseweb="menu"],
[role="listbox"] {{
    background-color: {COLORS["white"]} !important;
}}
[data-baseweb="popover"] *,
[data-baseweb="menu"] *,
[role="listbox"] * {{
    background-color: {COLORS["white"]} !important;
    color: {COLORS["text_dark"]} !important;
}}
[role="option"]:hover,
[role="option"][aria-selected="true"] {{
    background-color: {COLORS["pista_light"]} !important;
    color: {COLORS["text_dark"]} !important;
}}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {{
    background-color: {COLORS["white"]} !important;
    color: {COLORS["text_dark"]} !important;
    border: 1px solid {COLORS["brown_border"]} !important;
    border-radius: 7px !important;
}}

/* ── Tabs ─────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    background: {COLORS["beige_light"]} !important;
    border-radius: 8px !important;
    padding: 3px !important;
    gap: 3px !important;
    border: 1px solid {COLORS["brown_border"]} !important;
}}
[data-testid="stTabs"] [data-baseweb="tab"] {{
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    color: {COLORS["text_dark"]} !important;
    padding: 7px 14px !important;
    border-radius: 6px !important;
    background: transparent !important;
}}
[data-testid="stTabs"] [aria-selected="true"] {{
    background: {COLORS["pista"]} !important;
    color: {COLORS["text_dark"]} !important;
    box-shadow: 0 1px 4px rgba(100,130,80,0.2) !important;
}}
[data-testid="stTabs"] [aria-selected="true"] p {{
    color: {COLORS["text_dark"]} !important;
    font-weight: 700 !important;
}}

/* ── Sidebar Status Card ─────────────────────────────────── */
.sidebar-status-box {{
    margin: 14px 16px 0 16px;
    padding: 12px 14px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 600;
}}
.status-synth {{
    background: {COLORS["pista_light"]};
    border: 1px solid {COLORS["pista"]};
    color: {COLORS["pista_deep"]} !important;
}}
.status-upload {{
    background: #EFF4FA;
    border: 1px solid #98B8D8;
    color: #2D5880 !important;
}}
.status-empty {{
    background: {COLORS["beige_light"]};
    border: 1px solid {COLORS["brown_border"]};
    color: {COLORS["brown_faint"]} !important;
}}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# SESSION STATE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        "active_page":      "overview",
        "recon_month":      "2026-10",
        "tolerance":        Decimal("0.05"),
        "source_mode":      "synthetic",     # 'synthetic' or 'uploaded'
        # Data for Synthetic
        "synth_platform_df": None,
        "synth_bank_df":     None,
        "synth_summary":     None,
        "synth_rec_df":      None,
        "synth_exc_df":      None,
        # Data for Uploaded
        "user_platform_df":  None,
        "user_bank_df":      None,
        "user_summary":      None,
        "user_rec_df":       None,
        "user_exc_df":       None,
        "user_recon_run":    False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ═══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════
def load_sample_dataset(month: str = "2026-10"):
    """Generate and reconcile synthetic data for the given month."""
    p_df, b_df = generate_synthetic_data(num_records=50, month=month, seed=42)
    st.session_state["synth_platform_df"] = p_df
    st.session_state["synth_bank_df"]     = b_df
    
    engine = ReconciliationEngine(
        reconciliation_month=month,
        rounding_tolerance=st.session_state["tolerance"],
    )
    summary, rec_df, exc_df = engine.reconcile(p_df, b_df)
    st.session_state["synth_summary"] = summary
    st.session_state["synth_rec_df"]  = rec_df
    st.session_state["synth_exc_df"]  = exc_df
    st.session_state["recon_month"]   = month


def get_current_data():
    """Retrieve active platform_df, bank_df, summary, rec_df, exc_df based on source_mode."""
    mode = st.session_state["source_mode"]
    if mode == "uploaded":
        return (
            st.session_state["user_platform_df"],
            st.session_state["user_bank_df"],
            st.session_state["user_summary"],
            st.session_state["user_rec_df"],
            st.session_state["user_exc_df"],
        )
    else:
        # If synthetic data not yet loaded, load it
        if st.session_state["synth_platform_df"] is None:
            load_sample_dataset(st.session_state["recon_month"])
        return (
            st.session_state["synth_platform_df"],
            st.session_state["synth_bank_df"],
            st.session_state["synth_summary"],
            st.session_state["synth_rec_df"],
            st.session_state["synth_exc_df"],
        )


def render_styled_dataframe(df: pd.DataFrame, height: int = 320):
    """Render dataframe with faint-brown header and high-contrast visible text."""
    if df is None or df.empty:
        st.info("No records to display.")
        return

    # Prepare formatted copy for display
    display_df = df.copy()
    format_dict = {}
    money_cols = [
        "platform_amount", "bank_settlement_amount", "difference",
        "Expected Amount (INR)", "Actual Amount (INR)", "Difference (INR)",
        "amount", "settlement_amount", "Platform Amount (INR)", "Bank Amount (INR)"
    ]
    for c in money_cols:
        if c in display_df.columns:
            format_dict[c] = "₹{:,.2f}"

    styled = display_df.style.set_table_styles([
        {
            "selector": "thead th",
            "props": [
                ("background-color", f"{COLORS['brown_box']} !important"),
                ("color", "#FFFFFF !important"),
                ("font-weight", "700"),
                ("font-size", "0.78rem"),
                ("text-transform", "uppercase"),
                ("letter-spacing", "0.05em"),
                ("padding", "9px 12px"),
                ("border", "none")
            ]
        },
        {
            "selector": "tbody td",
            "props": [
                ("color", f"{COLORS['text_dark']} !important"),
                ("font-size", "0.82rem"),
                ("padding", "7px 12px")
            ]
        },
        {
            "selector": "tbody tr:nth-child(even)",
            "props": [("background-color", "#FAF8F5 !important")]
        },
        {
            "selector": "tbody tr:nth-child(odd)",
            "props": [("background-color", "#FFFFFF !important")]
        },
        {
            "selector": "tbody tr:hover",
            "props": [("background-color", f"{COLORS['pista_light']} !important")]
        }
    ])

    if format_dict:
        styled = styled.format(format_dict)

    st.dataframe(styled, use_container_width=True, hide_index=True, height=height)


def kpi_box(col, icon, label, value, note, accent_class="kpi-card-pista"):
    with col:
        st.markdown(f"""
        <div class="kpi-card {accent_class}">
            <span class="kpi-icon">{icon}</span>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-note">{note}</div>
        </div>""", unsafe_allow_html=True)


def plotly_theme(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, -apple-system, sans-serif", color=COLORS["text_dark"], size=11),
        margin=dict(l=10, r=10, t=32, b=10),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor=COLORS["brown_border"],
            borderwidth=1,
            font=dict(size=10, color=COLORS["text_dark"]),
        ),
    )
    fig.update_xaxes(gridcolor=COLORS["pista_light"], linecolor=COLORS["brown_border"], tickfont=dict(color=COLORS["text_dark"]))
    fig.update_yaxes(gridcolor=COLORS["pista_light"], linecolor=COLORS["brown_border"], tickfont=dict(color=COLORS["text_dark"]))
    return fig


def render_transaction_inspector(rec_df: pd.DataFrame, key_prefix: str = "insp"):
    """
    Renders an interactive Side-by-Side Transaction Investigation Card
    comparing Platform Record vs Bank Settlement Record for any selected Transaction ID.
    """
    if rec_df is None or rec_df.empty:
        return

    st.markdown('<div class="sec-title">🔍 Side-by-Side Transaction Investigation View</div>', unsafe_allow_html=True)
    
    # Selection dropdown
    tx_list = rec_df["transaction_id"].dropna().unique().tolist()
    if not tx_list:
        return

    selected_tx = st.selectbox(
        "Select Transaction to Investigate",
        options=tx_list,
        key=f"{key_prefix}_select_tx"
    )

    row = rec_df[rec_df["transaction_id"] == selected_tx].iloc[0]

    p_amt = row.get("platform_amount", Decimal("0.00"))
    b_amt = row.get("bank_settlement_amount", Decimal("0.00"))
    diff = row.get("difference", Decimal("0.00"))
    status = row.get("reconciliation_status", "UNKNOWN")
    reason = row.get("reason_for_mismatch", "Record matched within operational parameters.")
    action = row.get("recommended_action", "No adjustment required.")
    severity = row.get("severity", "LOW")

    sev_badge_class = "badge-ok" if severity == "LOW" else ("badge-warn" if severity == "MEDIUM" else "badge-err")

    col_plat, col_bank = st.columns(2, gap="medium")

    with col_plat:
        st.markdown(f"""
        <div class="inspector-col">
            <div style="font-weight:800; font-size:0.86rem; color:{COLORS['pista_deep']}; text-transform:uppercase; margin-bottom:10px;">
                🏦 Platform Ledger Record
            </div>
            <div class="inspector-label">Transaction ID</div>
            <div class="inspector-val">{row.get('transaction_id', 'N/A')}</div>
            <div class="inspector-label">Transaction Date & Time</div>
            <div class="inspector-val">{row.get('transaction_date', 'N/A')}</div>
            <div class="inspector-label">Customer ID / User</div>
            <div class="inspector-val">{row.get('customer_id', 'N/A')}</div>
            <div class="inspector-label">Payment Method</div>
            <div class="inspector-val">{row.get('payment_method', 'N/A')}</div>
            <div class="inspector-label">Platform Recorded Amount</div>
            <div class="inspector-val" style="font-size:1.1rem; color:{COLORS['text_dark']};">{format_inr(to_decimal(p_amt))}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_bank:
        st.markdown(f"""
        <div class="inspector-col">
            <div style="font-weight:800; font-size:0.86rem; color:{COLORS['brown_box']}; text-transform:uppercase; margin-bottom:10px;">
                🏛️ Bank Settlement Record
            </div>
            <div class="inspector-label">Settlement Reference (UTR)</div>
            <div class="inspector-val">{row.get('bank_reference', 'N/A') or 'N/A (No bank reference)'}</div>
            <div class="inspector-label">Settlement Date</div>
            <div class="inspector-val">{row.get('settlement_date', 'N/A') or 'N/A (Unsettled)'}</div>
            <div class="inspector-label">Settlement Batch ID</div>
            <div class="inspector-val">{row.get('settlement_id', 'N/A') or 'N/A'}</div>
            <div class="inspector-label">Bank Settlement Status</div>
            <div class="inspector-val">{row.get('settlement_status', 'N/A') or 'N/A'}</div>
            <div class="inspector-label">Bank Settled Amount</div>
            <div class="inspector-val" style="font-size:1.1rem; color:{COLORS['text_dark']};">{format_inr(to_decimal(b_amt))}</div>
        </div>
        """, unsafe_allow_html=True)

    # Determination banner
    st.markdown(f"""
    <div class="inspector-card" style="margin-top:12px; background:#FAF8F5;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <div>
                <strong style="text-transform:uppercase; font-size:0.75rem; color:{COLORS['brown_faint']};">Reconciliation Determination:</strong>
                <span style="font-size:0.95rem; font-weight:800; color:{COLORS['text_dark']}; margin-left:8px;">{status}</span>
            </div>
            <div>
                <span class="top-header-badge {sev_badge_class}">Severity: {severity}</span>
            </div>
        </div>
        <div style="font-size:0.84rem; color:{COLORS['text_dark']}; margin-bottom:6px;">
            <strong>Amount Variance (Platform − Bank):</strong> <code>{format_inr(to_decimal(diff))}</code>
        </div>
        <div style="font-size:0.82rem; color:{COLORS['text_dark']}; margin-bottom:4px;">
            <strong>Root Cause Analysis:</strong> {reason}
        </div>
        <div style="font-size:0.82rem; color:{COLORS['pista_deep']};">
            <strong>Recommended Action:</strong> {action}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div class="brand-block">
        <div class="brand-name">⚖️ {APP_NAME}</div>
        <div class="brand-sub">{APP_SUBTITLE}</div>
    </div>
    """, unsafe_allow_html=True)

    # Navigation menu
    for page_key, label, icon in NAV_ITEMS:
        active = st.session_state["active_page"] == page_key
        if st.button(f"{icon}  {label}", key=f"nav_{page_key}", use_container_width=True):
            st.session_state["active_page"] = page_key
            st.rerun()

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.divider()

    # Active Reconciliation Period
    st.markdown("**📅 Reconciliation Period**")
    current_period = st.session_state["recon_month"]
    selected_period = st.selectbox(
        "Period",
        options=["2026-10", "2026-09", "2026-08", "2026-11", "Custom"],
        index=0 if current_period == "2026-10" else (1 if current_period == "2026-09" else (2 if current_period == "2026-08" else 0)),
        label_visibility="collapsed",
    )
    if selected_period == "Custom":
        custom_input = st.text_input("Enter YYYY-MM", value=current_period)
        if custom_input != current_period:
            st.session_state["recon_month"] = custom_input
            if st.session_state["source_mode"] == "synthetic":
                load_sample_dataset(custom_input)
                st.rerun()
    elif selected_period != current_period:
        st.session_state["recon_month"] = selected_period
        if st.session_state["source_mode"] == "synthetic":
            load_sample_dataset(selected_period)
            st.rerun()

    # Rounding tolerance
    st.markdown("**🪙 Rounding Tolerance (₹)**")
    tol_val = st.number_input(
        "Tolerance",
        min_value=0.01, max_value=1.00,
        value=float(st.session_state["tolerance"]), step=0.01,
        label_visibility="collapsed",
        help="Variances at or below this amount are classified as paise rounding differences.",
    )
    st.session_state["tolerance"] = Decimal(str(tol_val))

    st.divider()

    # Data Mode Status Pill
    mode = st.session_state["source_mode"]
    if mode == "uploaded" and st.session_state["user_recon_run"]:
        st.markdown(f"""
        <div class="sidebar-status-box status-upload">
            📤 Custom Files Loaded<br>
            <span style='font-size:0.7rem; font-weight:400;'>Period: {st.session_state['recon_month']}</span>
        </div>""", unsafe_allow_html=True)
    elif mode == "uploaded" and not st.session_state["user_recon_run"]:
        st.markdown("""
        <div class="sidebar-status-box status-empty">
            ⏳ Files Uploaded (Pending Recon)<br>
            <span style='font-size:0.7rem; font-weight:400;'>Click 'Run Reconciliation'</span>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="sidebar-status-box status-synth">
            🧪 Sample Data Active<br>
            <span style='font-size:0.7rem; font-weight:400;'>Period: {st.session_state['recon_month']} · 4 planted gaps</span>
        </div>""", unsafe_allow_html=True)

    st.markdown(
        f"<p style='text-align:center; font-size:0.7rem; color:{COLORS['brown_faint']}; margin-top:20px;'>"
        "PaySync · INR Financial Operations</p>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ═══════════════════════════════════════════════════════════════════
def page_overview():
    p_df, b_df, summary, rec_df, exc_df = get_current_data()
    month = st.session_state["recon_month"]

    if summary is None:
        st.markdown(f"""
        <div class="top-header-bar">
            <div>
                <div class="top-header-title">Payment Reconciliation Overview</div>
                <div class="top-header-sub">Automated month-end ledger matching &amp; discrepancy diagnostics</div>
            </div>
            <div>
                <span class="top-header-badge badge-warn">⏳ Awaiting Reconciliation</span>
            </div>
        </div>
        <div class="banner banner-amber">
            No reconciliation executed for <strong>{month}</strong> yet. Go to the <strong>Reconciliation</strong> page to upload files or load sample data.
        </div>""", unsafe_allow_html=True)
        return

    exc_count = summary.total_exceptions_count
    status_badge = (
        '<span class="top-header-badge badge-ok">✓ Balanced (No Exceptions)</span>' if exc_count == 0
        else f'<span class="top-header-badge badge-warn">⚠️ {exc_count} Exceptions Detected</span>'
    )

    st.markdown(f"""
    <div class="top-header-bar">
        <div>
            <div class="top-header-title">Payment Reconciliation Overview</div>
            <div class="top-header-sub">
                Reconciliation Period: <strong>{month}</strong> &nbsp;·&nbsp; Source: <strong>{'User Uploaded CSV' if st.session_state['source_mode'] == 'uploaded' else 'Synthetic Test Data'}</strong>
            </div>
        </div>
        <div>{status_badge}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── DYNAMIC RECONCILIATION INSIGHT ──────────────────────────────
    st.markdown(f"""
    <div class="insight-card">
        <div class="insight-title">📊 Executive Reconciliation Summary &amp; Auditor Insight</div>
        Platform recorded <strong>{summary.raw_platform_count}</strong> transactions ({summary.unique_platform_count} unique IDs) totaling <strong>{format_inr(summary.total_platform_amount)}</strong>, 
        against <strong>{summary.raw_bank_count}</strong> bank settlement receipts totaling <strong>{format_inr(summary.total_bank_amount)}</strong>.<br>
        • <strong>Match Performance:</strong> {summary.matched_count} records ({summary.match_rate_percentage:.1f}%) settled cleanly (Exact: {summary.matched_exact_count}, Line Variance: {summary.matched_variance_count}).<br>
        • <strong>In-Transit Float:</strong> {summary.timing_difference_count} transactions ({format_inr(summary.timing_difference_amount)}) settled in the following month (normal T+1/T+2 cycle, not missing).<br>
        • <strong>Net Variance:</strong> {format_inr(summary.net_reconciliation_difference)} net difference between platform and bank books.<br>
        • <strong>Action Items:</strong> {summary.total_exceptions_count} items with <strong>{format_inr(summary.gross_exception_exposure)}</strong> gross exposure require accounting adjustments (Duplicates: {summary.duplicate_count}, Orphan Refunds: {summary.orphan_refund_count}, Missing: {summary.unsettled_count}).
    </div>
    """, unsafe_allow_html=True)

    # ── 6 KPI CARDS (2 BALANCED ROWS) ────────────────────────────────
    k1, k2, k3 = st.columns(3)
    kpi_box(
        k1, "🏦", "Total Platform Transactions",
        format_inr(summary.total_platform_amount),
        f"{summary.raw_platform_count} records · {summary.unique_platform_count} unique IDs",
        "kpi-card-brown"
    )
    kpi_box(
        k2, "🏛️", "Total Bank Settlements",
        format_inr(summary.total_bank_amount),
        f"{summary.raw_bank_count} records · {summary.unique_bank_count} unique UTRs",
        "kpi-card-pista"
    )
    kpi_box(
        k3, "✅", "Successfully Matched",
        f"{summary.matched_count}",
        f"{summary.match_rate_percentage:.1f}% match rate · {format_inr(summary.matched_amount)} (Exact: {summary.matched_exact_count})",
        "kpi-card-deep"
    )

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    k4, k5, k6 = st.columns(3)
    net_diff = summary.net_reconciliation_difference
    net_sign = "+" if net_diff > Decimal("0.00") else ""
    kpi_box(
        k4, "⚖️", "Net Reconciliation Difference",
        f"{net_sign}{format_inr(net_diff)}",
        "Platform Total − Bank Total (Float + Missing)",
        "kpi-card-amber"
    )
    kpi_box(
        k5, "⏱️", "Settled After Period End",
        format_inr(summary.timing_difference_amount),
        f"{summary.timing_difference_count} transactions · In-transit timing float",
        "kpi-card-blue"
    )
    kpi_box(
        k6, "⚠️", "Gross Exception Exposure",
        format_inr(summary.gross_exception_exposure),
        f"{summary.total_exceptions_count} exceptions requiring review",
        "kpi-card-red"
    )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # ── CHARTS ROW 1 ─────────────────────────────────────────────────
    st.markdown('<div class="sec-title">Financial Trends &amp; Distribution</div>', unsafe_allow_html=True)
    c_trend, c_donut = st.columns([1.4, 1], gap="medium")

    with c_trend:
        # Daily platform vs bank line chart
        p_temp = p_df.copy()
        p_temp["date"] = pd.to_datetime(p_temp["transaction_date"], errors="coerce").dt.date
        daily_p = p_temp.groupby("date")["amount"].sum().reset_index().rename(columns={"amount": "platform_amt"})

        b_temp = rec_df[rec_df["bank_settlement_amount"] > 0].copy()
        b_temp["date"] = pd.to_datetime(b_temp["settlement_date"], errors="coerce").dt.date
        daily_b = b_temp.groupby("date")["bank_settlement_amount"].sum().reset_index()

        daily_merged = daily_p.merge(daily_b, on="date", how="outer").sort_values("date").fillna(0)

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=daily_merged["date"], y=daily_merged["platform_amt"],
            name="Platform Transactions",
            line=dict(color=COLORS["pista_deep"], width=2.5),
            fill="tozeroy", fillcolor="rgba(130, 150, 106, 0.12)",
            hovertemplate="Platform: ₹%{y:,.2f}<extra></extra>",
        ))
        fig_trend.add_trace(go.Scatter(
            x=daily_merged["date"], y=daily_merged["bank_settlement_amount"],
            name="Bank Settlements",
            line=dict(color=COLORS["brown_faint"], width=2.5, dash="dot"),
            fill="tozeroy", fillcolor="rgba(184, 161, 138, 0.08)",
            hovertemplate="Bank: ₹%{y:,.2f}<extra></extra>",
        ))
        fig_trend.update_layout(
            title=dict(text="Transaction and Settlement Trend", font=dict(size=12, color=COLORS["text_dark"])),
            height=280, hovermode="x unified",
            xaxis_title="Date", yaxis_title="Amount (₹)",
        )
        plotly_theme(fig_trend)
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with c_donut:
        # Donut Chart
        labels = ["Matched", "Delayed (Next-Month)", "Rounding Diff", "Duplicates", "Orphan Refunds", "Unsettled", "Unmatched Bank"]
        vals = [
            summary.matched_count,
            summary.timing_difference_count,
            summary.rounding_difference_count,
            summary.duplicate_count,
            summary.orphan_refund_count,
            summary.unsettled_count,
            summary.unmatched_bank_count,
        ]
        colors_donut = [
            COLORS["pista_deep"], COLORS["pista"],
            COLORS["amber_soft"], COLORS["red_soft"],
            COLORS["lavender"], COLORS["brown_faint"], COLORS["blue_soft"],
        ]
        fig_donut = go.Figure(go.Pie(
            labels=labels, values=vals, hole=0.55,
            marker=dict(colors=colors_donut, line=dict(color=COLORS["white"], width=2)),
            textfont=dict(size=10, color=COLORS["text_dark"]),
            hovertemplate="<b>%{label}</b><br>Count: %{value} (%{percent})<extra></extra>",
        ))
        fig_donut.update_layout(
            title=dict(text="Reconciliation Status Distribution", font=dict(size=12, color=COLORS["text_dark"])),
            height=280, showlegend=True,
            legend=dict(font=dict(size=9), orientation="v"),
            annotations=[dict(
                text=f"<b>{summary.raw_platform_count}</b><br><span style='font-size:9px'>Total</span>",
                x=0.5, y=0.5, font=dict(size=13, color=COLORS["text_dark"]),
                showarrow=False,
            )],
        )
        plotly_theme(fig_donut)
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    # ── CHARTS ROW 2 ─────────────────────────────────────────────────
    st.markdown('<div class="sec-title">Exception Breakdown</div>', unsafe_allow_html=True)
    c_bar, c_daily_exc = st.columns([1, 1.2], gap="medium")

    with c_bar:
        # Horizontal bar chart
        cat_counts = {
            "Next-Month Settlement": summary.timing_difference_count,
            "Rounding Difference":   summary.rounding_difference_count,
            "Duplicate Entry":       summary.duplicate_count,
            "Orphan Refund":         summary.orphan_refund_count,
            "Unsettled / Missing":   summary.unsettled_count,
            "Unmatched Bank Credit": summary.unmatched_bank_count,
        }
        bar_df = pd.DataFrame(list(cat_counts.items()), columns=["Category", "Count"])
        bar_df = bar_df[bar_df["Count"] > 0]

        fig_bar = go.Figure(go.Bar(
            x=bar_df["Count"], y=bar_df["Category"], orientation="h",
            marker=dict(
                color=bar_df["Count"],
                colorscale=[[0, COLORS["pista_light"]], [1, COLORS["pista_deep"]]],
                showscale=False,
            ),
            text=bar_df["Count"], textposition="outside",
            textfont=dict(color=COLORS["text_dark"], size=11),
            hovertemplate="<b>%{y}</b>: %{x} items<extra></extra>",
        ))
        fig_bar.update_layout(
            title=dict(text="Exception Category Breakdown", font=dict(size=12, color=COLORS["text_dark"])),
            height=260, xaxis_title="Exceptions", yaxis=dict(autorange="reversed"),
        )
        plotly_theme(fig_bar)
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with c_daily_exc:
        # Daily exception trend
        if exc_df is not None and not exc_df.empty:
            e_temp = exc_df.copy()
            e_temp["date"] = pd.to_datetime(e_temp["Transaction Date"], errors="coerce").dt.date
            daily_e = e_temp.dropna(subset=["date"]).groupby("date").size().reset_index(name="count").sort_values("date")

            fig_daily = go.Figure(go.Scatter(
                x=daily_e["date"], y=daily_e["count"],
                mode="lines+markers",
                fill="tozeroy", fillcolor="rgba(183, 201, 154, 0.2)",
                line=dict(color=COLORS["pista_deep"], width=2.5),
                marker=dict(color=COLORS["pista_deep"], size=6),
                hovertemplate="<b>Date:</b> %{x}<br><b>Exceptions:</b> %{y}<extra></extra>",
            ))
            fig_daily.update_layout(
                title=dict(text="Daily Exception Trend", font=dict(size=12, color=COLORS["text_dark"])),
                height=260, xaxis_title="Date", yaxis_title="Exception Count",
            )
            plotly_theme(fig_daily)
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.plotly_chart(fig_daily, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)

    # ── SIDE-BY-SIDE TRANSACTION INSPECTOR ───────────────────────────
    render_transaction_inspector(rec_df, key_prefix="ov_inspector")

    # ── RECENT EXCEPTIONS TABLE ──────────────────────────────────────
    st.markdown('<div class="sec-title">Recent Exceptions Table</div>', unsafe_allow_html=True)
    if exc_df is not None and not exc_df.empty:
        f_type, f_sev = st.columns([1.5, 1])
        with f_type:
            types_opt = ["All"] + sorted(exc_df["Exception Type"].unique().tolist())
            sel_type = st.selectbox("Filter: Exception Type", types_opt, key="ov_sel_type")
        with f_sev:
            sevs_opt = ["All"] + sorted(exc_df["Severity"].unique().tolist())
            sel_sev = st.selectbox("Filter: Severity", sevs_opt, key="ov_sel_sev")

        tbl_filtered = exc_df.copy()
        if sel_type != "All":
            tbl_filtered = tbl_filtered[tbl_filtered["Exception Type"] == sel_type]
        if sel_sev != "All":
            tbl_filtered = tbl_filtered[tbl_filtered["Severity"] == sel_sev]

        cols_show = ["Transaction ID", "Exception Type", "Expected Amount (INR)", "Actual Amount (INR)",
                     "Difference (INR)", "Transaction Date", "Settlement Date", "Severity", "Recommended Action"]
        cols_show = [c for c in cols_show if c in tbl_filtered.columns]

        render_styled_dataframe(tbl_filtered[cols_show], height=260)
    else:
        st.info("No exceptions detected for this reconciliation period.")


# ═══════════════════════════════════════════════════════════════════
# PAGE: RECONCILIATION (STRICT SEPARATION OF MODES)
# ═══════════════════════════════════════════════════════════════════
def page_reconciliation():
    st.markdown(f"""
    <div class="top-header-bar">
        <div>
            <div class="top-header-title">⚖️ Reconciliation Engine</div>
            <div class="top-header-sub">Configure and execute month-end matching between platform and bank records</div>
        </div>
        <div>
            <span class="top-header-badge badge-ok">Active Period: {st.session_state['recon_month']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Mode Selector
    recon_mode = st.radio(
        "Choose Ingestion Mode",
        options=["📤 Upload My Files", "🧪 Use Sample Demo Data"],
        index=0 if st.session_state["source_mode"] == "uploaded" else 1,
        horizontal=True,
    )

    st.markdown("<hr style='border:none; border-top:1.5px solid #D0C4B4; margin:16px 0 20px 0;'>", unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────
    # MODE 1: UPLOAD MY FILES
    # ─────────────────────────────────────────────────────────────
    if "Upload My Files" in recon_mode:
        st.session_state["source_mode"] = "uploaded"

        st.markdown('<div class="sec-title">Step 1 — Upload Datasets &amp; Templates</div>', unsafe_allow_html=True)
        
        # Downloadable CSV templates
        c_tpl1, c_tpl2 = st.columns(2)
        with c_tpl1:
            st.download_button(
                "📥  Download Platform CSV Template",
                data=get_sample_platform_template_csv(),
                file_name="platform_transactions_template.csv",
                mime="text/csv",
                use_container_width=True,
                help="Download sample CSV format expected for platform transaction history.",
            )
        with c_tpl2:
            st.download_button(
                "📥  Download Bank Settlement CSV Template",
                data=get_sample_bank_template_csv(),
                file_name="bank_settlements_template.csv",
                mime="text/csv",
                use_container_width=True,
                help="Download sample CSV format expected for bank settlement statements.",
            )

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        col_up1, col_up2 = st.columns(2, gap="medium")

        with col_up1:
            st.markdown(f"""
            <div style="background:{COLORS['white']}; border:1.5px solid {COLORS['brown_border']}; border-radius:10px; padding:16px;">
                <strong style="color:{COLORS['pista_deep']}; text-transform:uppercase; font-size:0.78rem;">Platform Transactions CSV</strong>
                <p style="font-size:0.75rem; color:{COLORS['brown_faint']}; margin:4px 0 8px 0;">Required columns: <code>transaction_id</code>, <code>transaction_date</code>, <code>amount</code></p>
            </div>
            """, unsafe_allow_html=True)
            u_p = st.file_uploader("Upload Platform CSV", type=["csv"], key="user_p_upload", label_visibility="collapsed")

        with col_up2:
            st.markdown(f"""
            <div style="background:{COLORS['white']}; border:1.5px solid {COLORS['brown_border']}; border-radius:10px; padding:16px;">
                <strong style="color:{COLORS['pista_deep']}; text-transform:uppercase; font-size:0.78rem;">Bank Settlements CSV</strong>
                <p style="font-size:0.75rem; color:{COLORS['brown_faint']}; margin:4px 0 8px 0;">Required columns: <code>settlement_id</code>, <code>settlement_date</code>, <code>settlement_amount</code></p>
            </div>
            """, unsafe_allow_html=True)
            u_b = st.file_uploader("Upload Bank CSV", type=["csv"], key="user_b_upload", label_visibility="collapsed")

        p_valid = False
        b_valid = False

        if u_p is not None:
            try:
                df_p = pd.read_csv(u_p)
                req_p = {"transaction_id", "transaction_date", "amount"}
                missing_p = req_p - set(df_p.columns)
                if missing_p:
                    st.error(f"Platform CSV missing required columns: {missing_p}")
                else:
                    st.session_state["user_platform_df"] = df_p
                    p_valid = True
                    st.success(f"✓ Platform CSV: {len(df_p)} rows loaded. Total amount: ₹{pd.to_numeric(df_p['amount'], errors='coerce').sum():,.2f}")
            except Exception as e:
                st.error(f"Error reading Platform CSV: {e}")

        if u_b is not None:
            try:
                df_b = pd.read_csv(u_b)
                req_b = {"settlement_id", "settlement_date", "settlement_amount"}
                missing_b = req_b - set(df_b.columns)
                if missing_b:
                    st.error(f"Bank CSV missing required columns: {missing_b}")
                else:
                    st.session_state["user_bank_df"] = df_b
                    b_valid = True
                    st.success(f"✓ Bank CSV: {len(df_b)} settlements loaded. Total amount: ₹{pd.to_numeric(df_b['settlement_amount'], errors='coerce').sum():,.2f}")
            except Exception as e:
                st.error(f"Error reading Bank CSV: {e}")

        user_p = st.session_state.get("user_platform_df")
        user_b = st.session_state.get("user_bank_df")

        # Step 2: Configure
        st.markdown('<div class="sec-title">Step 2 — Configure Period &amp; Parameters</div>', unsafe_allow_html=True)
        cfg_c1, cfg_c2 = st.columns(2)
        with cfg_c1:
            detected_months = []
            if user_p is not None and "transaction_date" in user_p.columns:
                parsed_dates = pd.to_datetime(user_p["transaction_date"], errors="coerce").dropna()
                detected_months = sorted(parsed_dates.dt.strftime("%Y-%m").unique().tolist(), reverse=True)

            default_month = detected_months[0] if detected_months else st.session_state["recon_month"]
            period_input = st.text_input("Reconciliation Period (YYYY-MM)", value=default_month, key="user_month_input")
            st.session_state["recon_month"] = period_input

        with cfg_c2:
            tol_input = st.number_input(
                "Rounding Tolerance (₹)",
                min_value=0.01, max_value=1.00,
                value=float(st.session_state["tolerance"]), step=0.01,
                key="user_tol_input"
            )
            st.session_state["tolerance"] = Decimal(str(tol_input))

        # Step 3: Run
        st.markdown('<div class="sec-title">Step 3 — Run Reconciliation</div>', unsafe_allow_html=True)
        if user_p is None or user_b is None:
            st.button("▶  Run Reconciliation", disabled=True, help="Upload both valid CSV files first.")
        else:
            if st.button("▶  Run Reconciliation", type="primary", key="btn_run_user"):
                with st.spinner("Executing financial reconciliation on uploaded datasets..."):
                    engine = ReconciliationEngine(
                        reconciliation_month=st.session_state["recon_month"],
                        rounding_tolerance=st.session_state["tolerance"],
                    )
                    try:
                        u_summary, u_rec_df, u_exc_df = engine.reconcile(user_p, user_b)
                        st.session_state["user_summary"]   = u_summary
                        st.session_state["user_rec_df"]    = u_rec_df
                        st.session_state["user_exc_df"]    = u_exc_df
                        st.session_state["user_recon_run"] = True
                        st.success("Reconciliation successfully completed for uploaded files!")
                        st.rerun()
                    except ValueError as err:
                        st.error(f"Reconciliation error: {err}")

        # Display results ONLY if reconciliation has been run for user files
        if st.session_state["user_recon_run"] and st.session_state["user_summary"] is not None:
            u_sum = st.session_state["user_summary"]
            u_rec = st.session_state["user_rec_df"]

            st.markdown('<div class="sec-title">Uploaded Files Reconciliation Summary</div>', unsafe_allow_html=True)
            u_boxes = [
                ("Total Records",        u_sum.raw_platform_count),
                ("Matched",              u_sum.matched_count),
                ("Timing Differences",   u_sum.timing_difference_count),
                ("Rounding Differences", u_sum.rounding_difference_count),
                ("Duplicates",           u_sum.duplicate_count),
                ("Orphan Refunds",       u_sum.orphan_refund_count),
                ("Unsettled / Missing",  u_sum.unsettled_count),
            ]
            cols_res = st.columns(len(u_boxes))
            for c, (l, v) in zip(cols_res, u_boxes):
                with c:
                    st.markdown(f"""
                    <div class="recon-box">
                        <div class="recon-box-label">{l}</div>
                        <div class="recon-box-val">{v}</div>
                    </div>""", unsafe_allow_html=True)

            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="sec-title">Reconciliation Results Table</div>', unsafe_allow_html=True)
            render_styled_dataframe(u_rec, height=350)
            
            # Interactive inspector
            render_transaction_inspector(u_rec, key_prefix="user_rec_insp")

    # ─────────────────────────────────────────────────────────────
    # MODE 2: USE SAMPLE DEMO DATA
    # ─────────────────────────────────────────────────────────────
    else:
        st.session_state["source_mode"] = "synthetic"

        st.markdown('<div class="sec-title">Step 1 — Generate Sample Demo Data</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="banner banner-pista">
            <strong>Sample dataset intentionally plants all 4 required problems:</strong><br>
            • ⏱️ <strong>Next-Month Settlement</strong>: Month-end transaction settled in following month (T+1/T+2 cycle).<br>
            • 🪙 <strong>Rounding Difference</strong>: 2-3 paise line variances accumulating to an aggregate discrepancy.<br>
            • 📑 <strong>Duplicate Entry</strong>: Duplicate settlement record isolated from ledger.<br>
            • 👻 <strong>Orphan Refund</strong>: Refund referencing nonexistent sales transaction.
        </div>""", unsafe_allow_html=True)

        sc1, sc2 = st.columns([1.5, 1])
        with sc1:
            demo_month = st.selectbox(
                "Choose Demo Period to Generate",
                options=SAMPLE_PERIODS,
                index=0 if st.session_state["recon_month"] not in SAMPLE_PERIODS else SAMPLE_PERIODS.index(st.session_state["recon_month"]),
            )
        with sc2:
            st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
            if st.button("🔄  Generate & Load Sample Data", type="primary", use_container_width=True):
                with st.spinner(f"Generating realistic dataset for {demo_month}..."):
                    load_sample_dataset(demo_month)
                st.success(f"Sample data for {demo_month} loaded and reconciled!")
                st.rerun()

        # Planted Data Issue Manifest Viewer (Verification Key)
        with st.expander("📋 View Planted Data Issue Manifest (Verification Key)", expanded=False):
            st.markdown("""
            This manifest documents the exact test cases embedded in the synthetic generator, 
            their financial impact, and the expected classification by the reconciliation engine.
            """)
            manifest_df = get_data_issue_manifest(st.session_state["recon_month"])
            render_styled_dataframe(manifest_df, height=260)

        # Step 2: Configure
        st.markdown('<div class="sec-title">Step 2 — Configure Parameters</div>', unsafe_allow_html=True)
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.text_input("Active Period", value=st.session_state["recon_month"], disabled=True)
        with c_p2:
            s_tol = st.number_input(
                "Rounding Tolerance (₹)",
                min_value=0.01, max_value=1.00,
                value=float(st.session_state["tolerance"]), step=0.01,
                key="sample_tol_input"
            )
            st.session_state["tolerance"] = Decimal(str(s_tol))

        # Step 3: Results
        st.markdown('<div class="sec-title">Sample Data Reconciliation Results</div>', unsafe_allow_html=True)
        s_summary = st.session_state.get("synth_summary")
        s_rec     = st.session_state.get("synth_rec_df")

        if s_summary is not None:
            s_boxes = [
                ("Total Records",        s_summary.raw_platform_count),
                ("Matched",              s_summary.matched_count),
                ("Timing Differences",   s_summary.timing_difference_count),
                ("Rounding Differences", s_summary.rounding_difference_count),
                ("Duplicates",           s_summary.duplicate_count),
                ("Orphan Refunds",       s_summary.orphan_refund_count),
                ("Unsettled / Missing",  s_summary.unsettled_count),
            ]
            s_cols = st.columns(len(s_boxes))
            for c, (l, v) in zip(s_cols, s_boxes):
                with c:
                    st.markdown(f"""
                    <div class="recon-box">
                        <div class="recon-box-label">{l}</div>
                        <div class="recon-box-val">{v}</div>
                    </div>""", unsafe_allow_html=True)

            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
            render_styled_dataframe(s_rec, height=350)
            
            # Interactive inspector
            render_transaction_inspector(s_rec, key_prefix="sample_rec_insp")


# ═══════════════════════════════════════════════════════════════════
# PAGE: EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════
def page_exceptions():
    p_df, b_df, summary, rec_df, exc_df = get_current_data()
    month = st.session_state["recon_month"]

    st.markdown(f"""
    <div class="top-header-bar">
        <div>
            <div class="top-header-title">⚠️ Exception Management &amp; Audit</div>
            <div class="top-header-sub">Diagnose discrepancies, evaluate financial impact, and review recommended actions</div>
        </div>
        <div>
            <span class="top-header-badge badge-warn">{summary.total_exceptions_count if summary else 0} Total Exceptions</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if exc_df is None or exc_df.empty:
        st.info(f"No exceptions found for period {month}.")
        return

    # Filter row
    f1, f2, f3 = st.columns([2, 1.2, 1])
    with f1:
        search_q = st.text_input("🔍 Search Transaction ID or Reason", "")
    with f2:
        types_avail = ["All"] + sorted(exc_df["Exception Type"].unique().tolist())
        filter_t = st.selectbox("Exception Type", types_avail)
    with f3:
        sevs_avail = ["All"] + sorted(exc_df["Severity"].unique().tolist())
        filter_s = st.selectbox("Severity", sevs_avail)

    exc_filtered = exc_df.copy()
    if filter_t != "All":
        exc_filtered = exc_filtered[exc_filtered["Exception Type"] == filter_t]
    if filter_s != "All":
        exc_filtered = exc_filtered[exc_filtered["Severity"] == filter_s]
    if search_q:
        sq = search_q.lower()
        exc_filtered = exc_filtered[
            exc_filtered["Transaction ID"].str.lower().str.contains(sq, na=False) |
            exc_filtered["Reason for Mismatch"].str.lower().str.contains(sq, na=False)
        ]

    # Tabs for structured exception investigation
    tab_delayed, tab_rounding, tab_dup, tab_orphan, tab_all = st.tabs([
        f"⏱ Delayed ({summary.timing_difference_count})",
        f"🪙 Rounding ({summary.rounding_difference_count})",
        f"📑 Duplicates ({summary.duplicate_count})",
        f"👻 Orphan Refunds ({summary.orphan_refund_count})",
        f"📋 All Filtered ({len(exc_filtered)})",
    ])

    with tab_delayed:
        st.markdown("""
        <div class="banner banner-amber">
            ⏱ <strong>Next-Month Settlement (Timing Difference)</strong><br>
            Transactions recorded near month-end (e.g. last day of month) that settled on T+1/T+2 in the following month.<br>
            <strong>Action:</strong> Carry forward into Month-End In-Transit Float Ledger. Do not treat as permanently missing.
        </div>""", unsafe_allow_html=True)
        del_df = exc_filtered[exc_filtered["Exception Type"] == "Next-Month Settlement (Timing)"]
        render_styled_dataframe(del_df, height=280)

    with tab_rounding:
        st.markdown(f"""
        <div class="banner banner-amber">
            🪙 <strong>Rounding Differences</strong><br>
            Line-item variances ≤ ₹{st.session_state['tolerance']} caused by fractional MDR fee rounding or GST paise calculations.<br>
            <strong>Aggregate Net Drift:</strong> {format_inr(summary.aggregate_rounding_delta)}.<br>
            <strong>Action:</strong> Post minor balance to Small Balance / Rounding Expense Ledger.
        </div>""", unsafe_allow_html=True)
        rnd_df = exc_filtered[exc_filtered["Exception Type"] == "Rounding Difference"]
        render_styled_dataframe(rnd_df, height=280)

    with tab_dup:
        st.markdown("""
        <div class="banner banner-rose">
            📑 <strong>Duplicate Entries</strong><br>
            Duplicate settlement or platform records. Isolated from ledger totals to avoid double-counting balances.<br>
            <strong>Action:</strong> Verify with bank partner whether duplicate settlement was clawed back.
        </div>""", unsafe_allow_html=True)
        dup_df = exc_filtered[exc_filtered["Exception Type"].str.contains("Duplicate", na=False)]
        render_styled_dataframe(dup_df, height=280)

    with tab_orphan:
        st.markdown("""
        <div class="banner banner-rose">
            👻 <strong>Orphan Refunds</strong><br>
            Refund issued without any corresponding original payment record in the platform sales history.<br>
            <strong>Action:</strong> High severity — investigate potential merchant fraud or missing parent transaction.
        </div>""", unsafe_allow_html=True)
        orph_df = exc_filtered[exc_filtered["Exception Type"] == "Orphan Refund"]
        render_styled_dataframe(orph_df, height=280)

    with tab_all:
        render_styled_dataframe(exc_filtered, height=320)

    # Side-by-side inspector for any selected exception
    render_transaction_inspector(rec_df, key_prefix="exc_page_insp")

    # Download
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.download_button(
        "📥  Download Exception Report (CSV)",
        data=exc_filtered.to_csv(index=False).encode("utf-8"),
        file_name=f"exceptions_{month}.csv",
        mime="text/csv",
    )


# ═══════════════════════════════════════════════════════════════════
# PAGE: TRANSACTIONS / LEDGER
# ═══════════════════════════════════════════════════════════════════
def page_transactions():
    p_df, b_df, summary, rec_df, exc_df = get_current_data()
    month = st.session_state["recon_month"]

    st.markdown(f"""
    <div class="top-header-bar">
        <div>
            <div class="top-header-title">📋 Transaction &amp; Settlement Explorer</div>
            <div class="top-header-sub">Search, inspect, and filter individual transactions and bank credit batches</div>
        </div>
        <div>
            <span class="top-header-badge badge-ok">Period: {month}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if p_df is None or b_df is None or rec_df is None:
        st.info("No transaction data loaded. Please visit the Reconciliation page.")
        return

    # Filter section for ledger
    st.markdown('<div class="sec-title">Ledger Filters &amp; Search</div>', unsafe_allow_html=True)
    c_s1, c_s2, c_s3 = st.columns([2, 1.2, 1.2])
    with c_s1:
        tx_search = st.text_input("🔍 Search Transaction ID, UTR, or Customer", key="ledger_search")
    with c_s2:
        status_opts = ["All"] + sorted(rec_df["reconciliation_status"].dropna().unique().tolist())
        sel_status = st.selectbox("Reconciliation Status", status_opts, key="ledger_status")
    with c_s3:
        type_opts = ["All"]
        if "payment_method" in rec_df.columns:
            type_opts += sorted(rec_df["payment_method"].dropna().unique().tolist())
        sel_method = st.selectbox("Payment Method", type_opts, key="ledger_method")

    ledger_view = rec_df.copy()
    if sel_status != "All":
        ledger_view = ledger_view[ledger_view["reconciliation_status"] == sel_status]
    if sel_method != "All" and "payment_method" in ledger_view.columns:
        ledger_view = ledger_view[ledger_view["payment_method"] == sel_method]
    if tx_search:
        ts = tx_search.lower()
        ledger_view = ledger_view[
            ledger_view["transaction_id"].str.lower().str.contains(ts, na=False) |
            ledger_view["bank_reference"].fillna("").str.lower().str.contains(ts, na=False) |
            ledger_view["customer_id"].fillna("").str.lower().str.contains(ts, na=False)
        ]

    # Tabs for exploring
    t_full, t_plat, t_bank, t_matched, t_unmatched = st.tabs([
        f"📑 Filtered Ledger ({len(ledger_view)})",
        f"🏦 Platform Raw ({len(p_df)})",
        f"🏛️ Bank Raw ({len(b_df)})",
        f"✅ Matched Records ({summary.matched_count if summary else 0})",
        f"❓ Unsettled / Missing ({(summary.unsettled_count + summary.unmatched_bank_count) if summary else 0})",
    ])

    with t_full:
        render_styled_dataframe(ledger_view, height=360)

    with t_plat:
        render_styled_dataframe(p_df, height=360)

    with t_bank:
        render_styled_dataframe(b_df, height=360)

    with t_matched:
        m_records = rec_df[rec_df["reconciliation_status"] == "MATCHED"]
        render_styled_dataframe(m_records, height=360)

    with t_unmatched:
        un_records = rec_df[rec_df["reconciliation_status"].isin(["UNSETTLED_MISSING", "UNMATCHED_BANK_CREDIT"])]
        render_styled_dataframe(un_records, height=360)

    # Detailed transaction inspection view
    render_transaction_inspector(rec_df, key_prefix="ledger_page_insp")


# ═══════════════════════════════════════════════════════════════════
# PAGE: REPORTS
# ═══════════════════════════════════════════════════════════════════
def page_reports():
    p_df, b_df, summary, rec_df, exc_df = get_current_data()
    month = st.session_state["recon_month"]

    st.markdown(f"""
    <div class="top-header-bar">
        <div>
            <div class="top-header-title">📥 Financial Reports &amp; Audit Downloads</div>
            <div class="top-header-sub">Download compliance-ready CSV audit files and executive summaries</div>
        </div>
        <div>
            <span class="top-header-badge badge-ok">Period: {month}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if summary is None or rec_df is None:
        st.info("Reconciliation results required to generate reports. Please run reconciliation first.")
        return

    matched_df = rec_df[rec_df["reconciliation_status"] == "MATCHED"]
    delayed_df = rec_df[rec_df["reconciliation_status"] == "TIMING_DIFFERENCE_NEXT_MONTH"]
    dup_df     = rec_df[rec_df["reconciliation_status"].str.contains("DUPLICATE", na=False)]
    orphan_df  = rec_df[rec_df["reconciliation_status"] == "ORPHAN_REFUND"]

    summary_df = pd.DataFrame({
        "Metric": [
            "Reconciliation Month",
            "Total Platform Transactions (Raw Rows)",
            "Unique Platform Transaction IDs",
            "Total Platform Amount (INR)",
            "Total Bank Settlements (Raw Rows)",
            "Unique Bank Settlement IDs",
            "Total Bank Amount (INR)",
            "Matched Transactions Count (Total)",
            "Matched Exact Count",
            "Matched Within Variance Count",
            "Matched Amount (INR)",
            "Match Rate Percentage",
            "Delayed (Next-Month) Settlements Count",
            "Delayed Amount (INR)",
            "Rounding Difference Items",
            "Aggregate Net Rounding Delta (INR)",
            "Duplicate Entries Count",
            "Duplicate Amount (INR)",
            "Orphan Refunds Count",
            "Orphan Refunds Amount (INR)",
            "Unsettled (Missing) Count",
            "Unsettled Amount (INR)",
            "Unmatched Bank Credits Count",
            "Unmatched Bank Credits Amount (INR)",
            "Net Reconciliation Difference (INR)",
            "Gross Exception Exposure (INR)",
            "Total Exceptions Count"
        ],
        "Value": [
            month,
            summary.raw_platform_count,
            summary.unique_platform_count,
            format_inr(summary.total_platform_amount),
            summary.raw_bank_count,
            summary.unique_bank_count,
            format_inr(summary.total_bank_amount),
            summary.matched_count,
            summary.matched_exact_count,
            summary.matched_variance_count,
            format_inr(summary.matched_amount),
            f"{summary.match_rate_percentage:.2f}%",
            summary.timing_difference_count,
            format_inr(summary.timing_difference_amount),
            summary.rounding_difference_count,
            format_inr(summary.aggregate_rounding_delta),
            summary.duplicate_count,
            format_inr(summary.duplicate_amount),
            summary.orphan_refund_count,
            format_inr(summary.orphan_refund_amount),
            summary.unsettled_count,
            format_inr(summary.unsettled_amount),
            summary.unmatched_bank_count,
            format_inr(summary.unmatched_bank_amount),
            format_inr(summary.net_reconciliation_difference),
            format_inr(summary.gross_exception_exposure),
            summary.total_exceptions_count
        ]
    })

    REPORTS = [
        ("📋 Complete Reconciliation Ledger", "Every record with matching status, timestamps, and audit trail.", rec_df, f"reconciliation_full_{month}.csv"),
        ("✅ Matched Transactions Report", "Transactions matching perfectly between platform and bank.", matched_df, f"matched_{month}.csv"),
        ("⚠️ Exception Report", "Flagged discrepancies with root causes and corrective actions.", exc_df, f"exceptions_{month}.csv"),
        ("⏱️ Delayed Settlements Report", "Month-end transactions settling in the following month (float).", delayed_df, f"delayed_settlements_{month}.csv"),
        ("📑 Duplicate Entries Report", "Duplicate records quarantined to prevent double-counting.", dup_df, f"duplicates_{month}.csv"),
        ("👻 Orphan Refunds Report", "Refunds without matching original sales records.", orphan_df, f"orphan_refunds_{month}.csv"),
        ("📊 Executive Summary Report", "High-level summary of financial totals and metrics.", summary_df, f"executive_summary_{month}.csv"),
    ]

    for i in range(0, len(REPORTS), 3):
        cols = st.columns(3, gap="medium")
        for j, col in enumerate(cols):
            if i + j < len(REPORTS):
                title, desc, data, fname = REPORTS[i + j]
                with col:
                    st.markdown(f"""
                    <div style="background:{COLORS['white']}; border:1.5px solid {COLORS['brown_border']}; border-radius:10px; padding:16px; margin-bottom:12px; min-height:100px;">
                        <div style="font-weight:700; font-size:0.82rem; color:{COLORS['text_dark']}; margin-bottom:4px;">{title}</div>
                        <div style="font-size:0.72rem; color:{COLORS['brown_faint']};">{desc}</div>
                    </div>""", unsafe_allow_html=True)
                    st.download_button(
                        f"📥  Download ({len(data)} rows)",
                        data=data.to_csv(index=False).encode("utf-8"),
                        file_name=fname,
                        mime="text/csv",
                        use_container_width=True,
                        key=f"dl_rep_{fname}"
                    )
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# MAIN ROUTER
# ═══════════════════════════════════════════════════════════════════
cur_page = st.session_state["active_page"]

if cur_page == "overview":
    page_overview()
elif cur_page == "reconciliation":
    page_reconciliation()
elif cur_page == "exceptions":
    page_exceptions()
elif cur_page == "transactions":
    page_transactions()
elif cur_page == "reports":
    page_reports()
