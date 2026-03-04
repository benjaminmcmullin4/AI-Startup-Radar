"""Sidebar: branding, auth status, pipeline filters."""

from __future__ import annotations

import streamlit as st

from config import FIRM_NAME, COLORS, PIPELINE_STAGES, STAGE_LABELS, TIER_COLORS


def render_sidebar() -> dict:
    """Render the sidebar and return a dict of all active filter values."""

    with st.sidebar:
        # ── Branding ────────────────────────────────────────────────────
        st.markdown(
            f'<div style="padding:12px 0 8px 0;">'
            f'<span style="color:{COLORS["navy"]};font-size:1.4em;font-weight:700;">'
            f'◆ {FIRM_NAME}</span></div>',
            unsafe_allow_html=True,
        )

        # ── Auth status ─────────────────────────────────────────────────
        user_email = st.session_state.get("user_email", "")
        if user_email:
            st.caption(f"Signed in as **{user_email}**")
            if st.button("Sign Out", key="sidebar_signout"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        st.markdown("---")

        # ── Filters ─────────────────────────────────────────────────────
        st.header("Filters")

        tier_filter = st.multiselect(
            "Tier",
            ["hot", "warm", "monitor", "pass"],
            default=[],
            format_func=lambda t: f"{t.upper()}",
        )

        stage_filter = st.multiselect(
            "Pipeline Stage",
            PIPELINE_STAGES,
            format_func=lambda x: STAGE_LABELS.get(x, x),
            default=[],
        )

        sector_filter = st.multiselect(
            "Sector",
            [
                "Enterprise SaaS", "Fintech", "Healthcare IT", "Cybersecurity",
                "Data & Analytics", "DevOps & Infrastructure", "HR Tech",
                "Supply Chain & Logistics", "MarTech & AdTech", "Climate & Energy Tech",
                "Legal Tech", "PropTech",
            ],
            default=[],
        )

        arr_range = st.slider("ARR Range ($M)", 0.0, 200.0, (0.0, 200.0), step=1.0)
        growth_range = st.slider("Revenue Growth (%)", 0, 300, (0, 300), step=5)

        search = st.text_input("Search companies", "")

    return {
        "tier": tier_filter,
        "stage": stage_filter,
        "sector": sector_filter,
        "arr_range": arr_range,
        "growth_range": growth_range,
        "search": search,
    }
