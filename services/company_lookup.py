"""AI-powered company lookup using existing LLM API keys."""

import json
import logging
import re
from typing import Optional

from config.settings import OPENAI_API_KEY, ANTHROPIC_API_KEY, TAVILY_API_KEY
from models.company import Company

logger = logging.getLogger(__name__)


def is_lookup_available() -> bool:
    """Return True if any AI API key is configured."""
    return bool(OPENAI_API_KEY or ANTHROPIC_API_KEY)


def _call_llm(system: str, user: str) -> Optional[str]:
    """Call an LLM with Anthropic-first, OpenAI-fallback pattern. Returns raw text."""
    try:
        if ANTHROPIC_API_KEY:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            resp = client.messages.create(
                model="claude-sonnet-4-5-20241022",
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
    # Strip markdown code fences
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


SYSTEM_PROMPT = (
    "You are a startup research assistant. Return ONLY valid JSON, no markdown fences, "
    "no commentary. Use null for unknown values. Do not fabricate financial figures — "
    "only include data you are confident about."
)


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

    result = _call_llm(SYSTEM_PROMPT, user_prompt)
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

    # Try Tavily web searches for real-time data
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

    result = _call_llm(SYSTEM_PROMPT, user_prompt)
    parsed = _parse_json(result)

    if isinstance(parsed, dict) and parsed.get("name"):
        return parsed
    return None


def map_to_company(details: dict) -> Company:
    """Map an AI lookup response dict to our Company dataclass.

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
        # Private financials — not available from AI lookup
        arr_millions=None,
        revenue_growth_pct=None,
        gross_margin_pct=None,
        net_retention_pct=None,
        employee_growth_pct=None,
        # Funding data
        total_raised_millions=details.get("total_raised_millions"),
        last_round_type=details.get("last_round_type"),
        last_round_amount_millions=details.get("last_round_amount_millions"),
        last_round_date=details.get("last_round_date"),
        last_valuation_millions=details.get("valuation_millions"),
        key_investors=details.get("key_investors", []),
        source="ai_lookup",
    )
