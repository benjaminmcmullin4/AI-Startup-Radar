"""
Composite scoring algorithm for growth equity deal evaluation.

Five dimensions scored 1-10:
  Financial (default 25%): ARR size + revenue growth + gross margin + net retention
  Team (25%): Employee count + headcount growth + investor quality + company maturity
  Market (20%): Sector attractiveness + competitive signals + TAM indicators
  Product (15%): PLG signals + moat/differentiation + customer signals
  Momentum (15%): Round recency + headcount trend + news frequency + round trajectory
"""

import json
from datetime import datetime
from db.database import get_all_companies, upsert_score, get_default_thesis, get_news


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


# --- Financial Score (1-10) ---

def _score_financial(c: dict) -> tuple[float, dict]:
    breakdown = {}

    # ARR size (0-3): $0-5M=0.5, $5-15M=1, $15-30M=2, $30-50M=2.5, $50M+=3
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

    # Revenue growth (0-3): <20%=0.5, 20-40%=1, 40-80%=2, 80-120%=2.5, 120%+=3
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

    # Gross margin (0-2): <50%=0.3, 50-65%=0.8, 65-75%=1.3, 75%+=2
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

    # Net retention (0-2): <100%=0.3, 100-110%=0.8, 110-130%=1.3, 130%+=2
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

    # Employee count (0-3): <50=0.5, 50-150=1, 150-500=2, 500+=3
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

    # Headcount growth (0-3): <10%=0.5, 10-25%=1, 25-50%=2, 50%+=3
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

    # Investor quality (0-2): based on total raised as proxy
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

    # Maturity sweet spot (0-2): founded 4-8 years ago is ideal for growth equity
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

SECTOR_ATTRACTIVENESS = {
    "Cybersecurity": 9, "Enterprise SaaS": 8, "Healthcare IT": 8,
    "Data & Analytics": 8, "Fintech": 7, "DevOps & Infrastructure": 7,
    "Supply Chain & Logistics": 7, "Climate & Energy Tech": 7,
    "HR Tech": 6, "MarTech & AdTech": 6, "Legal Tech": 6, "PropTech": 5,
}


def _score_market(c: dict) -> tuple[float, dict]:
    breakdown = {}

    # Sector attractiveness (0-4)
    sector = c.get("sector", "")
    attractiveness = SECTOR_ATTRACTIVENESS.get(sector, 5)
    sector_pts = (attractiveness / 10) * 4
    breakdown["sector_attractiveness"] = round(sector_pts, 1)

    # Competitive position signals (0-3): higher ARR + growth = stronger position
    arr = c.get("arr_millions") or 0
    growth = c.get("revenue_growth_pct") or 0
    rule_of_40 = growth + (c.get("gross_margin_pct") or 0) - 25  # simplified proxy
    if rule_of_40 >= 80:
        comp_pts = 3.0
    elif rule_of_40 >= 50:
        comp_pts = 2.0
    elif rule_of_40 >= 30:
        comp_pts = 1.0
    else:
        comp_pts = 0.5
    breakdown["competitive_position"] = comp_pts

    # TAM indicators (0-3): use employee count growth + sector as proxy
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

    # PLG signals (0-3)
    plg_hits = sum(1 for kw in PLG_KEYWORDS if kw in desc)
    plg_pts = min(3.0, plg_hits * 1.0) if plg_hits else 1.0
    breakdown["plg_signals"] = plg_pts

    # Differentiation/moat (0-4)
    moat_hits = sum(1 for kw in MOAT_KEYWORDS if kw in desc)
    # Higher ARR and margins suggest stronger moat
    arr = c.get("arr_millions") or 0
    nrr = c.get("net_retention_pct") or 0
    moat_base = min(2.0, moat_hits * 1.0) if moat_hits else 0.5
    moat_boost = 1.0 if arr >= 20 and nrr >= 115 else 0.5 if arr >= 10 else 0
    moat_pts = min(4.0, moat_base + moat_boost)
    breakdown["differentiation"] = moat_pts

    # Customer signals (0-3)
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

    # Recency of last round (0-3)
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

    # Headcount growth trend (0-3)
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

    # News frequency (0-2): check for associated news items
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

    # Round size trajectory (0-2)
    last_amt = c.get("last_round_amount_millions") or 0
    total = c.get("total_raised_millions") or 0
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
