"""
Source credibility checker — scores a domain based on:
  - Known fake / satire / biased site lists
  - HTTPS presence
  - Domain age via WHOIS
  - Domain extension heuristics
"""

import os
import json
import datetime
from typing import Optional
from src.utils import extract_domain


# ---------------------------------------------------------------------------
# Load known sources database
# ---------------------------------------------------------------------------
_SOURCES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "known_sources.json")

def _load_sources() -> dict:
    try:
        with open(_SOURCES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"fake_news": [], "satire": [], "highly_biased": [], "credible": [], "fact_checkers": []}

KNOWN_SOURCES = _load_sources()


# ---------------------------------------------------------------------------
# WHOIS domain age lookup (best-effort, may fail for many domains)
# ---------------------------------------------------------------------------

def _get_domain_age_days(domain: str) -> Optional[int]:
    """Return domain age in days, or None if lookup fails."""
    try:
        import whois
        w = whois.whois(domain)
        creation = w.creation_date
        if isinstance(creation, list):
            creation = creation[0]
        if creation and isinstance(creation, datetime.datetime):
            age = (datetime.datetime.utcnow() - creation).days
            return max(0, age)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def check_source_credibility(url: str) -> dict:
    """
    Analyse the credibility of the source URL.

    Returns:
        {
            score: float  (0–100, higher = more credible),
            label: str,
            signals: list[dict],  # [{icon, label, detail, positive}]
            domain: str,
            category: str,        # 'fake_news'|'satire'|'highly_biased'|'credible'|'unknown'
        }
    """
    domain = extract_domain(url) if url else ""
    signals = []
    score = 50  # start neutral

    # ---- Category lookup ----
    category = "unknown"
    if domain:
        if domain in KNOWN_SOURCES.get("credible", []) or domain in KNOWN_SOURCES.get("fact_checkers", []):
            category = "credible"
            score += 30
            signals.append({
                "icon": "✅",
                "label": "Credible Source",
                "detail": f"{domain} is a recognized credible news outlet or fact-checker.",
                "positive": True,
            })
        elif domain in KNOWN_SOURCES.get("fake_news", []):
            category = "fake_news"
            score -= 45
            signals.append({
                "icon": "🚫",
                "label": "Known Misinformation Site",
                "detail": f"{domain} is flagged in our database as a known misinformation/fake news site.",
                "positive": False,
            })
        elif domain in KNOWN_SOURCES.get("satire", []):
            category = "satire"
            score -= 25
            signals.append({
                "icon": "🎭",
                "label": "Satire / Parody Site",
                "detail": f"{domain} is a known satire or parody site. Content is not meant to be taken as fact.",
                "positive": False,
            })
        elif domain in KNOWN_SOURCES.get("highly_biased", []):
            category = "highly_biased"
            score -= 15
            signals.append({
                "icon": "⚠️",
                "label": "Highly Biased Source",
                "detail": f"{domain} is rated as highly politically biased by media watchdogs.",
                "positive": False,
            })
    else:
        signals.append({
            "icon": "❓",
            "label": "No URL Provided",
            "detail": "Source could not be evaluated (text input only). Analysis relies on content alone.",
            "positive": None,
        })

    # ---- HTTPS check ----
    if url:
        if url.startswith("https://"):
            signals.append({
                "icon": "🔒",
                "label": "Secure HTTPS",
                "detail": "Site uses encrypted HTTPS connection.",
                "positive": True,
            })
            score += 5
        else:
            signals.append({
                "icon": "🔓",
                "label": "No HTTPS",
                "detail": "Site does not use HTTPS encryption — a red flag for legitimate news sites.",
                "positive": False,
            })
            score -= 8

    # ---- Domain extension heuristics ----
    if domain:
        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        suspicious_tlds = {"xyz", "tk", "ml", "ga", "cf", "gq", "top", "click", "link", "info", "biz"}
        credible_tlds = {"com", "org", "net", "edu", "gov", "co", "uk", "de", "fr", "au", "ca"}

        if tld in suspicious_tlds:
            signals.append({
                "icon": "🔴",
                "label": f"Suspicious TLD (.{tld})",
                "detail": f".{tld} domains are frequently used by low-quality or spam sites.",
                "positive": False,
            })
            score -= 10
        elif tld in ("edu", "gov"):
            signals.append({
                "icon": "🏛️",
                "label": f"Authoritative TLD (.{tld})",
                "detail": f".{tld} domains are restricted to educational institutions or governments.",
                "positive": True,
            })
            score += 15

        # Impersonation check (domain that looks like a known outlet but isn't)
        known_brands = ["nytimes", "bbc", "cnn", "reuters", "apnews", "washingtonpost", "usatoday"]
        for brand in known_brands:
            if brand in domain and domain not in KNOWN_SOURCES.get("credible", []):
                signals.append({
                    "icon": "⛔",
                    "label": "Possible Impersonation",
                    "detail": f"{domain} resembles a well-known outlet ({brand}) but is NOT the real site.",
                    "positive": False,
                })
                score -= 35
                break

    # ---- Domain age (best-effort WHOIS) ----
    if domain and category not in ("credible",):
        age_days = _get_domain_age_days(domain)
        if age_days is not None:
            if age_days < 90:
                signals.append({
                    "icon": "🆕",
                    "label": f"Very New Domain ({age_days} days old)",
                    "detail": "Newly registered domains are a common red flag for misinformation sites.",
                    "positive": False,
                })
                score -= 20
            elif age_days < 365:
                signals.append({
                    "icon": "📅",
                    "label": f"Young Domain ({age_days} days old)",
                    "detail": "Domain is less than 1 year old — somewhat suspicious.",
                    "positive": False,
                })
                score -= 8
            else:
                years = age_days // 365
                signals.append({
                    "icon": "📆",
                    "label": f"Established Domain ({years}+ years old)",
                    "detail": "Older domains tend to be more established and trustworthy.",
                    "positive": True,
                })
                score += 10

    # ---- Clamp score ----
    score = max(0, min(100, score))

    # ---- Label ----
    if score >= 75:
        label = "Highly Credible"
    elif score >= 55:
        label = "Moderately Credible"
    elif score >= 35:
        label = "Questionable"
    elif score >= 15:
        label = "Low Credibility"
    else:
        label = "Very Low Credibility"

    return {
        "score": score,
        "label": label,
        "signals": signals,
        "domain": domain,
        "category": category,
    }
