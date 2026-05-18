"""
Wikipedia entity verification — extracts named entities from article
and validates them against Wikipedia to detect unverifiable claims.
"""

import os
import re
import requests

WIKI_API = "https://en.wikipedia.org/w/api.php"


def _wiki_search(term: str) -> dict | None:
    """Search Wikipedia for a term. Returns summary snippet or None."""
    try:
        params = {
            "action": "query", "format": "json",
            "list": "search", "srsearch": term,
            "srlimit": 1, "srprop": "snippet",
        }
        r = requests.get(WIKI_API, params=params, timeout=8,
                         headers={"User-Agent": "TruthLens/1.0"})
        if r.status_code == 200:
            results = r.json().get("query", {}).get("search", [])
            if results:
                return {"title": results[0]["title"], "snippet": results[0]["snippet"]}
    except Exception:
        pass
    return None


def _extract_entities_regex(text: str) -> list[str]:
    """Fast regex-based NER: grab capitalized multi-word phrases."""
    pattern = r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\b'
    candidates = re.findall(pattern, text)
    # Deduplicate, skip generic/short ones
    stop_phrases = {"The United", "New York", "United States", "United Kingdom",
                    "According To", "Breaking News", "Click Here", "Read More"}
    seen, out = set(), []
    for c in candidates:
        if c not in stop_phrases and c not in seen and len(c) > 5:
            seen.add(c)
            out.append(c)
        if len(out) >= 8:
            break
    return out


def verify_entities(article_text: str, gemini_entities: list[str] | None = None) -> dict:
    """
    Extract named entities and verify them against Wikipedia.

    Returns:
        {
            score: float (0-100),
            verified: list[dict],
            unverified: list[str],
            signals: list[dict],
            error: str | None,
        }
    """
    result = {
        "score": 50,
        "verified": [],
        "unverified": [],
        "signals": [],
        "error": None,
    }

    # Use Gemini-provided entities if available, else regex
    entities = gemini_entities if gemini_entities else _extract_entities_regex(article_text)

    if not entities:
        result["score"] = 50
        result["signals"].append({
            "icon": "❓", "label": "No Entities Extracted",
            "detail": "No named entities found to verify against Wikipedia.",
            "positive": None,
        })
        return result

    verified, unverified = [], []
    for entity in entities[:6]:  # cap to avoid rate limits
        wiki = _wiki_search(entity)
        if wiki:
            verified.append({"entity": entity, "wiki_title": wiki["title"],
                              "snippet": re.sub(r'<[^>]+>', '', wiki["snippet"])[:120]})
        else:
            unverified.append(entity)

    result["verified"] = verified
    result["unverified"] = unverified

    total = len(verified) + len(unverified)
    if total == 0:
        return result

    verify_ratio = len(verified) / total

    if verify_ratio >= 0.7:
        result["score"] = round(60 + verify_ratio * 30)
        result["signals"].append({
            "icon": "✅",
            "label": f"{len(verified)}/{total} Entities Verified on Wikipedia",
            "detail": "Most named people, places, and organizations are verifiable.",
            "positive": True,
        })
    elif verify_ratio >= 0.4:
        result["score"] = 45
        result["signals"].append({
            "icon": "⚠️",
            "label": f"{len(verified)}/{total} Entities Verified",
            "detail": "Some entities could not be found on Wikipedia.",
            "positive": None,
        })
    else:
        result["score"] = max(15, round(30 * verify_ratio))
        result["signals"].append({
            "icon": "🚨",
            "label": f"Only {len(verified)}/{total} Entities Verifiable",
            "detail": f"Unverified: {', '.join(unverified[:3])}. Anonymous sources are a red flag.",
            "positive": False,
        })

    return result
