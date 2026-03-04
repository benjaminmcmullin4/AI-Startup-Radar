"""Consolidated pipeline services: scoring, company lookup, memo generation,
thesis matching, and enrichment."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Optional

from config import (
    ANTHROPIC_API_KEY,
    DEMO_MODE,
    OPENAI_API_KEY,
    SECTOR_ATTRACTIVENESS,
    TAVILY_API_KEY,
)
from db import (
    get_all_companies,
    get_default_thesis,
    get_news,
    log_activity,
    update_company,
    upsert_score,
)
from prompts import (
    COMPANY_LOOKUP_SYSTEM,
    ENRICHMENT_PROMPT,
    MEMO_AI_PROMPT,
    THESIS_MATCH_PROMPT,
)
from schema import Company, ThesisCriteria

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Formatting helpers
# ═══════════════════════════════════════════════════════════════════════

def fmt_money(value: float, decimals: int = 1) -> str:
    if value is None:
        return "N/A"
    if value >= 1000:
        return f"${value / 1000:.{decimals}f}B"
    return f"${value:.{decimals}f}M"


def fmt_pct(value: float, decimals: int = 0) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"


# ═══════════════════════════════════════════════════════════════════════
# LLM utilities (shared by lookup, memo, thesis, enrichment)
# ═══════════════════════════════════════════════════════════════════════

def _call_llm(system: str, user: str) -> Optional[str]:
    """Call an LLM with Anthropic-first, OpenAI-fallback pattern. Returns raw text."""
    try:
        if ANTHROPIC_API_KEY:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            resp = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return resp.content[0].text
        elif OPENAI_API_KEY:
            import openai
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=1500,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return resp.choices[0].message.content
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        try:
            import streamlit as st
            st.error(f"AI lookup error: {e}")
        except Exception:
            pass
    return None


def _parse_json(text: str):
    """Parse JSON from LLM response, stripping markdown fences if present."""
    if text is None:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from LLM response: %s", text[:200])
        return None


def _tavily_search(query: str, max_results: int = 5) -> Optional[list[dict]]:
    """Search the web via Tavily. Returns list of result dicts or None on failure."""
    if not TAVILY_API_KEY:
        return None
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(query=query, max_results=max_results)
        results = response.get("results", [])
        if not results:
            return None
        return [{"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")} for r in results]
    except Exception as e:
        logger.warning("Tavily search failed: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════════
# Company Lookup (from services/company_lookup.py)
# ═══════════════════════════════════════════════════════════════════════

def is_lookup_available() -> bool:
    """Return True if any AI API key is configured."""
    return bool(OPENAI_API_KEY or ANTHROPIC_API_KEY)


def search_companies(query: str) -> list[dict]:
    """Search for companies matching a query using AI knowledge.

    Returns list of dicts with: name, permalink, short_description.
    """
    if not is_lookup_available():
        return []

    web_results = _tavily_search(f"{query} startup company", max_results=5)

    if web_results:
        snippets = "\n\n".join(
            f"- {r['title']} ({r['url']}): {r['content'][:300]}"
            for r in web_results
        )
        user_prompt = (
            f"Based on these web search results, identify up to 5 companies related to '{query}'.\n\n"
            f"Web results:\n{snippets}\n\n"
            f"Return a JSON array where each element has: "
            f'"name" (string), "permalink" (slugified lowercase name, e.g. "datadog"), '
            f'"short_description" (one sentence).'
        )
    else:
        user_prompt = (
            f"List up to 5 real technology/software companies matching '{query}'. "
            f"Return a JSON array where each element has: "
            f'"name" (string), "permalink" (slugified lowercase name, e.g. "datadog"), '
            f'"short_description" (one sentence).'
        )

    result = _call_llm(COMPANY_LOOKUP_SYSTEM, user_prompt)
    parsed = _parse_json(result)

    if isinstance(parsed, list):
        return parsed[:5]
    return []


def get_company_details(company_name: str) -> Optional[dict]:
    """Fetch structured company details using AI knowledge.

    Returns a dict with company fields or None on failure.
    """
    if not is_lookup_available() or not company_name:
        return None

    overview_results = _tavily_search(f"{company_name} company overview funding employees", max_results=5)
    funding_results = _tavily_search(f"{company_name} funding round valuation investors", max_results=3)

    web_context = ""
    all_results = (overview_results or []) + (funding_results or [])
    if all_results:
        snippets = "\n\n".join(
            f"- {r['title']} ({r['url']}): {r['content'][:400]}"
            for r in all_results
        )
        web_context = (
            f"\n\nUse these web results as your primary source. Use null for fields not found in the results.\n\n"
            f"Web results:\n{snippets}"
        )

    user_prompt = (
        f"Provide factual details about the company '{company_name}'. "
        f"Return a JSON object with these fields: "
        f'"name" (string), "domain" (website domain without https://), '
        f'"description" (2-3 sentences), "sector" (one of: Enterprise SaaS, Fintech, '
        f"Healthcare IT, Cybersecurity, Data & Analytics, DevOps & Infrastructure, "
        f'HR Tech, Supply Chain & Logistics, MarTech & AdTech, Climate & Energy Tech, Legal Tech, PropTech), '
        f'"hq_location" (city, state/country), "founded_year" (integer), '
        f'"employee_count" (estimated integer), "total_raised_millions" (number or null), '
        f'"last_round_type" (e.g. Series A, Series B, etc. or null), '
        f'"last_round_amount_millions" (number or null), "last_round_date" (YYYY-MM-DD or null), '
        f'"valuation_millions" (number or null), "key_investors" (array of strings, up to 5). '
        f"Use null for any value you are not confident about."
        f"{web_context}"
    )

    result = _call_llm(COMPANY_LOOKUP_SYSTEM, user_prompt)
    parsed = _parse_json(result)

    if isinstance(parsed, dict) and parsed.get("name"):
        return parsed
    return None


def map_to_company(details: dict) -> Company:
    """Map an AI lookup response dict to our Company model.

    Private financials (ARR, growth, margin, retention) are left as None
    since the AI cannot reliably know these.
    """
    domain = details.get("domain")
    if domain:
        domain = domain.replace("https://", "").replace("http://", "").rstrip("/")

    return Company(
        name=details.get("name", "Unknown"),
        domain=domain,
        description=details.get("description"),
        sector=details.get("sector"),
        hq_location=details.get("hq_location"),
        founded_year=details.get("founded_year"),
        employee_count=details.get("employee_count"),
        arr_millions=None,
        revenue_growth_pct=None,
        gross_margin_pct=None,
        net_retention_pct=None,
        employee_growth_pct=None,
        total_raised_millions=details.get("total_raised_millions"),
        last_round_type=details.get("last_round_type"),
        last_round_amount_millions=details.get("last_round_amount_millions"),
        last_round_date=details.get("last_round_date"),
        last_valuation_millions=details.get("valuation_millions"),
        key_investors=details.get("key_investors", []),
        source="ai_lookup",
    )


# ═══════════════════════════════════════════════════════════════════════
# Scoring Engine (from services/scoring_engine.py)
# ═══════════════════════════════════════════════════════════════════════

def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


# --- Financial Score (1-10) ---

def _score_financial(c: dict) -> tuple[float, dict]:
    breakdown = {}

    arr = c.get("arr_millions") or 0
    if arr >= 50:
        arr_pts = 3.0
    elif arr >= 30:
        arr_pts = 2.5
    elif arr >= 15:
        arr_pts = 2.0
    elif arr >= 5:
        arr_pts = 1.0
    else:
        arr_pts = 0.5
    breakdown["arr_size"] = arr_pts

    growth = c.get("revenue_growth_pct") or 0
    if growth >= 120:
        growth_pts = 3.0
    elif growth >= 80:
        growth_pts = 2.5
    elif growth >= 40:
        growth_pts = 2.0
    elif growth >= 20:
        growth_pts = 1.0
    else:
        growth_pts = 0.5
    breakdown["revenue_growth"] = growth_pts

    margin = c.get("gross_margin_pct") or 0
    if margin >= 75:
        margin_pts = 2.0
    elif margin >= 65:
        margin_pts = 1.3
    elif margin >= 50:
        margin_pts = 0.8
    else:
        margin_pts = 0.3
    breakdown["gross_margin"] = margin_pts

    nrr = c.get("net_retention_pct") or 0
    if nrr >= 130:
        nrr_pts = 2.0
    elif nrr >= 110:
        nrr_pts = 1.3
    elif nrr >= 100:
        nrr_pts = 0.8
    else:
        nrr_pts = 0.3
    breakdown["net_retention"] = nrr_pts

    total = _clamp(arr_pts + growth_pts + margin_pts + nrr_pts)
    return total, breakdown


# --- Team Score (1-10) ---

def _score_team(c: dict) -> tuple[float, dict]:
    breakdown = {}

    emp = c.get("employee_count") or 0
    if emp >= 500:
        emp_pts = 3.0
    elif emp >= 150:
        emp_pts = 2.0
    elif emp >= 50:
        emp_pts = 1.0
    else:
        emp_pts = 0.5
    breakdown["employee_count"] = emp_pts

    hg = c.get("employee_growth_pct") or 0
    if hg >= 50:
        hg_pts = 3.0
    elif hg >= 25:
        hg_pts = 2.0
    elif hg >= 10:
        hg_pts = 1.0
    else:
        hg_pts = 0.5
    breakdown["headcount_growth"] = hg_pts

    raised = c.get("total_raised_millions") or 0
    if raised >= 100:
        inv_pts = 2.0
    elif raised >= 40:
        inv_pts = 1.3
    elif raised >= 15:
        inv_pts = 0.8
    else:
        inv_pts = 0.3
    breakdown["investor_quality"] = inv_pts

    founded = c.get("founded_year")
    if founded:
        age = datetime.now().year - founded
        if 4 <= age <= 8:
            mat_pts = 2.0
        elif 3 <= age <= 10:
            mat_pts = 1.3
        elif 2 <= age <= 12:
            mat_pts = 0.8
        else:
            mat_pts = 0.3
    else:
        mat_pts = 0.5
    breakdown["maturity"] = mat_pts

    total = _clamp(emp_pts + hg_pts + inv_pts + mat_pts)
    return total, breakdown


# --- Market Score (1-10) ---

def _score_market(c: dict) -> tuple[float, dict]:
    breakdown = {}

    sector = c.get("sector", "")
    attractiveness = SECTOR_ATTRACTIVENESS.get(sector, 5)
    sector_pts = (attractiveness / 10) * 4
    breakdown["sector_attractiveness"] = round(sector_pts, 1)

    arr = c.get("arr_millions") or 0
    growth = c.get("revenue_growth_pct") or 0
    rule_of_40 = growth + (c.get("gross_margin_pct") or 0) - 25
    if rule_of_40 >= 80:
        comp_pts = 3.0
    elif rule_of_40 >= 50:
        comp_pts = 2.0
    elif rule_of_40 >= 30:
        comp_pts = 1.0
    else:
        comp_pts = 0.5
    breakdown["competitive_position"] = comp_pts

    emp_growth = c.get("employee_growth_pct") or 0
    if emp_growth >= 40 and attractiveness >= 7:
        tam_pts = 3.0
    elif emp_growth >= 25 and attractiveness >= 6:
        tam_pts = 2.0
    elif emp_growth >= 10:
        tam_pts = 1.0
    else:
        tam_pts = 0.5
    breakdown["tam_indicators"] = tam_pts

    total = _clamp(sector_pts + comp_pts + tam_pts)
    return total, breakdown


# --- Product Score (1-10) ---

PLG_KEYWORDS = ["self-serve", "freemium", "product-led", "developer", "open source", "api-first", "plg"]
MOAT_KEYWORDS = ["proprietary", "patented", "network effect", "switching cost", "data moat", "platform", "ecosystem"]
CUSTOMER_KEYWORDS = ["enterprise", "fortune 500", "government", "multi-year", "contract"]


def _score_product(c: dict) -> tuple[float, dict]:
    desc = (c.get("description") or "").lower()
    breakdown = {}

    plg_hits = sum(1 for kw in PLG_KEYWORDS if kw in desc)
    plg_pts = min(3.0, plg_hits * 1.0) if plg_hits else 1.0
    breakdown["plg_signals"] = plg_pts

    moat_hits = sum(1 for kw in MOAT_KEYWORDS if kw in desc)
    arr = c.get("arr_millions") or 0
    nrr = c.get("net_retention_pct") or 0
    moat_base = min(2.0, moat_hits * 1.0) if moat_hits else 0.5
    moat_boost = 1.0 if arr >= 20 and nrr >= 115 else 0.5 if arr >= 10 else 0
    moat_pts = min(4.0, moat_base + moat_boost)
    breakdown["differentiation"] = moat_pts

    cust_hits = sum(1 for kw in CUSTOMER_KEYWORDS if kw in desc)
    cust_base = min(2.0, cust_hits * 1.0) if cust_hits else 0.5
    cust_boost = 1.0 if (c.get("gross_margin_pct") or 0) >= 70 else 0.3
    cust_pts = min(3.0, cust_base + cust_boost)
    breakdown["customer_signals"] = cust_pts

    total = _clamp(plg_pts + moat_pts + cust_pts)
    return total, breakdown


# --- Momentum Score (1-10) ---

def _score_momentum(c: dict) -> tuple[float, dict]:
    breakdown = {}

    last_date = c.get("last_round_date")
    if last_date:
        try:
            days_ago = (datetime.now() - datetime.strptime(last_date, "%Y-%m-%d")).days
            if days_ago <= 180:
                recency_pts = 3.0
            elif days_ago <= 365:
                recency_pts = 2.0
            elif days_ago <= 730:
                recency_pts = 1.0
            else:
                recency_pts = 0.3
        except ValueError:
            recency_pts = 0.5
    else:
        recency_pts = 0.5
    breakdown["round_recency"] = recency_pts

    hg = c.get("employee_growth_pct") or 0
    if hg >= 50:
        hg_pts = 3.0
    elif hg >= 30:
        hg_pts = 2.0
    elif hg >= 15:
        hg_pts = 1.0
    else:
        hg_pts = 0.3
    breakdown["headcount_trend"] = hg_pts

    company_id = c.get("id")
    news_count = 0
    if company_id:
        try:
            news = get_news(company_id)
            news_count = len(news)
        except Exception:
            pass
    if news_count >= 3:
        news_pts = 2.0
    elif news_count >= 1:
        news_pts = 1.0
    else:
        news_pts = 0.5
    breakdown["news_frequency"] = news_pts

    last_amt = c.get("last_round_amount_millions") or 0
    if last_amt >= 50:
        traj_pts = 2.0
    elif last_amt >= 20:
        traj_pts = 1.5
    elif last_amt >= 10:
        traj_pts = 1.0
    else:
        traj_pts = 0.3
    breakdown["round_trajectory"] = traj_pts

    total_score = _clamp(recency_pts + hg_pts + news_pts + traj_pts)
    return total_score, breakdown


# --- Composite Scoring ---

def compute_tier(score: float) -> str:
    if score >= 8.0:
        return "hot"
    elif score >= 6.0:
        return "warm"
    elif score >= 4.0:
        return "monitor"
    return "pass"


def score_company(company: dict, thesis: dict = None) -> dict:
    if thesis is None:
        thesis = get_default_thesis() or {}

    w_team = thesis.get("weight_team", 0.25)
    w_fin = thesis.get("weight_financial", 0.25)
    w_mkt = thesis.get("weight_market", 0.20)
    w_prod = thesis.get("weight_product", 0.15)
    w_mom = thesis.get("weight_momentum", 0.15)

    fin_score, fin_bd = _score_financial(company)
    team_score, team_bd = _score_team(company)
    mkt_score, mkt_bd = _score_market(company)
    prod_score, prod_bd = _score_product(company)
    mom_score, mom_bd = _score_momentum(company)

    composite = (
        w_fin * fin_score
        + w_team * team_score
        + w_mkt * mkt_score
        + w_prod * prod_score
        + w_mom * mom_score
    )

    breakdown = {
        "financial": fin_bd,
        "team": team_bd,
        "market": mkt_bd,
        "product": prod_bd,
        "momentum": mom_bd,
        "weights": {
            "financial": w_fin, "team": w_team, "market": w_mkt,
            "product": w_prod, "momentum": w_mom,
        },
    }

    result = {
        "company_id": company.get("id"),
        "thesis_id": thesis.get("id"),
        "team_score": round(team_score, 1),
        "financial_score": round(fin_score, 1),
        "market_score": round(mkt_score, 1),
        "product_score": round(prod_score, 1),
        "momentum_score": round(mom_score, 1),
        "composite_score": round(composite, 1),
        "tier": compute_tier(composite),
        "score_breakdown_json": json.dumps(breakdown),
    }
    return result


def score_all_companies(thesis: dict = None) -> list[dict]:
    companies = get_all_companies()
    results = []
    for c in companies:
        result = score_company(c, thesis)
        upsert_score(result)
        results.append(result)
    return results


# ═══════════════════════════════════════════════════════════════════════
# Memo Generator (from services/memo_generator.py)
# ═══════════════════════════════════════════════════════════════════════

def generate_memo_template(company: dict, score: dict = None) -> str:
    """Template-based memo generation (no LLM required)."""
    name = company.get("name", "Unknown")
    sector = company.get("sector", "N/A")
    arr = company.get("arr_millions", 0)
    growth = company.get("revenue_growth_pct", 0)
    margin = company.get("gross_margin_pct", 0)
    nrr = company.get("net_retention_pct", 0)
    emp = company.get("employee_count", 0)
    emp_growth = company.get("employee_growth_pct", 0)
    raised = company.get("total_raised_millions", 0)
    last_round = company.get("last_round_type", "N/A")
    last_amt = company.get("last_round_amount_millions", 0)
    valuation = company.get("last_valuation_millions", 0)
    description = company.get("description", "N/A")
    investors = company.get("key_investors", [])
    if isinstance(investors, str):
        try:
            investors = json.loads(investors)
        except (json.JSONDecodeError, TypeError):
            investors = []

    composite = score.get("composite_score", 0) if score else 0
    tier = (score.get("tier", "N/A") if score else "N/A").upper()

    rule_of_40 = (growth or 0) + (margin or 0) - 25
    arr_multiple = (valuation / arr) if arr and valuation else 0

    memo = f"""# Investment Memo: {name}
