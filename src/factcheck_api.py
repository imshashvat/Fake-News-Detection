"""
Google Fact Check Tools API integration.
Searches 100+ fact-checking databases (Snopes, PolitiFact, AFP, Reuters Fact Check, etc.)
for claims matching the article content.
API Docs: https://developers.google.com/fact-check/tools/api/reference/rest
"""

import os
import re
import requests
from src.utils import extract_headline_keywords

FACTCHECK_API_KEY = os.getenv("GOOGLE_FACTCHECK_API_KEY", "")
FACTCHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


def search_fact_checks(article_text: str, title: str = "") -> dict:
    """
    Query Google Fact Check Tools API for claims matching the article.
    """
    api_key = os.getenv("GOOGLE_FACTCHECK_API_KEY", "")
    result = {
        "score": 50,
        "label": "No Fact-Checks Found",
        "claims": [],
        "api_available": bool(api_key and api_key not in ("", "your_key_here")),
        "signals": [],
        "error": None,
    }

    if not result["api_available"]:
        result["error"] = "Google Fact Check API key not configured."
        result["signals"].append({
            "icon": "🔑",
            "label": "Fact Check API Not Configured",
            "detail": "Add GOOGLE_FACTCHECK_API_KEY to .env to enable direct fact-check database search.",
            "positive": None,
        })
        return result

    # Build query from title or first 200 chars
    source = title if title else article_text[:200]
    query = extract_headline_keywords(source, max_words=6)

    if not query:
        result["error"] = "Could not extract search terms."
        return result

    try:
        params = {
            "key": api_key,
            "query": query,
            "languageCode": "en",
            "pageSize": 8,
        }
        resp = requests.get(FACTCHECK_URL, params=params, timeout=10)

        if resp.status_code == 403:
            result["error"] = "Fact Check API key invalid or API not enabled in Google Cloud Console."
            return result
        if resp.status_code == 429:
            result["error"] = "Fact Check API quota exceeded."
            return result
        if resp.status_code != 200:
            result["error"] = f"Fact Check API error: HTTP {resp.status_code}"
            return result

        data = resp.json()
        raw_claims = data.get("claims", [])

        if not raw_claims:
            result["score"] = 35
            result["label"] = "No Matching Fact-Checks"
            result["signals"].append({
                "icon": "❓",
                "label": "No Fact-Check Records Found",
                "detail": f"No fact-checkers have reviewed claims matching '{query}'. "
                          "This may mean the story is too new, too niche, or hasn't been picked up yet.",
                "positive": None,
            })
            return result

        # Process claims
        processed = []
        false_count = 0
        true_count = 0
        misleading_count = 0

        RATING_MAP = {
            # FALSE variants
            "false": "FALSE", "fake": "FALSE", "pants on fire": "FALSE",
            "incorrect": "FALSE", "fabricated": "FALSE", "debunked": "FALSE",
            "not true": "FALSE", "inaccurate": "FALSE", "wrong": "FALSE",
            "hoax": "FALSE", "lie": "FALSE",
            # TRUE variants
            "true": "TRUE", "correct": "TRUE", "accurate": "TRUE",
            "verified": "TRUE", "confirmed": "TRUE",
            # MISLEADING variants
            "misleading": "MISLEADING", "mostly false": "MISLEADING",
            "mostly true": "MISLEADING", "half true": "MISLEADING",
            "mixture": "MISLEADING", "partly false": "MISLEADING",
            "exaggerated": "MISLEADING", "unproven": "MISLEADING",
        }

        for c in raw_claims:
            text = c.get("text", "No claim text")
            reviews = c.get("claimReview", [])
            claimant = c.get("claimant", "Unknown")

            for review in reviews[:1]:  # take first review per claim
                publisher = review.get("publisher", {}).get("name", "Unknown")
                rating_raw = review.get("textualRating", "Unknown").lower()
                url = review.get("url", "#")
                review_date = review.get("reviewDate", "")[:10]

                # Normalize rating
                rating = "UNKNOWN"
                for key, val in RATING_MAP.items():
                    if key in rating_raw:
                        rating = val
                        break

                if rating == "FALSE":
                    false_count += 1
                elif rating == "TRUE":
                    true_count += 1
                elif rating == "MISLEADING":
                    misleading_count += 1

                processed.append({
                    "claim": text[:200],
                    "claimant": claimant,
                    "publisher": publisher,
                    "rating": rating,
                    "rating_raw": review.get("textualRating", ""),
                    "url": url,
                    "date": review_date,
                })

        result["claims"] = processed[:6]
        total = len(processed)

        # Score calculation
        if false_count > 0 and true_count == 0:
            score = max(10, 30 - (false_count * 8))
            label = "Fact-Checked: FALSE"
        elif true_count > 0 and false_count == 0:
            score = min(90, 65 + (true_count * 8))
            label = "Fact-Checked: TRUE"
        elif misleading_count > 0:
            score = 35
            label = "Fact-Checked: MISLEADING"
        else:
            score = 50
            label = "Mixed Fact-Check Results"

        result["score"] = score
        result["label"] = label

        # Signals
        if false_count > 0:
            result["signals"].append({
                "icon": "🚫",
                "label": f"{false_count} Claim(s) Rated FALSE",
                "detail": f"Fact-checkers have rated {false_count} claim(s) in this story as FALSE.",
                "positive": False,
            })
        if true_count > 0:
            result["signals"].append({
                "icon": "✅",
                "label": f"{true_count} Claim(s) Verified TRUE",
                "detail": f"{true_count} claim(s) have been independently verified as accurate.",
                "positive": True,
            })
        if misleading_count > 0:
            result["signals"].append({
                "icon": "⚠️",
                "label": f"{misleading_count} Claim(s) Rated MISLEADING",
                "detail": "Some claims are partially true but presented in a misleading way.",
                "positive": False,
            })

        publishers = list({p["publisher"] for p in processed})
        result["signals"].append({
            "icon": "🔍",
            "label": f"{total} Fact-Check Record(s) Found",
            "detail": f"From: {', '.join(publishers[:3])}",
            "positive": total > 0,
        })

    except requests.exceptions.RequestException as e:
        result["error"] = f"Network error: {e}"

    return result
