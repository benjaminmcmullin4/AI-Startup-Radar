"""Crunchbase API client for searching and importing real startup data."""

import logging
from typing import Optional

import requests

from config.settings import CRUNCHBASE_API_KEY
from models.company import Company

logger = logging.getLogger(__name__)

BASE_URL = "https://api.crunchbase.com/api/v4"
TIMEOUT = 15


def is_crunchbase_configured() -> bool:
    return bool(CRUNCHBASE_API_KEY)


def _headers() -> dict:
    return {"X-cb-user-key": CRUNCHBASE_API_KEY}


def search_organizations(query: str, limit: int = 10) -> list[dict]:
    """Search Crunchbase organizations by name using the autocomplete endpoint.

    Returns list of dicts with: uuid, name, permalink, short_description.
    """
    if not is_crunchbase_configured():
        return []

    try:
        resp = requests.get(
            f"{BASE_URL}/autocompletes",
            headers=_headers(),
            params={
                "query": query,
                "collection_ids": "organizations",
                "limit": min(limit, 25),
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for entity in data.get("entities", []):
            ident = entity.get("identifier", {})
            results.append({
                "uuid": ident.get("uuid", ""),
                "name": ident.get("value", ""),
                "permalink": ident.get("permalink", ""),
                "short_description": entity.get("short_description", ""),
            })
        return results

    except requests.RequestException as e:
        logger.error("Crunchbase search failed: %s", e)
        return []


def get_organization(permalink: str) -> Optional[dict]:
    """Fetch full organization details from Crunchbase by permalink.

    Uses card_ids to pull funding_rounds and investors in a single call.
    """
    if not is_crunchbase_configured() or not permalink:
        return None

    try:
        resp = requests.get(
            f"{BASE_URL}/entities/organizations/{permalink}",
            headers=_headers(),
            params={
                "card_ids": "funding_rounds,investors",
                "field_ids": (
                    "name,short_description,categories,location_identifiers,"
                    "founded_on,num_employees_enum,website_url,"
                    "funding_total,last_funding_type,last_funding_at,"
                    "valuation,identifier"
                ),
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    except requests.RequestException as e:
        logger.error("Crunchbase org fetch failed for %s: %s", permalink, e)
        return None


def _parse_employee_enum(enum_value: Optional[str]) -> Optional[int]:
    """Convert Crunchbase employee count enum to a numeric midpoint estimate."""
    mapping = {
        "c_00001_00010": 5,
        "c_00011_00050": 30,
        "c_00051_00100": 75,
        "c_00101_00250": 175,
        "c_00251_00500": 375,
        "c_00501_01000": 750,
        "c_01001_05000": 3000,
        "c_05001_10000": 7500,
        "c_10001_max": 15000,
    }
    return mapping.get(enum_value)


def _extract_money_usd(money_obj: Optional[dict]) -> Optional[float]:
    """Extract USD millions from a Crunchbase money object."""
    if not money_obj:
        return None
    value = money_obj.get("value")
    currency = money_obj.get("currency", "USD")
    if value is not None and currency == "USD":
        return round(value / 1_000_000, 2)
    return None


def _extract_location(location_ids: Optional[list]) -> Optional[str]:
    """Build a location string from Crunchbase location identifiers."""
    if not location_ids:
        return None
    parts = []
    for loc in location_ids:
        loc_type = loc.get("location_type", "")
        if loc_type in ("city", "region", "country"):
            parts.append(loc.get("value", ""))
    return ", ".join(parts) if parts else None


def _extract_sector(categories: Optional[list]) -> Optional[str]:
    """Pick the first Crunchbase category as sector."""
    if not categories:
        return None
    return categories[0].get("value", None)


def _extract_last_round(cards: dict) -> tuple[Optional[str], Optional[float], Optional[str]]:
    """Extract last funding round type, amount, and date from funding_rounds card."""
    rounds = cards.get("funding_rounds", {}).get("items", [])
    if not rounds:
        return None, None, None

    last = rounds[0]  # Crunchbase returns most recent first
    props = last.get("properties", {})
    round_type = props.get("investment_type") or props.get("funding_type")
    amount = _extract_money_usd(props.get("money_raised"))
    date = props.get("announced_on")
    return round_type, amount, date


def _extract_investors(cards: dict) -> list[str]:
    """Extract investor names from the investors card."""
    investors_card = cards.get("investors", {}).get("items", [])
    names = []
    for inv in investors_card:
        ident = inv.get("identifier", {})
        name = ident.get("value")
        if name:
            names.append(name)
    return names[:10]  # Cap at 10 investors


def map_to_company(org_data: dict) -> Company:
    """Map a Crunchbase organization API response to our Company dataclass.

    Financial metrics (ARR, revenue growth, gross margin, net retention) are
    left as None since Crunchbase doesn't provide private financial data.
    """
    props = org_data.get("properties", {})
    cards = org_data.get("cards", {})

    # Basic info
    name = props.get("name", props.get("identifier", {}).get("value", "Unknown"))
    permalink = props.get("identifier", {}).get("permalink", "")
    domain = props.get("website_url")
    if domain:
        domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
    description = props.get("short_description")

    # Sector / location / founding
    sector = _extract_sector(props.get("categories"))
    hq_location = _extract_location(props.get("location_identifiers"))
    founded_on = props.get("founded_on")
    founded_year = int(founded_on[:4]) if founded_on and len(founded_on) >= 4 else None

    # Team
    employee_count = _parse_employee_enum(props.get("num_employees_enum"))

    # Funding
    total_raised = _extract_money_usd(props.get("funding_total"))
    valuation = _extract_money_usd(props.get("valuation"))
    last_round_type, last_round_amount, last_round_date = _extract_last_round(cards)
    key_investors = _extract_investors(cards)

    return Company(
        name=name,
        domain=domain,
        description=description,
        sector=sector,
        hq_location=hq_location,
        founded_year=founded_year,
        employee_count=employee_count,
        # Private financials — not available from Crunchbase
        arr_millions=None,
        revenue_growth_pct=None,
        gross_margin_pct=None,
        net_retention_pct=None,
        employee_growth_pct=None,
        # Funding data
        total_raised_millions=total_raised,
        last_round_type=last_round_type,
        last_round_amount_millions=last_round_amount,
        last_round_date=last_round_date,
        last_valuation_millions=valuation,
        key_investors=key_investors,
        source="crunchbase",
    )
