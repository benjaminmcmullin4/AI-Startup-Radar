"""Dashboard tab: KPI cards, pipeline funnel, top companies, recent activity, sector chart."""

from __future__ import annotations

import streamlit as st
import pandas as pd

from db import get_companies_with_scores, get_activity_log
from viz import pipeline_funnel, sector_distribution_chart
from config import COLORS, TIER_COLORS


# ── Helpers ────────────────────────────────────────────────────────────────

def _fmt_money(val) -> str:
    if val is None:
        return "—"
    return f"${val:,.1f}M"


def _fmt_score(val) -> str:
    if val is None:
        return "—"
    return f"{val:.1f}"


def _render_kpi(label: str, value: str):
    st.markdown(
        f'<div class="metric-card"><h4>{label}</h4>'
        f'<div class="value">{value}</div></div>',
        unsafe_allow_html=True,
    )


# ── Main renderer ──────────────────────────────────────────────────────────

def render_dashboard():
    companies = get_companies_with_scores()
    if not companies:
        st.info("No companies in the database. Go to Deal Flow to add companies or load demo data.")
        return

    # KPI cards
    total = len(companies)
    hot_count = sum(1 for c in companies if c.get("tier") == "hot")
    scored = [c for c in companies if c.get("composite_score")]
    avg_score = sum(c["composite_score"] for c in scored) / len(scored) if scored else 0
    active_pipeline = sum(
        1 for c in companies
        if c.get("pipeline_stage") in ("screening", "deep_dive", "ic_review")
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _render_kpi("Total Companies", str(total))
    with col2:
        _render_kpi("Hot Deals", str(hot_count))
    with col3:
        _render_kpi("Avg Score", _fmt_score(avg_score))
    with col4:
        _render_kpi("Active Pipeline", str(active_pipeline))

    st.markdown("---")

    # Pipeline funnel + Sector distribution
    col_left, col_right = st.columns(2)

    with col_left:
        stage_counts: dict[str, int] = {}
        for c in companies:
            stage = c.get("pipeline_stage", "new")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        st.plotly_chart(pipeline_funnel(stage_counts), use_container_width=True)

    with col_right:
        sector_counts: dict[str, int] = {}
        for c in companies:
            sector = c.get("sector", "Unknown")
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        chart = sector_distribution_chart(sector_counts)
        if chart:
            st.plotly_chart(chart, use_container_width=True)

    st.markdown("---")

    # Top 10 companies table
    st.subheader("Top Scored Companies")
    top_companies = sorted(
        companies, key=lambda x: x.get("composite_score") or 0, reverse=True
    )[:10]

    if top_companies:
        rows = []
        for c in top_companies:
            tier = c.get("tier", "pass")
            rows.append({
                "Company": c["name"],
                "Sector": c.get("sector", "—"),
                "ARR ($M)": _fmt_money(c.get("arr_millions")),
                "Growth": f"{c.get('revenue_growth_pct', 0):.0f}%" if c.get("revenue_growth_pct") else "—",
                "Score": _fmt_score(c.get("composite_score", 0)),
                "Tier": tier.upper(),
                "Stage": c.get("pipeline_stage", "new").replace("_", " ").title(),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Recent activity
    st.subheader("Recent Activity")
    activities = get_activity_log(limit=15)
    if activities:
        for a in activities:
            company_name = a.get("company_name", "Unknown")
            action = a.get("action", "")
            details = a.get("details", "")
            ts = a.get("created_at", "")
            icon = {
                "scored": "📊", "stage_changed": "🔄", "note_added": "📝",
                "memo_generated": "📋", "imported": "📥",
            }.get(action, "•")
            st.markdown(
                f"{icon} **{company_name}** — {action.replace('_', ' ')} — "
                f"{details[:80]} _{ts}_"
            )
    else:
        st.caption("No activity yet.")
