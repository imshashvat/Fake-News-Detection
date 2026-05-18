"""
Groq API integration — Llama-3.3 70B as a second LLM for cross-validation.
Runs in parallel with Gemini to get an independent verdict.
Groq is free with generous limits: https://console.groq.com
"""

import os
import json
import re
from src.utils import truncate_text

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

GROQ_PROMPT = """You are a fact-checking expert. Analyze this news article for credibility.

ARTICLE:
---
{article_text}
---
{title_line}

Respond ONLY with a valid JSON object (no markdown, no code fences):
{{
  "credibility_score": <integer 0-100>,
  "verdict": "<REAL|LIKELY_REAL|UNCERTAIN|LIKELY_FAKE|FAKE>",
  "confidence": "<HIGH|MEDIUM|LOW>",
  "summary": "<2 sentence assessment>",
  "top_red_flags": ["<up to 3 specific red flags>"],
  "top_positives": ["<up to 3 credibility indicators>"]
}}"""


def analyze_with_groq(article_text: str, title: str = "") -> dict:
    """
    Analyze article with Groq Llama-3 as a second opinion.

    Returns:
        {
            score: float,
            verdict: str,
            confidence: str,
            summary: str,
            top_red_flags: list,
            top_positives: list,
            api_available: bool,
            error: str | None,
        }
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    result = {
        "score": 50,
        "verdict": "UNCERTAIN",
        "confidence": "LOW",
        "summary": "",
        "top_red_flags": [],
        "top_positives": [],
        "api_available": bool(api_key and api_key not in ("", "your_key_here")),
        "error": None,
    }

    if not result["api_available"]:
        result["error"] = "Groq API key not configured. Add GROQ_API_KEY to .env."
        return result

    try:
        import requests
        title_line = f"\nTITLE: {title}" if title else ""
        safe_text = truncate_text(article_text, 4000)
        prompt = GROQ_PROMPT.format(article_text=safe_text, title_line=title_line)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 600,
        }
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=20)

        if resp.status_code == 401:
            result["error"] = "Invalid Groq API key."
            return result
        if resp.status_code == 429:
            result["error"] = "Groq rate limit reached."
            return result
        if resp.status_code != 200:
            result["error"] = f"Groq API error: HTTP {resp.status_code}"
            return result

        raw = resp.json()["choices"][0]["message"]["content"].strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        parsed = json.loads(raw)
        result["score"] = int(parsed.get("credibility_score", 50))
        result["verdict"] = parsed.get("verdict", "UNCERTAIN")
        result["confidence"] = parsed.get("confidence", "MEDIUM")
        result["summary"] = parsed.get("summary", "")
        result["top_red_flags"] = parsed.get("top_red_flags", [])
        result["top_positives"] = parsed.get("top_positives", [])

    except json.JSONDecodeError:
        result["error"] = "Groq returned non-JSON response."
    except Exception as e:
        result["error"] = f"Groq error: {str(e)[:150]}"

    return result


def compute_llm_consensus(gemini_result: dict, groq_result: dict) -> dict:
    """
    Compare Gemini and Groq verdicts and compute consensus.

    Returns:
        {
            consensus: str,         # 'AGREE' | 'PARTIAL' | 'DISAGREE'
            consensus_label: str,
            consensus_color: str,
            combined_score: float,
            explanation: str,
        }
    """
    g_score = gemini_result.get("score", 50)
    gr_score = groq_result.get("score", 50)
    g_verdict = gemini_result.get("verdict", "UNCERTAIN")
    gr_verdict = groq_result.get("verdict", "UNCERTAIN")

    diff = abs(g_score - gr_score)
    combined = round((g_score * 0.55) + (gr_score * 0.45))  # Gemini weighted slightly higher

    FAKE_VERDICTS = {"FAKE", "LIKELY_FAKE"}
    REAL_VERDICTS = {"REAL", "LIKELY_REAL"}

    if g_verdict == gr_verdict:
        consensus = "AGREE"
        label = "✅ Both LLMs Agree"
        color = "#8b5cf6"
        explanation = f"Gemini and Llama-3 both returned {g_verdict.replace('_', ' ')} ({g_score} vs {gr_score}). High confidence."
    elif (g_verdict in FAKE_VERDICTS and gr_verdict in FAKE_VERDICTS) or \
         (g_verdict in REAL_VERDICTS and gr_verdict in REAL_VERDICTS):
        consensus = "PARTIAL"
        label = "🟡 LLMs Broadly Agree"
        color = "#f59e0b"
        explanation = f"Both LLMs lean the same direction (Gemini: {g_verdict}, Llama-3: {gr_verdict}) with {diff}-point score difference."
    else:
        consensus = "DISAGREE"
        label = "🔴 LLMs Disagree"
        color = "#f97316"
        explanation = f"Gemini says {g_verdict.replace('_', ' ')} ({g_score}/100) but Llama-3 says {gr_verdict.replace('_', ' ')} ({gr_score}/100). Treat as UNCERTAIN."
        combined = 50  # force uncertain when LLMs disagree

    return {
        "consensus": consensus,
        "consensus_label": label,
        "consensus_color": color,
        "combined_score": combined,
        "explanation": explanation,
        "gemini_score": g_score,
        "groq_score": gr_score,
    }
