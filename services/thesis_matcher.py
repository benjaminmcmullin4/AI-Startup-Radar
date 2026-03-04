"""
Thesis matching: evaluates how well a company fits a specific investment thesis.
- Rule-based mode (no API): checks criteria against company fields, produces fit % + explanation
- AI mode (with API): LLM scores fit 1-10 with rationale
"""

import json
from models.scoring import ThesisCriteria
from config.settings import DEMO_MODE, OPENAI_API_KEY, ANTHROPIC_API_KEY


def match_thesis_rule_based(company: dict, thesis: dict) -> dict:
    """Rule-based thesis matching. Returns fit percentage and explanation bullets."""
    criteria = ThesisCriteria.from_json(thesis.get("criteria_json", "{}"))
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

    prompt = f"""You are a growth equity analyst. Score how well this company fits the investment thesis.

THESIS: {thesis_desc}

COMPANY: {company_summary}

Score the fit from 1-10 and provide exactly 3 bullet points explaining your rationale.
Respond in JSON format: {{"score": <int>, "rationale": ["bullet1", "bullet2", "bullet3"]}}"""

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
