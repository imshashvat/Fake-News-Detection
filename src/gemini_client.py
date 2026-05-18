"""
Google Gemini 1.5 Flash integration for deep fake-news analysis.
Uses structured JSON output from the LLM for reliable parsing.
"""

import os, json, re, warnings
from typing import Optional
warnings.filterwarnings("ignore", category=FutureWarning)
import google.generativeai as genai
from src.utils import truncate_text, count_caps_ratio, count_exclamation_ratio, detect_clickbait_phrases


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Gemini model — Flash is free-tier (1500 req/day)
MODEL_NAME = "gemini-2.0-flash"  # free, fast, current


def _get_model():
    """Configure and return the Gemini model."""
    # Re-read key at call time so hot-reloaded .env keys work
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key in ("your_gemini_api_key_here", ""):
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        MODEL_NAME,
        generation_config=genai.GenerationConfig(
            temperature=0.1,
            max_output_tokens=1500,
        )
    )


ANALYSIS_PROMPT = """You are an expert fact-checker and media literacy analyst. Analyze the following content for credibility. This may be a full news article, a short headline, a social media claim, or a simple question/statement.

CONTENT TO ANALYZE:
---
{article_text}
---
{title_line}

IMPORTANT: Even for very short text (headlines, claims, questions), you MUST still produce a full JSON response with your best assessment. For questions like "Is X a criminal?", assess whether there is credible public evidence for this claim.

Respond ONLY with a valid JSON object (no markdown, no code fences, just raw JSON):

{{
  "credibility_score": <integer 0-100, where 0=definitely false/fake, 100=definitely true/credible>,
  "verdict": "<one of: REAL | LIKELY_REAL | UNCERTAIN | LIKELY_FAKE | FAKE>",
  "confidence": "<one of: HIGH | MEDIUM | LOW>",
  "summary": "<2-3 sentence assessment of this claim/article>",
  "writing_quality": {{
    "score": <integer 0-100>,
    "issues": ["<list of specific writing quality issues if any>"]
  }},
  "emotional_language": {{
    "detected": <true|false>,
    "examples": ["<list of emotionally charged phrases found>"],
    "severity": "<LOW|MEDIUM|HIGH>"
  }},
  "logical_consistency": {{
    "score": <integer 0-100>,
    "issues": ["<list of logical inconsistencies or unsupported claims>"]
  }},
  "claim_specificity": {{
    "score": <integer 0-100>,
    "note": "<comment on whether claims are specific and verifiable or vague>"
  }},
  "red_flags": ["<list of specific red flags you detected>"],
  "positive_indicators": ["<list of credibility indicators>"],
  "recommended_action": "<what the reader should do>"
}}

Be decisive. Assign a clear score — avoid defaulting to 50 (uncertain) unless there is genuine ambiguity. Base analysis only on the text provided and your knowledge."""