**Generated:** {datetime.now().strftime('%B %d, %Y')}
**Prepared by:** Growth Equity Radar (Auto-Generated)

---

## Executive Summary

{name} is a {sector} company operating in the growth stage with **${arr:.1f}M ARR** growing at **{growth:.0f}% YoY**. The company has raised **${raised:.1f}M** to date, most recently a **{last_round} round of ${last_amt:.1f}M**{f' at a ${valuation:.0f}M valuation ({arr_multiple:.1f}x ARR)' if valuation else ''}.

**Composite Score: {composite:.1f}/10 ({tier})**

{description}

---

## Financial Profile

| Metric | Value | Assessment |
|--------|-------|------------|
| ARR | ${arr:.1f}M | {"Strong" if arr >= 20 else "Moderate" if arr >= 10 else "Early"} |
| Revenue Growth | {growth:.0f}% YoY | {"Exceptional" if growth >= 80 else "Strong" if growth >= 40 else "Moderate" if growth >= 20 else "Slow"} |
| Gross Margin | {margin:.0f}% | {"Best-in-class" if margin >= 80 else "Healthy" if margin >= 65 else "Below target" if margin >= 50 else "Concerning"} |
| Net Retention | {nrr:.0f}% | {"Elite" if nrr >= 130 else "Strong" if nrr >= 115 else "Acceptable" if nrr >= 100 else "Concerning"} |
| Rule of 40 | {rule_of_40:.0f} | {"Exceeds" if rule_of_40 >= 40 else "Approaches" if rule_of_40 >= 30 else "Below"} threshold |

