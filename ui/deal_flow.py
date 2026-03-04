"""Deal Flow tab: filterable company table, CSV import, add company, bulk actions."""

import streamlit as st
import pandas as pd
import json
import io
from db.database import (
    get_companies_with_scores, update_pipeline_stage, insert_company,
    get_all_theses, get_default_thesis, get_all_companies, get_company,
)
from models.company import Company
from services.scoring_engine import score_company, score_all_companies
from db.database import upsert_score
from config.settings import PIPELINE_STAGES, STAGE_LABELS
from utils.formatting import fmt_money
from utils.validators import validate_company_data


def render_deal_flow():
    # --- Company Search (hero section) ---
    from services.company_lookup import is_lookup_available
    if is_lookup_available():
        st.subheader("Find & Import Companies")
        _render_company_search()
        st.markdown("---")
    else:
        st.info(
            "**Find & Import Companies** — Configure an `OPENAI_API_KEY` or "
            "`ANTHROPIC_API_KEY` in `.streamlit/secrets.toml` or your environment "
            "to enable AI-powered company search."
        )
        st.markdown("---")

    companies = get_companies_with_scores()

    # --- Sidebar filters ---
    with st.sidebar:
        st.header("Filters")

        tier_filter = st.multiselect("Tier", ["hot", "warm", "monitor", "pass"], default=[])
        stage_filter = st.multiselect("Pipeline Stage",
                                       PIPELINE_STAGES,
                                       format_func=lambda x: STAGE_LABELS.get(x, x),
                                       default=[])
        sectors = sorted(set(c.get("sector", "") for c in companies if c.get("sector")))
        sector_filter = st.multiselect("Sector", sectors, default=[])

        arr_range = st.slider("ARR Range ($M)", 0.0, 200.0, (0.0, 200.0), step=1.0)
        growth_range = st.slider("Revenue Growth (%)", 0, 300, (0, 300), step=5)

        search = st.text_input("Search companies", "")

    # Apply filters
    filtered = companies
    if tier_filter:
        filtered = [c for c in filtered if c.get("tier") in tier_filter]
    if stage_filter:
        filtered = [c for c in filtered if c.get("pipeline_stage") in stage_filter]
    if sector_filter:
        filtered = [c for c in filtered if c.get("sector") in sector_filter]
    filtered = [c for c in filtered if arr_range[0] <= (c.get("arr_millions") or 0) <= arr_range[1]]
    filtered = [c for c in filtered if growth_range[0] <= (c.get("revenue_growth_pct") or 0) <= growth_range[1]]
    if search:
        search_lower = search.lower()
        filtered = [c for c in filtered if search_lower in (c.get("name") or "").lower()
                    or search_lower in (c.get("description") or "").lower()
                    or search_lower in (c.get("sector") or "").lower()]

    # --- Bulk actions ---
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Score All Companies", type="primary"):
            with st.spinner("Scoring all companies..."):
                results = score_all_companies()
                st.success(f"Scored {len(results)} companies")
                st.rerun()
    with col2:
        if st.button("Export CSV"):
            df = _companies_to_df(filtered)
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", csv, "deal_flow_export.csv", "text/csv")

    st.markdown(f"**{len(filtered)}** companies shown")

    # --- Company table ---
    if filtered:
        for c in filtered:
            col_name, col_sector, col_arr, col_growth, col_score, col_stage = st.columns([3, 2, 1.5, 1.5, 1, 2])

            with col_name:
                if st.button(c["name"], key=f"company_{c['id']}"):
                    st.session_state["selected_company_id"] = c["id"]
                    st.session_state["active_tab"] = "Company Detail"
                    st.rerun()

            with col_sector:
                st.caption(c.get("sector", "—"))

            with col_arr:
                arr = c.get("arr_millions")
                st.caption(f"${arr:.1f}M" if arr else "—")

            with col_growth:
                growth = c.get("revenue_growth_pct")
                st.caption(f"{growth:.0f}%" if growth else "—")

            with col_score:
                score = c.get("composite_score")
                tier = c.get("tier", "pass")
                color = {"hot": "🔴", "warm": "🟡", "monitor": "🔵", "pass": "⚪"}.get(tier, "⚪")
                st.caption(f"{color} {score:.1f}" if score else "—")

            with col_stage:
                current_stage = c.get("pipeline_stage", "new")
                new_stage = st.selectbox(
                    "Stage", PIPELINE_STAGES,
                    index=PIPELINE_STAGES.index(current_stage) if current_stage in PIPELINE_STAGES else 0,
                    format_func=lambda x: STAGE_LABELS.get(x, x),
                    key=f"stage_{c['id']}",
                    label_visibility="collapsed",
                )
                if new_stage != current_stage:
                    update_pipeline_stage(c["id"], new_stage)
                    st.rerun()

    st.markdown("---")

    # --- Add Company / CSV Import ---
    tab_add, tab_csv = st.tabs(["Add Company", "CSV Import"])

    with tab_add:
        _render_add_company_form()

    with tab_csv:
        _render_csv_import()


