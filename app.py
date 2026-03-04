"""Mercato Traverse Radar — Growth Equity Deal Sourcing & Screening
Internal tool for Mercato Partners' Traverse Fund.
"""

import streamlit as st
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import DEMO_MODE
from utils.demo_mode import load_sample_data, is_demo_mode
from db.database import init_db
from services.scoring_engine import score_all_companies
from services.auth import render_auth_gate

st.set_page_config(
    page_title="Mercato Traverse Radar",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Authentication Gate ---
if not render_auth_gate():
    st.stop()

# --- Initialize ---
if "initialized" not in st.session_state:
    init_db()
    if is_demo_mode():
        load_sample_data()
        score_all_companies()
    st.session_state["initialized"] = True

# --- Header ---
col_title, col_user = st.columns([5, 1])
with col_title:
    st.title("◆ Traverse Radar")
    st.caption("Mercato Partners — Growth Equity Deal Sourcing & Screening")
with col_user:
    user_email = st.session_state.get("user_email", "")
    if user_email:
        st.caption(f"Signed in as **{user_email}**")
    if st.button("Sign Out", key="signout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- Demo mode banner ---
if is_demo_mode():
    st.info("◆ **Demo Mode** — Showing sample portfolio pipeline with rule-based scoring. Configure API keys in Streamlit secrets for AI-powered enrichment.", icon="ℹ️")

# --- Tab routing ---
tabs = st.tabs(["Dashboard", "Deal Flow", "Company Detail", "Thesis Builder", "Weekly Digest"])

with tabs[0]:
    from ui.dashboard import render_dashboard
    render_dashboard()

with tabs[1]:
    from ui.deal_flow import render_deal_flow
    render_deal_flow()

with tabs[2]:
    from ui.company_detail import render_company_detail
    render_company_detail()

with tabs[3]:
    from ui.thesis_builder import render_thesis_builder
    render_thesis_builder()

with tabs[4]:
    from ui.weekly_digest import render_weekly_digest
    render_weekly_digest()