---

## Team & Organization

- **Headcount:** {emp:,} employees
- **Growth:** {emp_growth:.0f}% headcount growth YoY
- **Signal:** {"Aggressive hiring suggests strong demand and confidence" if emp_growth >= 30 else "Moderate growth trajectory" if emp_growth >= 15 else "Conservative hiring — watch for efficiency focus"}

---

## Funding & Capitalization

- **Total Raised:** ${raised:.1f}M
- **Last Round:** {last_round} — ${last_amt:.1f}M
- **Valuation:** {f'${valuation:.0f}M ({arr_multiple:.1f}x ARR multiple)' if valuation else 'N/A'}
- **Key Investors:** {', '.join(investors) if investors else 'N/A'}

---

## Investment Considerations

### Strengths
{_generate_strengths(company)}

### Risks
{_generate_risks(company)}

### Key Questions for Diligence
{_generate_questions(company)}

---

## Recommendation

{"**STRONG FIT** — This company meets or exceeds growth equity criteria across key dimensions. Recommend advancing to deep dive." if composite >= 8 else "**GOOD FIT** — Solid fundamentals with some areas to investigate. Recommend advancing to screening." if composite >= 6 else "**MONITOR** — Interesting profile but gaps in key criteria. Add to watchlist and revisit in 6 months." if composite >= 4 else "**PASS** — Does not meet current thesis criteria. Consider revisiting if fundamentals improve."}
"""
    return memo


def _generate_strengths(c: dict) -> str:
    strengths = []
    if (c.get("revenue_growth_pct") or 0) >= 60:
        strengths.append(f"- Strong revenue velocity at {c['revenue_growth_pct']:.0f}% YoY growth")
    if (c.get("gross_margin_pct") or 0) >= 70:
        strengths.append(f"- Healthy gross margins of {c['gross_margin_pct']:.0f}% indicate scalable economics")
    if (c.get("net_retention_pct") or 0) >= 115:
        strengths.append(f"- Net retention of {c['net_retention_pct']:.0f}% signals strong product-market fit")
    if (c.get("employee_growth_pct") or 0) >= 30:
        strengths.append(f"- Aggressive hiring ({c['employee_growth_pct']:.0f}% growth) suggests confidence in pipeline")
    if (c.get("arr_millions") or 0) >= 20:
        strengths.append(f"- Proven scale at ${c['arr_millions']:.1f}M ARR with institutional investor backing")
    if not strengths:
        strengths.append("- Early-stage company with growth potential in an active market")
    return "\n".join(strengths[:4])


def _generate_risks(c: dict) -> str:
    risks = []
    if (c.get("gross_margin_pct") or 0) < 65:
        risks.append(f"- Below-target gross margins ({c.get('gross_margin_pct', 0):.0f}%) may limit profitability path")
    if (c.get("net_retention_pct") or 0) < 110:
        risks.append(f"- Net retention ({c.get('net_retention_pct', 0):.0f}%) below growth equity standard of 110%+")
    if (c.get("revenue_growth_pct") or 0) < 30:
        risks.append(f"- Decelerating growth ({c.get('revenue_growth_pct', 0):.0f}%) may signal market saturation")
    if (c.get("employee_growth_pct") or 0) < 10:
        risks.append("- Flat headcount growth raises questions about scaling capacity")
    if not risks:
        risks.append("- Limited public data available; diligence needed on competitive dynamics and customer concentration")
    return "\n".join(risks[:4])


def _generate_questions(c: dict) -> str:
    questions = [
        "1. What is the customer acquisition cost (CAC) and payback period?",
        "2. What is the competitive landscape and key differentiation?",
        "3. What is the path to profitability and current burn rate?",
    ]
    if (c.get("arr_millions") or 0) >= 30:
        questions.append("4. Is the company evaluating IPO or strategic exit timelines?")
    else:
        questions.append("4. What are the next 12-month growth levers and investment priorities?")
    return "\n".join(questions)


def generate_memo_ai(company: dict, score: dict = None) -> str:
    """AI-powered memo generation using LLM."""
    company_context = json.dumps({
        k: v for k, v in company.items()
        if k not in ("ai_memo", "ai_summary", "created_at", "updated_at")
    }, default=str)

    score_context = json.dumps(score, default=str) if score else "N/A"
    prompt = MEMO_AI_PROMPT.format(company_context=company_context, score_context=score_context)

    try:
        if ANTHROPIC_API_KEY:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-sonnet-4-6-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        elif OPENAI_API_KEY:
            import openai
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
    except Exception as e:
        return f"AI memo generation failed: {e}\n\n" + generate_memo_template(company, score)

    return generate_memo_template(company, score)


def generate_memo(company: dict, score: dict = None) -> str:
    """Generate memo using AI if available, template otherwise."""
    if DEMO_MODE:
        memo = generate_memo_template(company, score)
    else:
        memo = generate_memo_ai(company, score)
    log_activity(company.get("id"), "memo_generated", f"Memo for {company.get('name', 'Unknown')}")
    return memo


# ═══════════════════════════════════════════════════════════════════════
# Thesis Matcher (from services/thesis_matcher.py)
# ═══════════════════════════════════════════════════════════════════════

def match_thesis_rule_based(company: dict, thesis: dict) -> dict:
    """Rule-based thesis matching. Returns fit percentage and explanation bullets."""
    criteria_json = thesis.get("criteria_json", "{}")
    try:
        criteria_data = json.loads(criteria_json) if isinstance(criteria_json, str) else criteria_json
    except (json.JSONDecodeError, TypeError):
        criteria_data = {}
    criteria = ThesisCriteria(**{k: v for k, v in criteria_data.items() if k in ThesisCriteria.model_fields})

    matches = []
    misses = []
    total_checks = 0
    passed_checks = 0

    # ARR range check
    arr = company.get("arr_millions") or 0
    total_checks += 1
    if criteria.min_arr <= arr <= criteria.max_arr:
        passed_checks += 1
        matches.append(f"ARR ${arr:.1f}M within target range (${criteria.min_arr:.0f}-${criteria.max_arr:.0f}M)")
    else:
        if arr < criteria.min_arr:
            misses.append(f"ARR ${arr:.1f}M below minimum ${criteria.min_arr:.0f}M")
        else:
            misses.append(f"ARR ${arr:.1f}M above maximum ${criteria.max_arr:.0f}M")

    # Growth threshold
    growth = company.get("revenue_growth_pct") or 0
    total_checks += 1
    if growth >= criteria.min_growth_pct:
        passed_checks += 1
        matches.append(f"Revenue growth {growth:.0f}% exceeds {criteria.min_growth_pct:.0f}% threshold")
    else:
        misses.append(f"Revenue growth {growth:.0f}% below {criteria.min_growth_pct:.0f}% threshold")

    # Sector fit
    if criteria.sectors:
        total_checks += 1
        sector = company.get("sector", "")
        if sector in criteria.sectors:
            passed_checks += 1
            matches.append(f"Sector '{sector}' is a target sector")
        else:
            misses.append(f"Sector '{sector}' not in target sectors")

    # Gross margin
    if criteria.min_gross_margin_pct > 0:
        total_checks += 1
        margin = company.get("gross_margin_pct") or 0
        if margin >= criteria.min_gross_margin_pct:
            passed_checks += 1
            matches.append(f"Gross margin {margin:.0f}% above {criteria.min_gross_margin_pct:.0f}% floor")
        else:
            misses.append(f"Gross margin {margin:.0f}% below {criteria.min_gross_margin_pct:.0f}% floor")

    # Net retention
    if criteria.min_net_retention_pct > 0:
        total_checks += 1
        nrr = company.get("net_retention_pct") or 0
        if nrr >= criteria.min_net_retention_pct:
            passed_checks += 1
            matches.append(f"Net retention {nrr:.0f}% above {criteria.min_net_retention_pct:.0f}% floor")
        else:
            misses.append(f"Net retention {nrr:.0f}% below {criteria.min_net_retention_pct:.0f}% floor")

    # Round type
    if criteria.round_types:
        total_checks += 1
        round_type = company.get("last_round_type", "")
        if round_type in criteria.round_types:
            passed_checks += 1
            matches.append(f"Round type '{round_type}' matches target stages")
        else:
            misses.append(f"Round type '{round_type}' not in target stages")

    fit_pct = (passed_checks / total_checks * 100) if total_checks > 0 else 0

    return {
        "fit_pct": round(fit_pct, 0),
        "matches": matches,
        "misses": misses,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
    }


def match_thesis_ai(company: dict, thesis: dict) -> dict:
    """AI-powered thesis matching using LLM."""
    thesis_desc = thesis.get("description", "Growth equity thesis")
    company_summary = (
        f"{company.get('name', 'Unknown')} — {company.get('description', 'N/A')}. "
        f"Sector: {company.get('sector', 'N/A')}. ARR: ${company.get('arr_millions', 0):.1f}M. "
        f"Growth: {company.get('revenue_growth_pct', 0):.0f}%. "
        f"Gross Margin: {company.get('gross_margin_pct', 0):.0f}%. "
        f"Net Retention: {company.get('net_retention_pct', 0):.0f}%. "
        f"Employees: {company.get('employee_count', 0)}. "
        f"Last Round: {company.get('last_round_type', 'N/A')} ${company.get('last_round_amount_millions', 0):.1f}M."
    )

    prompt = THESIS_MATCH_PROMPT.format(thesis_desc=thesis_desc, company_summary=company_summary)

    try:
        if ANTHROPIC_API_KEY:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-sonnet-4-6-20250514",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
        elif OPENAI_API_KEY:
            import openai
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.choices[0].message.content
        else:
            return match_thesis_rule_based(company, thesis)

        result = json.loads(text)
        return {
            "fit_score": result.get("score", 5),
            "rationale": result.get("rationale", []),
            "method": "ai",
        }
    except Exception:
        return match_thesis_rule_based(company, thesis)


def match_thesis(company: dict, thesis: dict) -> dict:
    """Match company to thesis, using AI if available, rule-based otherwise."""
    if DEMO_MODE:
        return match_thesis_rule_based(company, thesis)
    return match_thesis_ai(company, thesis)


# ═══════════════════════════════════════════════════════════════════════
# Enrichment (from services/enrichment.py)
# ═══════════════════════════════════════════════════════════════════════

def generate_summary_template(company: dict) -> str:
    """Template-based summary for demo mode."""
    name = company.get("name", "Unknown")
    sector = company.get("sector", "N/A")
    arr = company.get("arr_millions", 0)
    growth = company.get("revenue_growth_pct", 0)
    margin = company.get("gross_margin_pct", 0)
    nrr = company.get("net_retention_pct", 0)
    emp = company.get("employee_count", 0)
    last_round = company.get("last_round_type", "N/A")
    desc = company.get("description", "")

    strength = "rapidly scaling" if growth >= 80 else "steadily growing" if growth >= 40 else "early-stage"
    margin_note = "best-in-class margins" if margin >= 75 else "healthy unit economics" if margin >= 65 else "developing margins"
    retention_note = f"with {nrr:.0f}% net retention indicating strong expansion" if nrr >= 115 else f"with {nrr:.0f}% net retention"

    return (
        f"{name} is a {strength} {sector} company with ${arr:.1f}M ARR growing {growth:.0f}% YoY. "
        f"The company demonstrates {margin_note} at {margin:.0f}% gross margin, {retention_note}. "
        f"With {emp:,} employees and backed by a {last_round} round, {name} is "
        f"{'well-positioned for growth equity investment' if arr >= 15 and growth >= 40 else 'building toward growth equity readiness'}. "
        f"{desc}"
    )


def generate_summary_ai(company: dict) -> str:
    """AI-powered company summary."""
    company_data = json.dumps({k: v for k, v in company.items()
                                if k not in ("ai_summary", "ai_memo", "created_at", "updated_at")}, default=str)
    prompt = ENRICHMENT_PROMPT.format(company_data=company_data)
    try:
        if ANTHROPIC_API_KEY:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            resp = client.messages.create(model="claude-sonnet-4-6-20250514", max_tokens=300,
                                          messages=[{"role": "user", "content": prompt}])
            return resp.content[0].text
        elif OPENAI_API_KEY:
            import openai
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(model="gpt-4o-mini", max_tokens=300,
                                                   messages=[{"role": "user", "content": prompt}])
            return resp.choices[0].message.content
    except Exception:
        pass
    return generate_summary_template(company)


def enrich_company(company: dict) -> str:
    """Generate and save AI summary for a company."""
    if DEMO_MODE:
        summary = generate_summary_template(company)
    else:
        summary = generate_summary_ai(company)
    if company.get("id"):
        update_company(company["id"], {"ai_summary": summary})
    return summary
