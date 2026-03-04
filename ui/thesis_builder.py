"""Thesis Builder tab: weight sliders, criteria config, save/load, score preview."""

import streamlit as st
import json
from db.database import (
    get_all_theses, insert_thesis, update_thesis, get_default_thesis,
)
from services.scoring_engine import score_all_companies
from models.scoring import ThesisCriteria
from utils.validators import validate_thesis_weights


def render_thesis_builder():
    st.subheader("Investment Thesis Builder")
    st.caption("Configure scoring weights and investment criteria, then score all companies against your thesis.")

    # Load existing theses
    theses = get_all_theses()
    thesis_names = {t["id"]: t["name"] for t in theses}

    col_select, col_new = st.columns([3, 1])
    with col_select:
        if theses:
            selected_thesis_id = st.selectbox(
                "Load Thesis", list(thesis_names.keys()),
                format_func=lambda x: thesis_names[x],
            )
            thesis = next((t for t in theses if t["id"] == selected_thesis_id), None)
        else:
            thesis = None
            st.info("No theses saved. Create one below.")
    with col_new:
        if st.button("New Thesis"):
            thesis = None

    st.markdown("---")

    # Thesis form
    with st.form("thesis_form"):
        name = st.text_input("Thesis Name", value=thesis["name"] if thesis else "My Growth Thesis")
        description = st.text_area(
            "Thesis Description",
            value=thesis["description"] if thesis else "Growth equity thesis targeting...",
            height=80,
        )

        # Weight sliders
        st.subheader("Scoring Weights")
        st.caption("Weights must sum to 100%")

        wc1, wc2, wc3, wc4, wc5 = st.columns(5)
        with wc1:
            w_financial = st.slider("Financial", 0, 100, int((thesis or {}).get("weight_financial", 0.25) * 100), step=5)
        with wc2:
            w_team = st.slider("Team", 0, 100, int((thesis or {}).get("weight_team", 0.25) * 100), step=5)
        with wc3:
            w_market = st.slider("Market", 0, 100, int((thesis or {}).get("weight_market", 0.20) * 100), step=5)
        with wc4:
            w_product = st.slider("Product", 0, 100, int((thesis or {}).get("weight_product", 0.15) * 100), step=5)
        with wc5:
            w_momentum = st.slider("Momentum", 0, 100, int((thesis or {}).get("weight_momentum", 0.15) * 100), step=5)

        weight_total = w_financial + w_team + w_market + w_product + w_momentum
        if weight_total != 100:
            st.warning(f"Weights sum to {weight_total}%. Must equal 100%.")

        # Criteria
        st.subheader("Investment Criteria")
        existing_criteria = ThesisCriteria.from_json(thesis.get("criteria_json", "{}")) if thesis else ThesisCriteria()

        cc1, cc2 = st.columns(2)
        with cc1:
            min_arr = st.number_input("Min ARR ($M)", value=existing_criteria.min_arr, step=1.0)
            max_arr = st.number_input("Max ARR ($M)", value=existing_criteria.max_arr, step=10.0)
            min_growth = st.number_input("Min Revenue Growth (%)", value=existing_criteria.min_growth_pct, step=5.0)
            min_margin = st.number_input("Min Gross Margin (%)", value=existing_criteria.min_gross_margin_pct, step=5.0)
        with cc2:
            min_nrr = st.number_input("Min Net Retention (%)", value=existing_criteria.min_net_retention_pct, step=5.0)
            sectors = st.multiselect("Target Sectors", [
                "Enterprise SaaS", "Fintech", "Healthcare IT", "Cybersecurity",
                "Data & Analytics", "DevOps & Infrastructure", "HR Tech",
                "Supply Chain & Logistics", "MarTech & AdTech", "Climate & Energy Tech",
                "Legal Tech", "PropTech",
            ], default=existing_criteria.sectors)
            round_types = st.multiselect("Target Round Types", [
                "Seed", "Series A", "Series B", "Series C", "Series D", "Growth",
            ], default=existing_criteria.round_types)

        submitted = st.form_submit_button("Save Thesis", type="primary")

        if submitted:
            if weight_total != 100:
                st.error("Weights must sum to 100%.")
            else:
                criteria = ThesisCriteria(
                    min_arr=min_arr, max_arr=max_arr, min_growth_pct=min_growth,
                    sectors=sectors, round_types=round_types,
                    min_gross_margin_pct=min_margin, min_net_retention_pct=min_nrr,
                )
                thesis_data = {
                    "name": name,
                    "description": description,
                    "weight_financial": w_financial / 100,
                    "weight_team": w_team / 100,
                    "weight_market": w_market / 100,
                    "weight_product": w_product / 100,
                    "weight_momentum": w_momentum / 100,
                    "criteria_json": criteria.to_json(),
                }
                if thesis:
                    update_thesis(thesis["id"], thesis_data)
                    st.success(f"Updated thesis '{name}'")
                else:
                    insert_thesis(thesis_data)
                    st.success(f"Created thesis '{name}'")
                st.rerun()

    st.markdown("---")

    # Score all companies with current thesis
    st.subheader("Score Preview")
    if st.button("Score All Companies with Selected Thesis", type="primary"):
        active_thesis = thesis or get_default_thesis()
        if active_thesis:
            with st.spinner("Scoring all companies..."):
                results = score_all_companies(active_thesis)
                tiers = {}
                for r in results:
                    t = r.get("tier", "pass")
                    tiers[t] = tiers.get(t, 0) + 1
                st.success(f"Scored {len(results)} companies")
                tc1, tc2, tc3, tc4 = st.columns(4)
                with tc1:
                    st.metric("Hot", tiers.get("hot", 0))
                with tc2:
                    st.metric("Warm", tiers.get("warm", 0))
                with tc3:
                    st.metric("Monitor", tiers.get("monitor", 0))
                with tc4:
                    st.metric("Pass", tiers.get("pass", 0))
        else:
            st.warning("Save a thesis first before scoring.")