def analyze_with_gemini(article_text: str, title: str = "") -> dict:
    """
    Send article to Gemini 1.5 Flash for deep analysis.

    Returns:
        {
            score: float (0-100),
            verdict: str,
            confidence: str,
            summary: str,
            writing_quality: dict,
            emotional_language: dict,
            logical_consistency: dict,
            claim_specificity: dict,
            red_flags: list,
            positive_indicators: list,
            recommended_action: str,
            signals: list[dict],
            api_available: bool,
            error: str | None,
            raw_text_signals: dict,  # pre-LLM heuristics
        }
    """
    # ---- Pre-LLM heuristic signals (always run) ----
    raw_signals = _compute_text_heuristics(article_text)

    api_key = os.getenv("GEMINI_API_KEY", "")
    result = {
        "score": 50,
        "verdict": "UNCERTAIN",
        "confidence": "LOW",
        "summary": "Analysis incomplete.",
        "writing_quality": {"score": 50, "issues": []},
        "emotional_language": {"detected": False, "examples": [], "severity": "LOW"},
        "logical_consistency": {"score": 50, "issues": []},
        "claim_specificity": {"score": 50, "note": ""},
        "red_flags": [],
        "positive_indicators": [],
        "recommended_action": "Seek additional sources before sharing.",
        "signals": [],
        "api_available": bool(api_key and api_key not in ("", "your_gemini_api_key_here")),
        "error": None,
        "raw_text_signals": raw_signals,
    }

    if not result["api_available"]:
        result["error"] = "Gemini API key not configured. Add GEMINI_API_KEY to .env."
        result["signals"].append({
            "icon": "🔑",
            "label": "Gemini API Not Configured",
            "detail": "Add your free Gemini API key from aistudio.google.com to enable LLM analysis.",
            "positive": None,
        })
        # Fall back to heuristics only
        result.update(_heuristics_only_analysis(raw_signals, article_text))
        return result

    model = _get_model()
    if model is None:
        result["error"] = "Could not initialize Gemini model."
        return result

    # Prepare prompt
    title_line = f"\nARTICLE TITLE: {title}" if title else ""
    safe_text = truncate_text(article_text, 5000)
    prompt = ANALYSIS_PROMPT.format(article_text=safe_text, title_line=title_line)

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Strip markdown fences if Gemini wrapped it anyway
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        parsed = json.loads(raw)

        # Merge parsed result
        result["score"] = int(parsed.get("credibility_score", 50))
        result["verdict"] = parsed.get("verdict", "UNCERTAIN")
        result["confidence"] = parsed.get("confidence", "MEDIUM")
        result["summary"] = parsed.get("summary", "")
        result["writing_quality"] = parsed.get("writing_quality", result["writing_quality"])
        result["emotional_language"] = parsed.get("emotional_language", result["emotional_language"])
        result["logical_consistency"] = parsed.get("logical_consistency", result["logical_consistency"])
        result["claim_specificity"] = parsed.get("claim_specificity", result["claim_specificity"])
        result["red_flags"] = parsed.get("red_flags", [])
        result["positive_indicators"] = parsed.get("positive_indicators", [])
        result["recommended_action"] = parsed.get("recommended_action", "")

        # Build signals list
        result["signals"] = _build_signals_from_parsed(parsed, raw_signals)

    except json.JSONDecodeError as e:
        result["error"] = f"Gemini returned non-JSON response. Raw: {raw[:200]}..."
        # Fall back to heuristics
        result.update(_heuristics_only_analysis(raw_signals, article_text))
    except Exception as e:
        err_str = str(e)
        if "API_KEY_INVALID" in err_str or "401" in err_str:
            result["error"] = "Invalid Gemini API key. Please check your GEMINI_API_KEY in .env"
        elif "quota" in err_str.lower() or "429" in err_str:
            result["error"] = "Gemini API quota exceeded. Free tier allows 1,500 requests/day."
        else:
            result["error"] = f"Gemini API error: {err_str[:200]}"
        result.update(_heuristics_only_analysis(raw_signals, article_text))

    return result


# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------

def _compute_text_heuristics(text: str) -> dict:
    """Fast, offline text analysis — no API needed."""
    caps_ratio = count_caps_ratio(text)
    excl_ratio = count_exclamation_ratio(text)
    clickbait = detect_clickbait_phrases(text)
    word_count = len(text.split())
    sentence_count = max(1, text.count(".") + text.count("!") + text.count("?"))
    avg_sentence_len = word_count / sentence_count

    return {
        "caps_ratio": caps_ratio,
        "excl_ratio": excl_ratio,
        "clickbait_phrases": clickbait,
        "word_count": word_count,
        "avg_sentence_len": avg_sentence_len,
        "has_numbers": bool(re.search(r"\d", text)),
        "has_quotes": bool(re.search(r'["""]', text)),
    }


