"""News ingestion (RSS) and weekly digest generation."""

from __future__ import annotations

from datetime import datetime, timedelta

import feedparser

from db import (
    get_activity_log,
    get_all_companies,
    get_companies_with_scores,
    get_news,
    insert_news,
)


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


def fmt_score(score: float) -> str:
    if score is None:
        return "N/A"
    return f"{score:.1f}"


def fmt_number(value: int) -> str:
    if value is None:
        return "N/A"
    if value >= 1000:
        return f"{value:,.0f}"
    return str(value)


# ═══════════════════════════════════════════════════════════════════════
# News Ingestion (from services/news_ingestion.py)
# ═══════════════════════════════════════════════════════════════════════

FUNDING_RSS_FEEDS = [
    "https://techcrunch.com/category/fundraising/feed/",
    "https://news.crunchbase.com/feed/",
]

GROWTH_KEYWORDS = [
    "series b", "series c", "series d", "growth round", "growth equity",
    "raises", "funding", "million", "valuation",
]


def fetch_funding_news(feeds: list[str] | None = None) -> list[dict]:
    """Fetch and parse RSS feeds for funding-related news."""
    feeds = feeds or FUNDING_RSS_FEEDS
    items: list[dict] = []
    for feed_url in feeds:
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:20]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                combined = (title + " " + summary).lower()

                # Filter for growth-stage funding news
                if any(kw in combined for kw in GROWTH_KEYWORDS):
                    items.append({
                        "title": title,
                        "url": entry.get("link", ""),
                        "source": parsed.feed.get("title", "RSS"),
                        "published_date": _parse_date(entry),
                        "summary": summary[:500],
                        "category": "funding",
                    })
        except Exception:
            continue
    return items


def _parse_date(entry) -> str:
    """Extract and format published date from RSS entry."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6]).strftime("%Y-%m-%d")
            except Exception:
                pass
    return datetime.now().strftime("%Y-%m-%d")


def match_news_to_companies(news_items: list[dict]) -> list[dict]:
    """Try to match news items to existing companies by name."""
    companies = get_all_companies()
    company_names = {c["name"].lower(): c["id"] for c in companies}

    matched: list[dict] = []
    for item in news_items:
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()
        for name, cid in company_names.items():
            if name in text:
                item["company_id"] = cid
                matched.append(item)
                break
        else:
            # Unmatched news still gets stored
            item["company_id"] = None
            matched.append(item)
    return matched


def ingest_news() -> int:
    """Full ingestion pipeline: fetch, match, store."""
    raw_items = fetch_funding_news()
    matched = match_news_to_companies(raw_items)
    count = 0
    for item in matched:
        insert_news(item)
        count += 1
    return count


# ═══════════════════════════════════════════════════════════════════════
# Digest Generator (from services/digest_generator.py)
# ═══════════════════════════════════════════════════════════════════════

def generate_digest(start_date: str | None = None, end_date: str | None = None) -> str:
    """Generate a weekly digest markdown document."""
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    companies = get_companies_with_scores()
    activities = get_activity_log(limit=200)
    news = get_news(limit=50)

    # Filter activities by date range
    period_activities: list[dict] = []
    for a in activities:
        ts = a.get("created_at", "")
        if ts and start_date <= ts[:10] <= end_date:
            period_activities.append(a)

    # Categorize companies
    hot_deals = [c for c in companies if c.get("tier") == "hot"]
    warm_deals = [c for c in companies if c.get("tier") == "warm"]

    # New additions in period
    new_additions = [a for a in period_activities if a.get("action") == "imported"]

    # Stage movements
    stage_changes = [a for a in period_activities if a.get("action") == "stage_changed"]

    # Summary stats
    total = len(companies)
    scored = [c for c in companies if c.get("composite_score")]
    avg_score = sum(c["composite_score"] for c in scored) / len(scored) if scored else 0
    active = sum(1 for c in companies if c.get("pipeline_stage") in ("screening", "deep_dive", "ic_review"))

    digest = f"""# Growth Equity Radar — Weekly Deal Flow Digest
**Period:** {start_date} to {end_date}
**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

---

## Executive Summary

- **Total Pipeline:** {total} companies tracked
- **Active Pipeline:** {active} companies in screening or later stages
- **Average Score:** {avg_score:.1f}/10
- **Hot Deals:** {len(hot_deals)} companies scoring 8.0+
- **New Additions:** {len(new_additions)} companies added this period

---

## Hot Deals ({len(hot_deals)})

Companies scoring 8.0+ on composite score — recommend IC review.

| Company | Sector | ARR | Growth | Score | Stage |
|---------|--------|-----|--------|-------|-------|
"""

    for c in sorted(hot_deals, key=lambda x: x.get("composite_score", 0), reverse=True)[:10]:
        digest += (
            f"| {c.get('name', '—')} | {c.get('sector', '—')} | "
            f"{fmt_money(c.get('arr_millions'))} | {fmt_pct(c.get('revenue_growth_pct'))} | "
            f"{fmt_score(c.get('composite_score'))} | {c.get('pipeline_stage', '—').replace('_', ' ').title()} |\n"
        )

    digest += f"""
---

## Warm Pipeline ({len(warm_deals)})

Companies scoring 6.0-7.9 — worth screening.

| Company | Sector | ARR | Growth | Score |
|---------|--------|-----|--------|-------|
"""

    for c in sorted(warm_deals, key=lambda x: x.get("composite_score", 0), reverse=True)[:10]:
        digest += (
            f"| {c.get('name', '—')} | {c.get('sector', '—')} | "
            f"{fmt_money(c.get('arr_millions'))} | {fmt_pct(c.get('revenue_growth_pct'))} | "
            f"{fmt_score(c.get('composite_score'))} |\n"
        )

    digest += "\n---\n\n## New Additions\n\n"
    if new_additions:
        for a in new_additions[:15]:
            digest += f"- **{a.get('company_name', 'Unknown')}** — {a.get('details', '')}\n"
    else:
        digest += "_No new companies added this period._\n"

    digest += "\n---\n\n## Stage Movements\n\n"
    if stage_changes:
        for a in stage_changes[:15]:
            digest += f"- **{a.get('company_name', 'Unknown')}** — {a.get('details', '')}\n"
    else:
        digest += "_No stage changes this period._\n"

    digest += f"""
---

## Thesis Match Highlights

Top companies with strongest thesis alignment:

"""
    top_5 = sorted(companies, key=lambda x: x.get("composite_score", 0), reverse=True)[:5]
    for i, c in enumerate(top_5, 1):
        digest += (
            f"{i}. **{c.get('name', '—')}** ({c.get('sector', '—')}) — "
            f"Score: {fmt_score(c.get('composite_score'))} | "
            f"ARR: {fmt_money(c.get('arr_millions'))} | "
            f"Growth: {fmt_pct(c.get('revenue_growth_pct'))}\n"
        )

    digest += """
---

_Generated by Growth Equity Radar_
"""
    return digest
