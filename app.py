"""Growth Equity Radar — Deal Sourcing & Screening."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from config import COLORS, FIRM_NAME, APP_TITLE, APP_SUBTITLE, DEMO_MODE, DATA_DIR
from db import init_db, get_company_count

# ── Page config ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title=FIRM_NAME,
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Load custom CSS ────────────────────────────────────────────────────
css_path = Path(__file__).parent / "styles" / "custom.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# ── Auth gate ──────────────────────────────────────────────────────────
from auth import render_auth_gate

if not render_auth_gate():
    st.stop()

# ── Initialize DB & demo data ─────────────────────────────────────────
if "initialized" not in st.session_state:
    init_db()
    if DEMO_MODE:
        from pipeline import score_all_companies
        _load_demo_data()
        score_all_companies()
    st.session_state["initialized"] = True


def _load_demo_data():
    """Load sample companies and default thesis if DB is empty."""
    from db import get_company_count, insert_company, insert_thesis, insert_news
    from schema import Company
    if get_company_count() > 0:
        return
    sample_path = DATA_DIR / "sample_companies.json"
    if sample_path.exists():
        companies = json.loads(sample_path.read_text())
        for c_data in companies:
            company = Company.model_validate(c_data)
            insert_company(company)
    thesis_path = Path(__file__).parent / "examples" / "default_thesis.json"
    if thesis_path.exists():
        thesis = json.loads(thesis_path.read_text())
        insert_thesis(thesis)
    news_path = DATA_DIR / "sample_news.json"
    if news_path.exists():
        news_items = json.loads(news_path.read_text())
        for item in news_items:
            insert_news(item)


# ── Sidebar ────────────────────────────────────────────────────────────
from components.sidebar import render_sidebar

filters = render_sidebar()

# ── Header ─────────────────────────────────────────────────────────────
st.markdown(
    f'<h1 style="color: {COLORS["navy"]}; margin-bottom: 0;">◆ {FIRM_NAME}</h1>'
    f'<p style="color: {COLORS["muted"]}; margin-top: 0;">{APP_SUBTITLE}</p>',
    unsafe_allow_html=True,
)

# Demo mode banner
if DEMO_MODE:
    st.markdown(
        '<div class="demo-banner">'
        '◆ <strong>Demo Mode</strong> — Configure API keys for AI-powered features'
        '</div>',
        unsafe_allow_html=True,
    )

# ── Tabs ───────────────────────────────────────────────────────────────
tabs = st.tabs(["Dashboard", "Deal Flow", "Company Detail", "Thesis Builder", "Weekly Digest"])

from components.dashboard_tab import render_dashboard
from components.deal_flow_tab import render_deal_flow
from components.company_detail_tab import render_company_detail
from components.thesis_builder_tab import render_thesis_builder
from components.weekly_digest_tab import render_weekly_digest

with tabs[0]:
    render_dashboard()

with tabs[1]:
    render_deal_flow(filters)

with tabs[2]:
    render_company_detail()

with tabs[3]:
    render_thesis_builder()

with tabs[4]:
    render_weekly_digest()
