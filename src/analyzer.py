"""
TruthLens — Core Analysis Orchestrator (Phase 2: 6-Layer Pipeline)
Runs all analysis layers concurrently where possible and combines scores.
"""

import time
import threading
from src.gemini_client import analyze_with_gemini
from src.groq_client import analyze_with_groq, compute_llm_consensus
from src.ml_classifier import classify_with_bert
from src.factcheck_api import search_fact_checks
from src.news_checker import cross_reference_news
from src.source_checker import check_source_credibility
from src.wikipedia_checker import verify_entities
from src.utils import clean_text, is_valid_url, fetch_article_text


# ── Scoring weights (Phase 2) ──────────────────────────────────────────────
W_GEMINI   = 0.25
W_GROQ     = 0.20
W_BERT     = 0.15
W_FACTCHECK= 0.15
W_NEWS     = 0.15
W_SOURCE   = 0.10


VERDICT_MAP = [
    (85, "REAL",         "✅", "#8b5cf6", "This content appears credible and factual."),
    (65, "LIKELY REAL",  "🟢", "#a78bfa", "Strong indicators of credibility detected."),
    (40, "UNCERTAIN",    "🟡", "#f59e0b", "Mixed signals. Verify with additional trusted sources."),
    (20, "LIKELY FAKE",  "🟠", "#f97316", "Multiple red flags detected. Treat with skepticism."),
    ( 0, "FAKE",         "🔴", "#ef4444", "Strong indicators of misinformation detected."),
]


def _get_verdict(score: float) -> tuple:
    for threshold, *info in VERDICT_MAP:
        if score >= threshold:
            return tuple(info)
    return VERDICT_MAP[-1][1:]


