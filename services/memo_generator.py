"""Investment memo generation — template-based (demo) or AI-powered."""

import json
from datetime import datetime
from config.settings import DEMO_MODE, OPENAI_API_KEY, ANTHROPIC_API_KEY
from utils.formatting import fmt_money, fmt_pct
from db.database import log_activity


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

    # Rule of 40
    rule_of_40 = (growth or 0) + (margin or 0) - 25  # simplified with margin proxy

    # Implied ARR multiple
    arr_multiple = (valuation / arr) if arr and valuation else 0

    memo = f"""# Investment Memo: {name}
**Generated:** {datetime.now().strftime('%B %d, %Y')}
**Prepared by:** Mercato Partners — Traverse Fund (Auto-Generated)

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

    prompt = f"""You are a senior growth equity analyst at Mercato Partners (Traverse Fund) writing an investment memo for IC review. Mercato focuses on growth-stage technology companies in underserved, non-coastal geographies with strong organic growth (40-200% YoY), proven unit economics, and category-leading potential.

COMPANY DATA: {company_context}

SCORE DATA: {json.dumps(score, default=str) if score else 'N/A'}

Write a professional investment memo with these sections:
1. Executive Summary (2-3 sentences)
2. Financial Profile (key metrics table)
3. Team & Organization
4. Funding & Capitalization
5. Investment Considerations (strengths, risks, diligence questions)
6. Traverse Fit Assessment (how this aligns with Mercato's growth equity thesis)
7. Recommendation (Strong Fit / Good Fit / Monitor / Pass with reasoning)

Use specific numbers from the data. Be direct and analytical."""

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
