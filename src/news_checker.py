"""
News cross-reference — NewsAPI.org primary + GNews fallback.
Validates article claims against real headlines from 60,000+ trusted sources.
"""

import os
import re
import requests
from src.utils import extract_headline_keywords, clean_text

NEWS_API_BASE  = "https://newsapi.org/v2/everything"
GNEWS_API_BASE = "https://gnews.io/api/v4/search"
NEWS_API_KEY   = os.getenv("NEWS_API_KEY", "")
GNEWS_API_KEY  = os.getenv("GNEWS_API_KEY", "")

TRUSTED_SOURCES = [
    "reuters.com", "apnews.com", "bbc.com", "nytimes.com",
    "theguardian.com", "bloomberg.com", "npr.org", "pbs.org",
    "washingtonpost.com", "cbsnews.com", "nbcnews.com",
    "abcnews.go.com", "usatoday.com", "theatlantic.com",
    "france24.com", "dw.com", "aljazeera.com",
]


def _search_newsapi(query: str, page_size: int = 8) -> list[dict]:
    """NewsAPI.org search — returns list of article dicts."""
    if not NEWS_API_KEY or NEWS_API_KEY == "your_newsapi_key_here":
        return []
    params = {
        "q": query, "language": "en",
        "sortBy": "relevancy", "pageSize": page_size,
        "apiKey": NEWS_API_KEY,
    }
    try:
        resp = requests.get(NEWS_API_BASE, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("articles", [])
        if resp.status_code == 401:
            return [{"_error": "Invalid NewsAPI key."}]
        if resp.status_code == 429:
            return [{"_quota_exceeded": True}]
    except requests.exceptions.RequestException:
        pass
    return []


def _search_gnews(query: str, page_size: int = 8) -> list[dict]:
    """GNews fallback — 60,000+ sources, 100 req/day free."""
    if not GNEWS_API_KEY or GNEWS_API_KEY == "your_key_here":
        return []
    params = {
        "q": query, "lang": "en",
        "max": page_size, "apikey": GNEWS_API_KEY,
    }
    try:
        resp = requests.get(GNEWS_API_BASE, params=params, timeout=10)
        if resp.status_code == 200:
            articles = resp.json().get("articles", [])
            # Normalize GNews format to match NewsAPI format
            return [{
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "url": a.get("url", ""),
                "publishedAt": a.get("publishedAt", ""),
                "source": {"name": a.get("source", {}).get("name", "Unknown")},
            } for a in articles]
    except requests.exceptions.RequestException:
        pass
    return []



def cross_reference_news(article_text: str, article_title: str = "") -> dict:
    """
    Cross-reference the article against NewsAPI headlines.

    Returns:
        {
            score: float (0-100, higher = better corroboration),
            label: str,
            articles: list[dict],  # matching articles found
            query_used: str,
            signals: list[dict],
            api_available: bool,
            error: str | None,
        }
    """
    result = {
        "score": 50,
        "label": "No Cross-Reference",
        "articles": [],
        "query_used": "",
        "signals": [],
        "api_used": "none",
        "api_available": bool(
            (NEWS_API_KEY and NEWS_API_KEY != "your_newsapi_key_here") or
            (GNEWS_API_KEY and GNEWS_API_KEY != "your_key_here")
        ),
        "error": None,
    }

    if not result["api_available"]:
        result["error"] = "No news API configured. Add NEWS_API_KEY or GNEWS_API_KEY to .env."
        result["label"] = "API Key Missing"
        result["signals"].append({
            "icon": "🔑", "label": "No News API Configured",
            "detail": "Add NEWS_API_KEY (newsapi.org) or GNEWS_API_KEY (gnews.io) — both free.",
            "positive": None,
        })
        return result

    # Build search query from title + article body keywords
    source_text = article_title if article_title else article_text
    query = extract_headline_keywords(source_text, max_words=8)
    result["query_used"] = query

    if not query or len(query) < 5:
        result["error"] = "Could not extract meaningful search terms from article."
        result["signals"].append({
            "icon": "❓",
            "label": "No Keywords Extracted",
            "detail": "Article text was too short or generic to search.",
            "positive": None,
        })
        return result

    # Try NewsAPI first, GNews as fallback
    raw_articles = _search_newsapi(query)
    api_used = "NewsAPI"

    if raw_articles and "_error" in raw_articles[0]:
        result["signals"].append({
            "icon": "⚠️", "label": "NewsAPI Error",
            "detail": raw_articles[0]["_error"],
            "positive": None,
        })
        raw_articles = []

    # NewsAPI quota hit → try GNews
    if not raw_articles and (
        not NEWS_API_KEY or NEWS_API_KEY == "your_newsapi_key_here"
        or (raw_articles and raw_articles[0].get("_quota_exceeded"))
    ):
        raw_articles = _search_gnews(query)
        api_used = "GNews"
        if raw_articles:
            result["signals"].append({
                "icon": "🔄", "label": "Using GNews Fallback",
                "detail": "NewsAPI quota reached — switched to GNews (60,000+ sources).",
                "positive": None,
            })

    result["api_used"] = api_used

    if not raw_articles:
        result["score"] = 30
        result["label"] = "No Corroboration Found"
        result["signals"].append({
            "icon": "❌", "label": "No Matching Stories Found",
            "detail": f"No stories matching '{query}' found. Red flag if article claims major events.",
            "positive": False,
        })
        return result

    # Process found articles
    processed = []
    trusted_count = 0
    for art in raw_articles:
        source = art.get("source", {})
        source_name = source.get("name", "Unknown")
        source_url = art.get("url", "")
        
        # Check if from trusted source
        is_trusted = any(
            t in source_url.lower() 
            for t in TRUSTED_SOURCES
        )
        if is_trusted:
            trusted_count += 1

        processed.append({
            "title": art.get("title", "No title"),
            "source": source_name,
            "url": source_url,
            "description": art.get("description", ""),
            "published_at": art.get("publishedAt", ""),
            "is_trusted": is_trusted,
        })

    result["articles"] = processed[:6]
    total = len(processed)

    # ---- Scoring ----
    # Start skeptical — only rise with trusted corroboration
    if trusted_count == 0:
        # Stories found but NONE from trusted outlets — suspicious
        base_score = 35
    else:
        # At least one trusted outlet — start neutral
        base_score = 50

    # Trusted outlets boost (max +35)
    trusted_ratio = trusted_count / total if total > 0 else 0
    trust_boost = trusted_ratio * 35
    base_score += trust_boost

    # Volume of trusted corroboration boost
    if trusted_count >= 4:
        base_score += 10
    elif trusted_count >= 2:
        base_score += 5

    result["score"] = min(100, round(base_score))

    # ---- Signals ----
    result["signals"].append({
        "icon": "📰",
        "label": f"{total} Matching Stories Found",
        "detail": f"Searched for: \"{query}\"",
        "positive": total > 0,
    })

    if trusted_count > 0:
        result["signals"].append({
            "icon": "✅",
            "label": f"{trusted_count} Trusted Outlet(s) Reporting",
            "detail": f"{trusted_count}/{total} results are from recognized credible outlets (Reuters, BBC, AP, etc.)",
            "positive": True,
        })
    else:
        result["signals"].append({
            "icon": "⚠️",
            "label": "No Trusted Outlets Found",
            "detail": "None of the matching stories are from major credible news outlets.",
            "positive": False,
        })

    # Label
    score = result["score"]
    if score >= 75:
        result["label"] = "Well Corroborated"
    elif score >= 60:
        result["label"] = "Partially Corroborated"
    elif score >= 45:
        result["label"] = "Weakly Corroborated"
    else:
        result["label"] = "Not Corroborated"

    return result