def run_full_analysis(text_or_url: str, progress_callback=None) -> dict:
    """
    Run 6-layer analysis pipeline with parallel execution where safe.
    Returns complete analysis result dict.
    """
    # Force-reload .env every run so newly added keys are always picked up
    from dotenv import load_dotenv
    load_dotenv(override=True)

    start_time = time.time()

    result = {
        "input_type": "text",
        "raw_text": "",
        "title": "",
        "url": None,
        "domain": None,
        "final_score": 50,
        "verdict": "UNCERTAIN",
        "verdict_icon": "🟡",
        "verdict_color": "#fbbf24",
        "verdict_message": "",
        "llm_analysis": None,
        "groq_analysis": None,
        "llm_consensus": None,
        "bert_analysis": None,
        "factcheck": None,
        "news_check": None,
        "source_check": None,
        "entity_check": None,
        "layer_scores": {},
        "elapsed_seconds": 0,
        "error": None,
    }

    def _p(step, msg):
        if progress_callback:
            progress_callback(step, msg)

    # ── Step 1: Resolve input ─────────────────────────────────────────────
    _p(1, "🔍 Resolving input…")
    if is_valid_url(text_or_url.strip()):
        result["input_type"] = "url"
        result["url"] = text_or_url.strip()
        _p(1, f"🌐 Fetching article from URL…")
        fetch = fetch_article_text(result["url"])
        if not fetch["success"]:
            result["error"] = fetch.get("error", "Failed to fetch article.")
            return result
        result["raw_text"] = fetch["text"]
        result["title"]    = fetch["title"]
        result["domain"]   = fetch["domain"]
    else:
        result["raw_text"] = clean_text(text_or_url)
        if len(result["raw_text"]) < 10:
            result["error"] = "Input too short. Please enter at least a headline or sentence."
            return result

    text  = result["raw_text"]
    title = result["title"]
    url   = result["url"] or ""

    # ── Step 2: Source check (fast, no API needed) ────────────────────────
    _p(2, "🔎 Checking source credibility…")
    source_result = check_source_credibility(url)
    result["source_check"] = source_result
    if result["domain"] is None:
        result["domain"] = source_result.get("domain", "")

    # ── Steps 3-6: Run remaining layers concurrently ──────────────────────
    _p(3, "🤖 Running AI + ML analysis in parallel…")

    gemini_result = groq_result = bert_result = factcheck_result = news_result = entity_result = None

    def _run_gemini():
        nonlocal gemini_result
        gemini_result = analyze_with_gemini(text, title)

    def _run_groq():
        nonlocal groq_result
        groq_result = analyze_with_groq(text, title)

    def _run_bert():
        nonlocal bert_result
        bert_result = classify_with_bert(text)

    def _run_factcheck():
        nonlocal factcheck_result
        factcheck_result = search_fact_checks(text, title)

    def _run_news():
        nonlocal news_result
        news_result = cross_reference_news(text, title)

    def _run_entities():
        nonlocal entity_result
        # Pass Gemini named entities if available after Gemini runs
        entity_result = verify_entities(text)

    # Launch all threads concurrently
    threads = [
        threading.Thread(target=_run_gemini, daemon=True),
        threading.Thread(target=_run_groq,   daemon=True),
        threading.Thread(target=_run_bert,   daemon=True),
        threading.Thread(target=_run_factcheck, daemon=True),
        threading.Thread(target=_run_news,   daemon=True),
        threading.Thread(target=_run_entities, daemon=True),
    ]
    for t in threads:
        t.start()

    # Progress updates while waiting
    _p(4, "📰 Cross-referencing news + fact-check databases…")
    for t in threads:
        t.join(timeout=45)  # max 45s total
    _p(5, "🧮 Computing final verdict…")

    # ── LLM Consensus ────────────────────────────────────────────────────
    # If Gemini failed (quota/error), skip it from consensus — Groq is authoritative
    gemini_failed = bool((gemini_result or {}).get("error"))
    if gemini_failed and groq_result and not groq_result.get("error"):
        # Build a synthetic consensus using only Groq
        gr_v = groq_result.get("verdict", "UNCERTAIN")
        gr_s = groq_result.get("score", 50)
        consensus = {
            "consensus": "GROQ_ONLY",
            "consensus_label": "⚡ Llama-3 Primary (Gemini quota exceeded)",
            "consensus_color": "#8b5cf6",
            "combined_score": gr_s,
            "explanation": f"Gemini quota exceeded — Llama-3 is acting as primary LLM. Verdict: {gr_v.replace('_',' ')} ({gr_s}/100).",
            "gemini_score": "—",
            "groq_score": gr_s,
        }
    else:
        consensus = compute_llm_consensus(gemini_result or {}, groq_result or {})


    result["llm_analysis"]  = gemini_result
    result["groq_analysis"] = groq_result
    result["llm_consensus"] = consensus
    result["bert_analysis"] = bert_result
    result["factcheck"]     = factcheck_result
    result["news_check"]    = news_result
    result["entity_check"]  = entity_result

    # ── Weighted final score ──────────────────────────────────────────────
    g_score  = (gemini_result   or {}).get("score", 45)
    gr_score = (groq_result     or {}).get("score", 45)
    b_score  = (bert_result     or {}).get("score", 45)
    fc_score = (factcheck_result or {}).get("score", 45)
    n_score  = (news_result     or {}).get("score", 45)
    s_score  = source_result.get("score", 45)

    groq_ok = (groq_result or {}).get("api_available", False) and not (groq_result or {}).get("error")
    bert_ok = (bert_result or {}).get("api_available", False) and not (bert_result or {}).get("error")
    fc_ok   = (factcheck_result or {}).get("api_available", False) and not (factcheck_result or {}).get("error")

    # Detect Gemini failure (quota, error) → promote Groq as primary
    gemini_failed = bool((gemini_result or {}).get("error"))
    gemini_ok = not gemini_failed

    if gemini_ok and groq_ok and bert_ok and fc_ok:
        # All 6 layers working
        raw_score = (
            g_score  * W_GEMINI +
            gr_score * W_GROQ   +
            b_score  * W_BERT   +
            fc_score * W_FACTCHECK +
            n_score  * W_NEWS   +
            s_score  * W_SOURCE
        )
    elif not gemini_ok and groq_ok:
        # Gemini down → Groq is primary LLM at 45%
        w_bert = 0.15 if bert_ok else 0
        w_fc   = 0.15 if fc_ok  else 0
        w_news = 0.25
        w_src  = 0.15
        weight_sum = 0.45 + w_bert + w_fc + w_news + w_src
        raw_score = (
            gr_score * 0.45 +
            b_score  * w_bert +
            fc_score * w_fc +
            n_score  * w_news +
            s_score  * w_src
        ) / weight_sum
    elif groq_ok:
        raw_score = (
            g_score  * 0.35 +
            gr_score * 0.25 +
            n_score  * 0.25 +
            s_score  * 0.15
        )
    else:
        # Only Gemini or heuristics
        raw_score = (
            g_score  * 0.45 +
            n_score  * 0.30 +
            s_score  * 0.25
        )

    final_score = round(max(0, min(100, raw_score)))

    # Hard overrides
    if source_result.get("category") == "fake_news":
        final_score = min(final_score, 22)
    elif source_result.get("category") == "credible" and g_score >= 70:
        final_score = max(final_score, 65)

    # LLM disagreement → cap at UNCERTAIN range
    # BUT: don't cap if Gemini failed (GROQ_ONLY mode) — Groq verdict is authoritative
    if consensus.get("consensus") == "DISAGREE":
        final_score = max(35, min(55, final_score))

    result["final_score"] = final_score
    result["layer_scores"] = {
        "gemini": g_score, "groq": gr_score, "bert": b_score,
        "factcheck": fc_score, "news": n_score, "source": s_score,
    }

    verdict, icon, color, message = _get_verdict(final_score)
    result["verdict"]         = verdict
    result["verdict_icon"]    = icon
    result["verdict_color"]   = color
    result["verdict_message"] = message
    result["elapsed_seconds"] = round(time.time() - start_time, 1)

    _p(6, "✅ Analysis complete!")
    return result