def _heuristics_only_analysis(raw_signals: dict, text: str) -> dict:
    """Generate analysis purely from text heuristics (no LLM)."""
    score = 50
    red_flags = []
    positive_indicators = []
    signals = []

    caps = raw_signals["caps_ratio"]
    excl = raw_signals["excl_ratio"]
    clickbait = raw_signals["clickbait_phrases"]

    if caps > 0.15:
        score -= 15
        red_flags.append(f"High ratio of ALL-CAPS words ({caps:.0%})")
        signals.append({"icon": "🔠", "label": f"Excessive CAPS ({caps:.0%})", "detail": "High ALL-CAPS ratio is a common tactic in sensationalized/fake news.", "positive": False})

    if excl > 0.3:
        score -= 10
        red_flags.append("Excessive use of exclamation marks")
        signals.append({"icon": "❗", "label": "Excessive Exclamation Marks", "detail": "Very high exclamation mark density — common in sensationalized content.", "positive": False})

    if clickbait:
        score -= 12
        red_flags.append(f"Clickbait phrases detected: {', '.join(clickbait[:3])}")
        signals.append({"icon": "🪤", "label": f"{len(clickbait)} Clickbait Phrase(s)", "detail": f"Detected: {', '.join(clickbait[:4])}", "positive": False})

    if raw_signals["has_numbers"]:
        score += 5
        positive_indicators.append("Contains specific numbers/statistics (more verifiable)")

    if raw_signals["has_quotes"]:
        score += 5
        positive_indicators.append("Contains quotes from named sources")

    if raw_signals["word_count"] > 400:
        positive_indicators.append("Substantial article length suggests in-depth reporting")
        score += 5
    elif raw_signals["word_count"] < 80:
        red_flags.append("Very short text — insufficient content to evaluate fully")
        score -= 10

    score = max(0, min(100, score))

    if score >= 65:
        verdict = "LIKELY_REAL"
    elif score <= 30:
        verdict = "LIKELY_FAKE"
    else:
        verdict = "UNCERTAIN"

    return {
        "score": score,
        "verdict": verdict,
        "confidence": "LOW",
        "summary": "API not available — analysis based on text heuristics only (CAPS ratio, clickbait phrases, etc.). For full analysis, configure your Gemini API key.",
        "red_flags": red_flags,
        "positive_indicators": positive_indicators,
        "signals": signals,
        "recommended_action": "Configure Gemini API for deeper analysis. Verify with trusted news sources.",
    }


def _build_signals_from_parsed(parsed: dict, raw: dict) -> list:
    """Convert Gemini's parsed JSON into UI signal cards."""
    signals = []

    # Writing quality
    wq = parsed.get("writing_quality", {})
    wq_score = wq.get("score", 50)
    positive = wq_score >= 65
    signals.append({
        "icon": "✍️" if positive else "📝",
        "label": f"Writing Quality: {wq_score}/100",
        "detail": "; ".join(wq.get("issues", [])) or "No major writing issues detected.",
        "positive": positive,
    })

    # Emotional language
    el = parsed.get("emotional_language", {})
    if el.get("detected"):
        severity = el.get("severity", "MEDIUM")
        signals.append({
            "icon": "🌡️",
            "label": f"Emotional Language ({severity})",
            "detail": "Examples: " + (", ".join(el.get("examples", [])[:3]) or "none"),
            "positive": False,
        })
    else:
        signals.append({
            "icon": "😐",
            "label": "Neutral Language",
            "detail": "No significant emotional manipulation detected.",
            "positive": True,
        })

    # Logical consistency
    lc = parsed.get("logical_consistency", {})
    lc_score = lc.get("score", 50)
    positive = lc_score >= 65
    signals.append({
        "icon": "🧩" if positive else "🔀",
        "label": f"Logical Consistency: {lc_score}/100",
        "detail": "; ".join(lc.get("issues", [])[:2]) or "No logical inconsistencies found.",
        "positive": positive,
    })

    # Claim specificity
    cs = parsed.get("claim_specificity", {})
    cs_score = cs.get("score", 50)
    positive = cs_score >= 65
    signals.append({
        "icon": "🎯" if positive else "💭",
        "label": f"Claim Specificity: {cs_score}/100",
        "detail": cs.get("note", ""),
        "positive": positive,
    })

    # Clickbait heuristics (from local)
    if raw["clickbait_phrases"]:
        signals.append({
            "icon": "🪤",
            "label": f"Clickbait Phrases ({len(raw['clickbait_phrases'])})",
            "detail": f"Detected: {', '.join(raw['clickbait_phrases'][:4])}",
            "positive": False,
        })

    return signals
