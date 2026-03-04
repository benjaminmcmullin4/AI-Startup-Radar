"""RSS news ingestion focused on Series B+ funding rounds."""

import feedparser
from datetime import datetime
from db.database import insert_news, get_all_companies


FUNDING_RSS_FEEDS = [
    "https://techcrunch.com/category/fundraising/feed/",
    "https://news.crunchbase.com/feed/",
]

GROWTH_KEYWORDS = [
    "series b", "series c", "series d", "growth round", "growth equity",
    "raises", "funding", "million", "valuation",
]


def fetch_funding_news(feeds: list[str] = None) -> list[dict]:
    """Fetch and parse RSS feeds for funding-related news."""
    feeds = feeds or FUNDING_RSS_FEEDS
    items = []
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

    matched = []
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