def _render_add_company_form():
    with st.form("add_company"):
        st.subheader("Add New Company")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Company Name*")
            domain = st.text_input("Domain")
            sector = st.selectbox("Sector", [
                "Enterprise SaaS", "Fintech", "Healthcare IT", "Cybersecurity",
                "Data & Analytics", "DevOps & Infrastructure", "HR Tech",
                "Supply Chain & Logistics", "MarTech & AdTech", "Climate & Energy Tech",
                "Legal Tech", "PropTech",
            ])
            description = st.text_area("Description", height=80)
            hq_location = st.text_input("HQ Location")
            founded_year = st.number_input("Founded Year", min_value=1990, max_value=2026, value=2020)

        with col2:
            arr_millions = st.number_input("ARR ($M)", min_value=0.0, step=0.1, value=0.0)
            revenue_growth_pct = st.number_input("Revenue Growth (%)", min_value=-100.0, step=1.0, value=0.0)
            gross_margin_pct = st.number_input("Gross Margin (%)", min_value=0.0, max_value=100.0, step=1.0, value=70.0)
            net_retention_pct = st.number_input("Net Retention (%)", min_value=0.0, step=1.0, value=100.0)
            employee_count = st.number_input("Employee Count", min_value=0, step=1, value=0)
            employee_growth_pct = st.number_input("Employee Growth (%)", min_value=-100.0, step=1.0, value=0.0)
            last_round_type = st.selectbox("Last Round Type", ["", "Seed", "Series A", "Series B", "Series C", "Series D", "Growth"])
            last_round_amount = st.number_input("Last Round Amount ($M)", min_value=0.0, step=0.1, value=0.0)

        submitted = st.form_submit_button("Add Company", type="primary")
        if submitted and name:
            company = Company(
                name=name, domain=domain, description=description, sector=sector,
                hq_location=hq_location, founded_year=int(founded_year),
                employee_count=int(employee_count), employee_growth_pct=employee_growth_pct,
                arr_millions=arr_millions, revenue_growth_pct=revenue_growth_pct,
                gross_margin_pct=gross_margin_pct, net_retention_pct=net_retention_pct,
                last_round_type=last_round_type if last_round_type else None,
                last_round_amount_millions=last_round_amount if last_round_amount else None,
                source="manual",
            )
            cid = insert_company(company)
            # Auto-score
            from db.database import get_company
            c_data = get_company(cid)
            if c_data:
                result = score_company(c_data)
                upsert_score(result)
            st.success(f"Added {name} and scored automatically!")
            st.rerun()


def _render_csv_import():
    st.subheader("Import from CSV")
    st.caption("Upload a CSV file with company data. [Download template](data/example_import.csv)")
    uploaded = st.file_uploader("Choose CSV file", type=["csv"])
    if uploaded:
        try:
            df = pd.read_csv(uploaded)
            st.dataframe(df.head(), use_container_width=True)
            if st.button("Import All Rows", type="primary"):
                count = 0
                for _, row in df.iterrows():
                    data = row.to_dict()
                    # Parse key_investors if string
                    if "key_investors" in data and isinstance(data["key_investors"], str):
                        try:
                            data["key_investors"] = json.loads(data["key_investors"])
                        except (json.JSONDecodeError, TypeError):
                            data["key_investors"] = []
                    company = Company(**{k: v for k, v in data.items()
                                        if k in Company.__dataclass_fields__ and pd.notna(v)})
                    cid = insert_company(company)
                    c_data = {"id": cid, **data}
                    result = score_company(c_data)
                    upsert_score(result)
                    count += 1
                st.success(f"Imported and scored {count} companies!")
                st.rerun()
        except Exception as e:
            st.error(f"Error reading CSV: {e}")


def _render_company_search():
    from services.company_lookup import search_companies

    query = st.text_input("Company name", key="cb_search_query", placeholder="e.g. Datadog")

    if query:
        with st.spinner("Searching for companies..."):
            results = search_companies(query)

        if not results:
            st.info("No results found. Try a different search term.")
            return

        for i, r in enumerate(results):
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                st.markdown(f"**{r['name']}**")
                if r.get("short_description"):
                    st.caption(r["short_description"])
            with col_btn:
                if st.button("Import", key=f"cb_import_{i}_{r.get('permalink', i)}"):
                    _import_company(r["name"])


def _import_company(company_name: str):
    from services.company_lookup import get_company_details, map_to_company

    # Check for duplicate by name
    existing = get_all_companies()
    with st.spinner("Looking up company details..."):
        details = get_company_details(company_name)

    if not details:
        st.error("Failed to fetch company details. Please try again.")
        return

    company = map_to_company(details)

    # Duplicate check
    existing_names = {c["name"].lower() for c in existing}
    if company.name.lower() in existing_names:
        st.warning(f"**{company.name}** already exists in your pipeline.")
        return

    cid = insert_company(company)

    # Auto-score
    c_data = get_company(cid)
    if c_data:
        result = score_company(c_data)
        upsert_score(result)

    st.success(f"Imported **{company.name}**!")
    st.warning(
        "Financial metrics (ARR, revenue growth, gross margin, net retention) are not "
        "available from AI lookup. Edit them on the Company Detail page to improve scoring."
    )
    st.rerun()


def _companies_to_df(companies: list[dict]) -> pd.DataFrame:
    rows = []
    for c in companies:
        rows.append({
            "Name": c.get("name"),
            "Sector": c.get("sector"),
            "ARR ($M)": c.get("arr_millions"),
            "Revenue Growth (%)": c.get("revenue_growth_pct"),
            "Gross Margin (%)": c.get("gross_margin_pct"),
            "Net Retention (%)": c.get("net_retention_pct"),
            "Employees": c.get("employee_count"),
            "Score": c.get("composite_score"),
            "Tier": c.get("tier"),
            "Pipeline Stage": c.get("pipeline_stage"),
            "Last Round": c.get("last_round_type"),
        })
    return pd.DataFrame(rows)
