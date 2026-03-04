"""LLM-powered enrichment: AI summaries and 'why this matters' analysis."""

import json
from config.settings import DEMO_MODE, OPENAI_API_KEY, ANTHROPIC_API_KEY
from db.database import update_company


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
    prompt = (
        f"Write a 2-3 sentence growth equity analyst summary for this company. "
        f"Focus on ARR, growth trajectory, unit economics, and investment readiness.\n\n{company_data}"
    )
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
