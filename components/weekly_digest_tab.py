"""Weekly Digest tab: date range selector, digest generation, export."""

from __future__ import annotations

import streamlit as st
from datetime import datetime, timedelta

from news import generate_digest


def render_weekly_digest():
    st.subheader("Weekly Deal Flow Digest")
    st.caption(
        "Generate a summary of pipeline activity, hot deals, and thesis match highlights."
    )

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=7))
    with col2:
        end_date = st.date_input("End Date", value=datetime.now())

    if st.button("Generate Digest", type="primary"):
        with st.spinner("Generating digest..."):
            digest = generate_digest(
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
            )
            st.session_state["last_digest"] = digest

    if "last_digest" in st.session_state:
        digest = st.session_state["last_digest"]
        st.markdown(digest)
        st.download_button(
            "Download as Markdown",
            digest,
            f"digest_{datetime.now().strftime('%Y%m%d')}.md",
            "text/markdown",
        )
