"""
Utility functions: URL text extraction, text preprocessing, language detection.
"""

import re
import os
import urllib.parse
from typing import Optional

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# URL / Article extraction
# ---------------------------------------------------------------------------

def is_valid_url(text: str) -> bool:
    """Return True if *text* looks like a URL."""
    try:
        result = urllib.parse.urlparse(text.strip())
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False


def extract_domain(url: str) -> str:
    """Extract bare domain from a URL (e.g. 'https://www.bbc.com/...' → 'bbc.com')."""
    try:
        import tldextract
        ext = tldextract.extract(url)
        if ext.domain and ext.suffix:
            return f"{ext.domain}.{ext.suffix}".lower()
    except Exception:
        pass
    # Fallback
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        return netloc.replace("www.", "")
    except Exception:
        return ""


def fetch_article_text(url: str) -> dict:
    """
    Fetch and extract the main article text from a URL.
    Returns a dict with keys: title, text, domain, success, error.
    """
    result = {
        "title": "",
        "text": "",
        "domain": extract_domain(url),
        "success": False,
        "error": None,
    }

    # --- Try trafilatura first (best quality) ---
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                output_format="txt",
            )
            if extracted and len(extracted) > 100:
                result["text"] = extracted
                # Get title via metadata
                meta = trafilatura.extract_metadata(downloaded)
                if meta and meta.title:
                    result["title"] = meta.title
                result["success"] = True
                return result
    except Exception:
        pass

    # --- Fallback: requests + BeautifulSoup ---
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Title
        title_tag = soup.find("title")
        if title_tag:
            result["title"] = title_tag.get_text(strip=True)

        # Remove noise tags
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "noscript", "iframe"]):
            tag.decompose()

        # Article body heuristics
        candidates = soup.find_all(["article", "main"])
        if candidates:
            text = " ".join(c.get_text(" ", strip=True) for c in candidates)
        else:
            body = soup.find("body")
            text = body.get_text(" ", strip=True) if body else ""

        text = re.sub(r"\s{2,}", " ", text).strip()
        if len(text) > 100:
            result["text"] = text[:8000]  # cap to avoid token overflow
            result["success"] = True
        else:
            result["error"] = "Could not extract meaningful article text."
    except requests.exceptions.RequestException as e:
        result["error"] = f"Network error: {e}"
    except Exception as e:
        result["error"] = f"Extraction error: {e}"

    return result


# ---------------------------------------------------------------------------
# Text pre-processing helpers
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Basic text cleaning — collapse whitespace, remove URLs."""
    text = re.sub(r"http\S+", "", text)  # remove URLs
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate_text(text: str, max_chars: int = 6000) -> str:
    """Truncate to max_chars, preserving whole words where possible."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:
        truncated = truncated[:last_space]
    return truncated + "…"


def extract_headline_keywords(text: str, max_words: int = 10) -> str:
    """Extract the most relevant words for a NewsAPI query."""
    # Remove common stopwords
    stop = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "must",
        "this", "that", "these", "those", "it", "its", "he", "she", "they",
        "we", "you", "i", "my", "your", "his", "her", "their", "our",
        "said", "says", "according", "also", "new", "one", "two", "three",
    }
    words = re.findall(r"[a-zA-Z]{4,}", text)
    seen = set()
    keywords = []
    for w in words:
        lw = w.lower()
        if lw not in stop and lw not in seen:
            seen.add(lw)
            keywords.append(w)
        if len(keywords) >= max_words:
            break
    return " ".join(keywords[:6])  # Use top 6 for query


def count_caps_ratio(text: str) -> float:
    """Return ratio of ALL-CAPS words to total words (0–1)."""
    words = text.split()
    if not words:
        return 0.0
    caps_words = [w for w in words if w.isupper() and len(w) > 1]
    return len(caps_words) / len(words)


def count_exclamation_ratio(text: str) -> float:
    """Exclamation mark density per sentence-like unit."""
    sentences = max(1, text.count(".") + text.count("!") + text.count("?"))
    exclamations = text.count("!")
    return min(1.0, exclamations / sentences)


def detect_clickbait_phrases(text: str) -> list[str]:
    """Return list of detected clickbait phrases in text."""
    patterns = [
        r"\byou won'?t believe\b", r"\bshocking\b", r"\bbombshell\b",
        r"\bbreaking[:\s]", r"\bexclusive[:\s]", r"\bwhat they don'?t want you to know\b",
        r"\bsecret\b", r"\bthey'?re hiding\b", r"\bhidden truth\b",
        r"\bthe truth about\b", r"\bwake up\b", r"\bsheep\b",
        r"\bsheeple\b", r"\bdeep state\b", r"\bplandemic\b",
        r"\bthey lied\b", r"\bmass media lies\b", r"\bmainstream media\b",
        r"\bfake news\b", r"\bhoax\b", r"\bcrisis actor\b",
        r"\bfalse flag\b", r"\bnwo\b", r"\bnew world order\b",
        r"\billuminati\b", r"\bsoros\b", r"\bgeorge soros\b",
        r"\bvaccine truth\b", r"\bclimate hoax\b",
    ]
    found = []
    text_lower = text.lower()
    for pat in patterns:
        if re.search(pat, text_lower):
            # Clean up the pattern for display
            clean = re.sub(r"\\b|\\s\+|\[:\s\]|\[:\\\s\]", " ", pat).strip().replace("\\", "")
            found.append(clean.strip())
    return found[:8]  # cap at 8
