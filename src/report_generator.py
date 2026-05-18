"""
PDF report generator — exports full analysis as a professional branded PDF.
Uses fpdf2 (lightweight, no system dependencies).
"""

import os
import io
from datetime import datetime


def generate_pdf_report(result: dict) -> bytes:
    """
    Generate a PDF analysis report from a full analysis result dict.
    Returns raw PDF bytes.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError("fpdf2 not installed. Run: pip install fpdf2")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Colors ──
    GREEN = (0, 200, 100)
    RED   = (239, 68, 68)
    ORANGE = (249, 115, 22)
    YELLOW = (251, 191, 36)
    DARK  = (15, 20, 40)
    GRAY  = (100, 116, 139)
    WHITE = (255, 255, 255)
    LIGHT = (226, 232, 240)

    def verdict_color(verdict: str):
        v = verdict.upper().replace(" ", "_")
        if "FAKE" in v:    return RED
        if "LIKELY_REAL" in v: return GREEN
        if "REAL" in v:   return GREEN
        return YELLOW

    score = result.get("final_score", 50)
    verdict = result.get("verdict", "UNCERTAIN")
    vcolor = verdict_color(verdict)

    # ── Header banner ──
    pdf.set_fill_color(*DARK)
    pdf.rect(0, 0, 210, 42, 'F')
    pdf.set_text_color(*GREEN)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_xy(10, 8)
    pdf.cell(0, 10, "TruthLens — AI Fake News Analysis Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GRAY)
    pdf.set_xy(10, 22)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                   f"Analysis time: {result.get('elapsed_seconds', 0)}s", ln=True)

    # Accent line
    pdf.set_fill_color(*GREEN)
    pdf.rect(0, 40, 210, 1.5, 'F')
    pdf.ln(10)

    # ── Verdict block ──
    pdf.set_fill_color(*vcolor)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_x(10)
    pdf.cell(190, 16, f"  VERDICT: {verdict}   |   Score: {score}/100", ln=True,
             fill=True, align="C")
    pdf.ln(4)

    # Verdict message
    pdf.set_text_color(*GRAY)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_x(10)
    pdf.multi_cell(190, 5, result.get("verdict_message", ""), align="C")
    pdf.ln(6)

    # ── Input info ──
    if result.get("title"):
        pdf.set_text_color(*DARK)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(10)
        pdf.cell(0, 7, "Article:", ln=False)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*GRAY)
        pdf.multi_cell(0, 6, f" {result['title'][:120]}")
        pdf.ln(2)

    if result.get("url"):
        pdf.set_text_color(*DARK)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_x(10)
        pdf.cell(30, 6, "Source URL:", ln=False)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 120, 200)
        pdf.cell(0, 6, result["url"][:90], ln=True)
        pdf.ln(2)

    # ── Score summary table ──
    pdf.set_fill_color(240, 244, 248)
    pdf.set_text_color(*DARK)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_x(10)
    pdf.cell(190, 8, "Layer-by-Layer Score Breakdown", ln=True, fill=True)
    pdf.ln(2)

    layers = [
        ("🤖 AI Analysis (Gemini)", result.get("llm_analysis", {}).get("score", "N/A"), "45%"),
        ("⚡ AI Analysis (Groq/Llama)", result.get("groq_analysis", {}).get("score", "N/A"), "—"),
        ("🤖 ML Classifier (RoBERTa)", result.get("bert_analysis", {}).get("score", "N/A"), "15%"),
        ("🔎 Fact Check DB", result.get("factcheck", {}).get("score", "N/A"), "15%"),
        ("📰 News Cross-Reference", result.get("news_check", {}).get("score", "N/A"), "15%"),
        ("🔎 Source Credibility", result.get("source_check", {}).get("score", "N/A"), "10%"),
    ]
    pdf.set_font("Helvetica", "", 10)
    for name, sc, weight in layers:
        sc_str = str(sc) if sc != "N/A" else "—"
        try:
            sc_val = int(sc)
            bar_color = GREEN if sc_val >= 65 else (YELLOW if sc_val >= 40 else RED)
        except Exception:
            bar_color = GRAY

        pdf.set_x(12)
        pdf.set_text_color(*DARK)
        pdf.cell(100, 6, name, ln=False)
        pdf.set_text_color(*bar_color)
        pdf.cell(30, 6, f"{sc_str}/100", ln=False, align="C")
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 6, f"Weight: {weight}", ln=True, align="R")
    pdf.ln(4)

    # ── AI Summary ──
    llm = result.get("llm_analysis", {})
    if llm.get("summary"):
        pdf.set_fill_color(240, 253, 244)
        pdf.set_text_color(*DARK)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(10)
        pdf.cell(190, 8, "AI Analysis Summary", ln=True, fill=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(50, 60, 80)
        pdf.set_x(10)
        pdf.multi_cell(190, 5, llm["summary"])
        pdf.ln(4)

    # ── Red flags ──
    red_flags = llm.get("red_flags", [])
    if red_flags:
        pdf.set_text_color(*DARK)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(10)
        pdf.cell(0, 8, "Red Flags Detected:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*RED)
        for flag in red_flags[:6]:
            pdf.set_x(14)
            pdf.cell(0, 5, f"• {flag[:100]}", ln=True)
        pdf.ln(3)

    # ── Positive indicators ──
    positives = llm.get("positive_indicators", [])
    if positives:
        pdf.set_text_color(*DARK)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(10)
        pdf.cell(0, 8, "Credibility Indicators:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*GREEN)
        for pos in positives[:6]:
            pdf.set_x(14)
            pdf.cell(0, 5, f"✓ {pos[:100]}", ln=True)
        pdf.ln(3)

    # ── Fact checks ──
    factcheck = result.get("factcheck", {})
    claims = factcheck.get("claims", [])
    if claims:
        pdf.set_text_color(*DARK)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(10)
        pdf.cell(190, 8, f"Fact-Check Records ({len(claims)} found)", ln=True,
                 fill=True)
        pdf.set_font("Helvetica", "", 9)
        for c in claims[:4]:
            rating = c.get("rating", "UNKNOWN")
            r_color = RED if rating == "FALSE" else (GREEN if rating == "TRUE" else YELLOW)
            pdf.set_x(12)
            pdf.set_text_color(*r_color)
            pdf.cell(30, 5, f"[{rating}]", ln=False)
            pdf.set_text_color(*DARK)
            pdf.multi_cell(0, 5, f"{c.get('publisher','')}: {c.get('claim','')[:80]}")
        pdf.ln(3)

    # ── News articles ──
    news = result.get("news_check", {})
    articles = news.get("articles", [])
    if articles:
        pdf.set_text_color(*DARK)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(10)
        pdf.cell(190, 8, f"Cross-Referenced News ({len(articles)} stories)", ln=True, fill=True)
        pdf.set_font("Helvetica", "", 9)
        for a in articles[:4]:
            trusted = " ✅" if a.get("is_trusted") else ""
            pdf.set_x(12)
            pdf.set_text_color(0, 120, 200)
            pdf.cell(50, 5, f"{a.get('source','')}{trusted}", ln=False)
            pdf.set_text_color(*DARK)
            pdf.multi_cell(0, 5, a.get("title", "")[:90])
        pdf.ln(3)

    # ── Footer ──
    pdf.set_y(-20)
    pdf.set_fill_color(*DARK)
    pdf.rect(0, pdf.get_y(), 210, 20, 'F')
    pdf.set_text_color(*GRAY)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_x(10)
    pdf.cell(0, 6,
             "TruthLens AI Fake News Detector | For research purposes only | "
             "Always verify with trusted sources", ln=True, align="C")

    return pdf.output()
