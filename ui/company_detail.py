"""Company Detail tab: full profile, score breakdown, memo, notes, tags."""

import streamlit as st
import json
from db.database import (
    get_company, get_score, get_notes, get_tags, get_news,
    update_pipeline_stage, add_note, add_tag, remove_tag,
    update_company, get_default_thesis, get_all_companies,
)
from ui.components import score_gauge, radar_chart, tier_badge, thesis_fit_bar
from services.memo_generator import generate_memo
from services.thesis_matcher import match_thesis
from services.scoring_engine import score_company
from db.database import upsert_score
from config.settings import PIPELINE_STAGES, STAGE_LABELS
from utils.formatting import fmt_money, fmt_pct, fmt_number


def render_company_detail():
    # Company selector
    companies = get_all_companies()
    if not companies:
        st.info("No companies in database. Add companies in the Deal Flow tab.")
        return

    company_names = {c["id"]: c["name"] for c in companies}
    selected_id = st.session_state.get("selected_company_id")

    options = list(company_names.keys())
    default_idx = options.index(selected_id) if selected_id in options else 0

    chosen_id = st.selectbox(
        "Select Company",
        options,
        index=default_idx,
        format_func=lambda x: company_names.get(x, "Unknown"),
    )
    st.session_state["selected_company_id"] = chosen_id

    company = get_company(chosen_id)
    if not company:
        st.error("Company not found.")
        return

    score = get_score(chosen_id)

    # --- Header ---
    col_h1, col_h2, col_h3 = st.columns([4, 2, 2])
    with col_h1:
        st.header(company["name"])
        st.caption(f"{company.get('sector', '—')} · {company.get('hq_location', '—')} · Founded {company.get('founded_year', '—')}")
    with col_h2:
        if score:
            st.plotly_chart(score_gauge(score["composite_score"]), use_container_width=True)
    with col_h3:
        if score:
            tier_badge(score.get("tier", "pass"))
        # Pipeline stage selector
        current_stage = company.get("pipeline_stage", "new")
        new_stage = st.selectbox(
            "Pipeline Stage", PIPELINE_STAGES,
            index=PIPELINE_STAGES.index(current_stage) if current_stage in PIPELINE_STAGES else 0,
            format_func=lambda x: STAGE_LABELS.get(x, x),
            key="detail_stage_select",
        )
        if new_stage != current_stage:
            update_pipeline_stage(chosen_id, new_stage)
            st.rerun()

    st.markdown("---")

    # --- Two column layout ---
    col_left, col_right = st.columns([3, 2])

    with col_left:
        # Overview
        st.subheader("Overview")
        st.write(company.get("description") or "No description available.")

        # Financials
        st.subheader("Financial Profile")
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            st.metric("ARR", fmt_money(company.get("arr_millions")))
        with fc2:
            st.metric("Revenue Growth", fmt_pct(company.get("revenue_growth_pct")))
        with fc3:
            st.metric("Gross Margin", fmt_pct(company.get("gross_margin_pct")))
        with fc4:
            st.metric("Net Retention", fmt_pct(company.get("net_retention_pct")))

        # Funding
        st.subheader("Funding & Capitalization")
        fu1, fu2, fu3 = st.columns(3)
        with fu1:
            st.metric("Total Raised", fmt_money(company.get("total_raised_millions")))
        with fu2:
            st.metric("Last Round", f"{company.get('last_round_type', '—')} · {fmt_money(company.get('last_round_amount_millions'))}")
        with fu3:
            st.metric("Valuation", fmt_money(company.get("last_valuation_millions")))

        investors = company.get("key_investors", [])
        if isinstance(investors, str):
            try:
                investors = json.loads(investors)
            except (json.JSONDecodeError, TypeError):
                investors = []
        if investors:
            st.caption(f"**Key Investors:** {', '.join(investors)}")

        # Team
        st.subheader("Team")
        tc1, tc2 = st.columns(2)
        with tc1:
            st.metric("Employees", fmt_number(company.get("employee_count")))
        with tc2:
            st.metric("Headcount Growth", fmt_pct(company.get("employee_growth_pct")))

        # Edit Financial Metrics (for imports with missing financials)
        if company.get("source") in ("ai_lookup", "crunchbase") or any(
            company.get(f) is None for f in ["arr_millions", "revenue_growth_pct", "gross_margin_pct", "net_retention_pct"]
        ):
            with st.expander("Edit Financial Metrics"):
                with st.form(f"edit_financials_{chosen_id}"):
                    ef1, ef2 = st.columns(2)
                    with ef1:
                        new_arr = st.number_input(
                            "ARR ($M)", min_value=0.0, step=0.1,
                            value=float(company.get("arr_millions") or 0.0),
                            key=f"edit_arr_{chosen_id}",
                        )
                        new_growth = st.number_input(
                            "Revenue Growth (%)", min_value=-100.0, step=1.0,
                            value=float(company.get("revenue_growth_pct") or 0.0),
                            key=f"edit_growth_{chosen_id}",
                        )
                        new_emp_growth = st.number_input(
                            "Employee Growth (%)", min_value=-100.0, step=1.0,
                            value=float(company.get("employee_growth_pct") or 0.0),
                            key=f"edit_emp_growth_{chosen_id}",
                        )
                    with ef2:
                        new_margin = st.number_input(
                            "Gross Margin (%)", min_value=0.0, max_value=100.0, step=1.0,
                            value=float(company.get("gross_margin_pct") or 0.0),
                            key=f"edit_margin_{chosen_id}",
                        )
                        new_retention = st.number_input(
                            "Net Retention (%)", min_value=0.0, step=1.0,
                            value=float(company.get("net_retention_pct") or 0.0),
                            key=f"edit_retention_{chosen_id}",
                        )

                    if st.form_submit_button("Save & Re-score", type="primary"):
                        updates = {
                            "arr_millions": new_arr if new_arr else None,
                            "revenue_growth_pct": new_growth if new_growth else None,
                            "gross_margin_pct": new_margin if new_margin else None,
                            "net_retention_pct": new_retention if new_retention else None,
                            "employee_growth_pct": new_emp_growth if new_emp_growth else None,
                        }
                        update_company(chosen_id, updates)
                        # Re-score with updated financials
                        updated = get_company(chosen_id)
                        if updated:
                            result = score_company(updated)
                            upsert_score(result)
                        st.success("Financial metrics updated and company re-scored!")
                        st.rerun()

        # News
        st.subheader("Recent News")
        news = get_news(chosen_id)
        if news:
            for n in news[:5]:
                st.markdown(f"**{n.get('title', '—')}** — _{n.get('source', '')} · {n.get('published_date', '')}_")
                if n.get("summary"):
                    st.caption(n["summary"])
        else:
            st.caption("No news items.")

    with col_right:
        # Radar chart
        if score:
            st.plotly_chart(radar_chart(score), use_container_width=True)

        # Thesis fit
        st.subheader("Thesis Fit")
        thesis = get_default_thesis()
        if thesis:
            fit_result = match_thesis(company, thesis)
            if "fit_pct" in fit_result:
                thesis_fit_bar(fit_result["fit_pct"])
                st.caption(f"**{fit_result['passed_checks']}/{fit_result['total_checks']}** criteria met")
                if fit_result.get("matches"):
                    for m in fit_result["matches"]:
                        st.markdown(f"✅ {m}")
                if fit_result.get("misses"):
                    for m in fit_result["misses"]:
                        st.markdown(f"❌ {m}")
            elif "fit_score" in fit_result:
                st.metric("AI Fit Score", f"{fit_result['fit_score']}/10")
                for r in fit_result.get("rationale", []):
                    st.markdown(f"• {r}")
        else:
            st.caption("No thesis configured. Set one up in the Thesis Builder tab.")

        # Tags
        st.subheader("Tags")
        tags = get_tags(chosen_id)
        if tags:
            tag_cols = st.columns(min(len(tags), 4))
            for i, tag in enumerate(tags):
                with tag_cols[i % len(tag_cols)]:
                    if st.button(f"❌ {tag}", key=f"rm_tag_{tag}_{chosen_id}"):
                        remove_tag(chosen_id, tag)
                        st.rerun()

        new_tag = st.text_input("Add tag", key="new_tag_input")
        if new_tag and st.button("Add Tag"):
            add_tag(chosen_id, new_tag.strip())
            st.rerun()

    st.markdown("---")

    # --- Investment Memo ---
    st.subheader("Investment Memo")
    if company.get("ai_memo"):
        st.markdown(company["ai_memo"])
        st.download_button("Download Memo", company["ai_memo"], f"memo_{company['name'].replace(' ', '_')}.md", "text/markdown")
    else:
        if st.button("Generate Investment Memo", type="primary"):
            with st.spinner("Generating memo..."):
                memo = generate_memo(company, score)
                update_company(chosen_id, {"ai_memo": memo})
                st.rerun()

    st.markdown("---")

    # --- Notes ---
    st.subheader("Analyst Notes")
    notes = get_notes(chosen_id)
    for note in notes:
        st.markdown(f"**{note.get('author', 'analyst')}** — _{note.get('created_at', '')}_")
        st.write(note.get("content", ""))
        st.markdown("---")

    with st.form(f"note_form_{chosen_id}"):
        note_content = st.text_area("Add a note", height=80)
        if st.form_submit_button("Save Note") and note_content:
            add_note(chosen_id, note_content)
            st.rerun()
