"""TruthLens — AI Fake News Detector (v2 UI: Violet + Amber theme)"""

import os, sys, streamlit as st
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

# ── Streamlit Cloud secrets → os.environ bridge ──────────────────────────────
# On Streamlit Cloud, keys live in st.secrets (TOML).
# Locally, load_dotenv() already populated os.environ from .env.
# This bridge makes both work transparently.
_SECRET_KEYS = [
    "GEMINI_API_KEY", "NEWS_API_KEY", "GROQ_API_KEY",
    "HUGGINGFACE_API_KEY", "GOOGLE_FACTCHECK_API_KEY", "GNEWS_API_KEY",
]
for _k in _SECRET_KEYS:
    if _k not in os.environ:
        try:
            os.environ[_k] = st.secrets[_k]
        except Exception:
            pass  # key not set — handled gracefully by each module

st.set_page_config(page_title="TruthLens — AI Fake News Detector", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, .stApp { font-family: 'Inter', sans-serif !important; background: #060611 !important; color: #e2e0f0 !important; }

[data-testid="stSidebar"] { background: linear-gradient(160deg,#0d0a1f 0%,#0a0818 100%) !important; border-right: 1px solid rgba(139,92,246,0.2) !important; }
[data-testid="stSidebar"] * { color: #c4bfe8 !important; }
.main .block-container { padding: 1.5rem 2rem 4rem !important; max-width: 1080px; }

/* Hero */
.hero {
  background: linear-gradient(135deg,#0f0a24 0%,#0a0618 40%,#12071e 100%);
  border: 1px solid rgba(139,92,246,0.3); border-radius: 24px;
  padding: 2.8rem 2.2rem 2.2rem; margin-bottom: 2rem; position: relative; overflow: hidden;
}
.hero::before { content:''; position:absolute; top:0; left:0; right:0; height:3px;
  background: linear-gradient(90deg,transparent,#8b5cf6,#f59e0b,transparent); }
.hero::after { content:''; position:absolute; bottom:-60px; right:-60px; width:240px; height:240px;
  background: radial-gradient(circle,rgba(139,92,246,0.12) 0%,transparent 70%); border-radius:50%; }
.hero-title { font-family:'Space Grotesk',sans-serif; font-size:2.8rem; font-weight:800; letter-spacing:-0.04em;
  background: linear-gradient(135deg,#a78bfa 0%,#f59e0b 60%,#fb923c 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; margin-bottom:.4rem; }
.hero-sub { font-size:1rem; color:#9d94c8; line-height:1.65; max-width:580px; margin-bottom:1.2rem; }
.hero-tag { background:rgba(139,92,246,0.12); border:1px solid rgba(139,92,246,0.3); color:#a78bfa;
  font-size:.68rem; font-weight:700; letter-spacing:.1em; padding:.2rem .6rem; border-radius:20px;
  text-transform:uppercase; display:inline-block; margin:.15rem; }

/* Input card */
.input-card { background:rgba(13,10,30,0.95); border:1px solid rgba(139,92,246,0.2);
  border-radius:18px; padding:1.6rem; margin-bottom:1.6rem; }

/* Verdict */
.verdict-box { text-align:center; padding:2.2rem 1rem 1.8rem;
  border-radius:22px; border:1px solid; margin-bottom:1.5rem; position:relative; overflow:hidden; }
.verdict-box::before { content:''; position:absolute; top:0; left:0; right:0; height:2px;
  background: var(--vcolor); opacity:.6; }
.v-icon { font-size:3.8rem; display:block; margin-bottom:.4rem; }
.v-label { font-family:'Space Grotesk',sans-serif; font-size:2.6rem; font-weight:800;
  letter-spacing:-.02em; display:block; margin-bottom:.3rem; }
.v-score { font-size:1rem; font-weight:600; color:#6b6490; }
.v-msg { font-size:.92rem; color:#9d94c8; max-width:400px; margin:.4rem auto 0; line-height:1.6; }
.v-time { font-size:.72rem; color:#3d3660; margin-top:.6rem; font-family:'JetBrains Mono',monospace; }

/* Score bar */
.sbar-wrap { margin:.6rem 0; }
.sbar-lbl { font-size:.72rem; color:#6b6490; margin-bottom:.25rem; display:flex; justify-content:space-between; }
.sbar-bg { height:8px; background:rgba(255,255,255,0.06); border-radius:99px; overflow:hidden; }
.sbar-fill { height:100%; border-radius:99px; }

/* Signal cards */
.sgrid { display:grid; grid-template-columns:1fr 1fr; gap:.65rem; margin-top:.8rem; }
.scard { background:rgba(15,12,32,0.9); border-radius:12px; padding:.8rem .95rem; border-left:3px solid; }
.scard.pos { border-color:#8b5cf6; } .scard.neg { border-color:#ef4444; } .scard.neu { border-color:#f59e0b; }
.scard-icon { font-size:1.1rem; } .scard-lbl { font-size:.8rem; font-weight:700; color:#e2e0f0; margin:.15rem 0 .08rem; }
.scard-det { font-size:.72rem; color:#6b6490; line-height:1.4; }

/* Layer header */
.lhdr { display:flex; align-items:center; gap:.55rem; font-size:1rem; font-weight:700;
  margin:1.5rem 0 .85rem; color:#e2e0f0; border-left:3px solid #8b5cf6; padding-left:.8rem; }
.lbadge { background:rgba(245,158,11,0.12); border:1px solid rgba(245,158,11,0.3); color:#f59e0b;
  font-size:.62rem; font-weight:700; padding:.12rem .45rem; border-radius:5px; letter-spacing:.06em; }
.lscore { margin-left:auto; font-family:'JetBrains Mono',monospace; font-size:.82rem;
  font-weight:700; padding:.18rem .55rem; border-radius:7px; background:rgba(255,255,255,0.05); }

/* News article card */
.acard { background:rgba(15,12,32,0.85); border-radius:10px; padding:.85rem 1rem;
  border:1px solid rgba(139,92,246,0.1); margin-bottom:.5rem; }
.acard-src { font-size:.68rem; font-weight:800; text-transform:uppercase; letter-spacing:.06em; color:#f59e0b; margin-bottom:.2rem; }
.acard-title { font-size:.86rem; color:#c4bfe8; line-height:1.45; }
.acard-trusted { display:inline-block; font-size:.62rem; font-weight:700;
  background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.3); color:#a78bfa;
  padding:.08rem .38rem; border-radius:4px; margin-top:.28rem; }

/* Consensus box */
.cons-box { border-radius:16px; padding:1.1rem 1.3rem; margin:.7rem 0; border:1px solid; }

/* History */
.hist-item { background:rgba(15,12,32,0.8); border-radius:10px; padding:.65rem .85rem;
  border:1px solid rgba(139,92,246,0.1); margin-bottom:.45rem; }
.hist-v { font-size:.72rem; font-weight:700; }
.hist-s { font-size:.7rem; color:#3d3660; margin-top:.12rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

/* Status pill */
.api-row { display:flex; align-items:center; gap:.5rem; font-size:.78rem; margin:.22rem 0; }
.dot-on  { width:7px; height:7px; border-radius:50%; background:#8b5cf6; flex-shrink:0; box-shadow:0 0 6px #8b5cf6; }
.dot-off { width:7px; height:7px; border-radius:50%; background:#2d2850; flex-shrink:0; }

/* Streamlit overrides */
.stTextArea textarea, .stTextInput input {
  background:rgba(10,8,22,0.9) !important; border:1px solid rgba(139,92,246,0.25) !important;
  border-radius:12px !important; color:#e2e0f0 !important; font-family:'Inter',sans-serif !important; }
.stTextArea textarea:focus, .stTextInput input:focus {
  border-color:rgba(139,92,246,0.6) !important; box-shadow:0 0 0 3px rgba(139,92,246,0.08) !important; }
.stButton > button {
  background:linear-gradient(135deg,#7c3aed,#6d28d9) !important;
  color:#fff !important; font-weight:800 !important; border:none !important;
  border-radius:12px !important; font-size:.95rem !important; padding:.65rem 1.5rem !important;
  box-shadow:0 4px 20px rgba(139,92,246,0.35) !important; width:100% !important; transition:all .2s !important; }
.stButton > button:hover { transform:translateY(-1px) !important; box-shadow:0 6px 28px rgba(139,92,246,0.5) !important; }
div[data-testid="stExpander"] { background:rgba(13,10,30,0.9) !important;
  border:1px solid rgba(139,92,246,0.15) !important; border-radius:12px !important; }
.stTabs [data-baseweb="tab-list"] { background:rgba(13,10,30,0.8) !important; border-radius:12px !important; gap:4px; padding:4px; }
.stTabs [data-baseweb="tab"] { border-radius:9px !important; color:#9d94c8 !important; }
.stTabs [aria-selected="true"] { background:rgba(139,92,246,0.2) !important; color:#a78bfa !important; }
hr { border-color:rgba(139,92,246,0.1) !important; }
.stAlert { border-radius:12px !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────
for k, v in [("history",[]),("result",None),("textarea_val",""),("run_example",False)]:
    if k not in st.session_state: st.session_state[k] = v

EXAMPLE = """BREAKING: Scientists SHOCKED as New Study PROVES 5G Towers Cause Memory Loss — Government Hiding the Truth!

A bombshell new study that the mainstream media doesn't want you to see has revealed that exposure to 5G towers causes severe memory loss. The study, conducted by unnamed researchers at an undisclosed university, found 100% of participants experienced significant memory impairment after just 30 days near a 5G tower.

\"They're hiding this from us,\" said one anonymous source. \"Big Tech and the Deep State have paid billions to suppress these findings.\" Wake up, sheeple! The new world order wants to control your mind. Share this before they take it down!"""

# ── Helpers ────────────────────────────────────────────────────────────────
def vc(s):
    if s>=80: return "#8b5cf6"
    if s>=60: return "#a78bfa"
    if s>=40: return "#f59e0b"
    if s>=20: return "#f97316"
    return "#ef4444"

def sbar(score, label=""):
    c = vc(score)
    lbl = f'<div class="sbar-lbl"><span>{label}</span><span style="color:{c};">{score}/100</span></div>' if label else ""
    st.markdown(f'<div class="sbar-wrap">{lbl}<div class="sbar-bg"><div class="sbar-fill" style="width:{score}%;background:{c};"></div></div></div>', unsafe_allow_html=True)

def signals(lst):
    if not lst: return
    h = '<div class="sgrid">'
    for s in lst:
        p = s.get("positive")
        cls = "pos" if p is True else ("neg" if p is False else "neu")
        h += f'<div class="scard {cls}"><div class="scard-icon">{s.get("icon","ℹ️")}</div><div class="scard-lbl">{s.get("label","")}</div><div class="scard-det">{s.get("detail","")}</div></div>'
    st.markdown(h+"</div>", unsafe_allow_html=True)

def lhdr(icon, title, badge, score):
    c = vc(score)
    st.markdown(f'<div class="lhdr">{icon} {title} <span class="lbadge">{badge}</span><span class="lscore" style="color:{c};">{score}/100</span></div>', unsafe_allow_html=True)

def flag_list(items, red=True):
    if not items:
        st.markdown('<p style="font-size:.8rem;color:#3d3660;">None detected.</p>', unsafe_allow_html=True); return
    pre = "⛳ " if red else "✓ "
    col = "#ef4444" if red else "#8b5cf6"
    st.markdown("".join(f'<p style="font-size:.8rem;color:{col};padding:.2rem 0;">{pre}{i}</p>' for i in items), unsafe_allow_html=True)

def art_cards(arts):
    for a in arts:
        tb = '<span class="acard-trusted">✦ TRUSTED</span>' if a.get("is_trusted") else ""
        desc = a.get("description","")[:110]+"…" if len(a.get("description",""))>110 else a.get("description","")
        st.markdown(f'<div class="acard"><div class="acard-src">{a.get("source","")}</div><div class="acard-title"><a href="{a.get("url","#")}" target="_blank" style="color:#c4bfe8;text-decoration:none;">{a.get("title","")}</a></div>{"<div style=font-size:.72rem;color:#3d3660;>"+desc+"</div>" if desc else ""}{tb}</div>', unsafe_allow_html=True)

def verdict_box(r):
    s = r["final_score"]; c = vc(s)
    st.markdown(f'<div class="verdict-box" style="background:rgba(10,8,22,.95);border-color:{c}33;--vcolor:{c}"><span class="v-icon">{r["verdict_icon"]}</span><span class="v-label" style="color:{c};">{r["verdict"]}</span><div class="v-score">Credibility Score: <strong style="color:{c};">{s}/100</strong></div><div class="v-msg">{r["verdict_message"]}</div><div class="v-time">⏱ {r.get("elapsed_seconds",0)}s</div></div>', unsafe_allow_html=True)

def render_results(r):
    verdict_box(r)

    # PDF download
    try:
        from src.report_generator import generate_pdf_report
        st.download_button("📄 Download PDF Report", generate_pdf_report(r),
            file_name=f"truthlens_{r.get('domain','report')}.pdf", mime="application/pdf", use_container_width=True)
    except Exception: pass

    st.markdown("<br>", unsafe_allow_html=True)
    ls = r.get("layer_scores", {})
    llm = r.get("llm_analysis",{}) or {}
    groq = r.get("groq_analysis",{}) or {}
    bert = r.get("bert_analysis",{}) or {}
    fc = r.get("factcheck",{}) or {}
    news = r.get("news_check",{}) or {}
    src = r.get("source_check",{}) or {}
    cons = r.get("llm_consensus",{}) or {}
    ent = r.get("entity_check",{}) or {}

    # Radar + score bars
    if ls:
        c1, c2 = st.columns([1,1])
        with c1:
            st.markdown('<p style="font-size:.72rem;font-weight:700;color:#6b6490;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.4rem;">Signal Radar</p>', unsafe_allow_html=True)
            try:
                import plotly.graph_objects as go
                cats=["Gemini","Groq","ML","FactCheck","News","Source"]
                vals=[ls.get(k,50) for k in["gemini","groq","bert","factcheck","news","source"]]
                fig=go.Figure(go.Scatterpolar(r=vals+[vals[0]],theta=cats+[cats[0]],fill="toself",
                    fillcolor="rgba(139,92,246,0.08)",line=dict(color="#8b5cf6",width=2),marker=dict(color="#f59e0b",size=5)))
                fig.update_layout(polar=dict(bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(visible=True,range=[0,100],tickfont=dict(color="#3d3660",size=8),gridcolor="rgba(139,92,246,0.1)"),
                    angularaxis=dict(tickfont=dict(color="#9d94c8",size=9),gridcolor="rgba(139,92,246,0.1)")),
                    paper_bgcolor="rgba(0,0,0,0)",margin=dict(l=25,r=25,t=10,b=10),height=250)
                st.plotly_chart(fig, use_container_width=True)
            except Exception: pass
        with c2:
            st.markdown('<p style="font-size:.72rem;font-weight:700;color:#6b6490;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.4rem;">Layer Scores</p>', unsafe_allow_html=True)
            for name, key in [("🤖 Gemini","gemini"),("⚡ Groq","groq"),("🧠 ML","bert"),("🔍 FactCheck","factcheck"),("📰 News","news"),("🌐 Source","source")]:
                sbar(ls.get(key,50), name)

    st.markdown("<br>", unsafe_allow_html=True)

    # Layer 1 — Gemini
    lhdr("🤖","AI Analysis","Gemini 1.5 Flash · 25%", llm.get("score",50))
    if llm.get("error"): st.warning(f"⚠️ {llm['error']}")
    if llm.get("summary"):
        st.markdown(f'<div style="background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.18);border-radius:12px;padding:.9rem 1.1rem;margin-bottom:.9rem;font-size:.88rem;color:#9d94c8;line-height:1.65;">💬 <strong style="color:#e2e0f0;">Summary:</strong> {llm["summary"]}</div>', unsafe_allow_html=True)
    signals(llm.get("signals",[]))
    with st.expander("📊 Detailed Breakdown"):
        wq=llm.get("writing_quality",{}); el=llm.get("emotional_language",{}); lc=llm.get("logical_consistency",{}); cs=llm.get("claim_specificity",{})
        x1,x2=st.columns(2)
        with x1: sbar(wq.get("score",50),"Writing Quality"); sbar(lc.get("score",50),"Logic")
        with x2: sbar(cs.get("score",50),"Claim Specificity")
        if el.get("detected"): st.markdown(f'<p style="font-size:.8rem;color:#f97316;margin-top:.5rem;">🌡️ Emotional severity: <b>{el.get("severity","—")}</b></p>', unsafe_allow_html=True)
        if llm.get("red_flags"): st.markdown("**🚩 Red Flags:**"); flag_list(llm["red_flags"])
        if llm.get("positive_indicators"): st.markdown("**✅ Positives:**"); flag_list(llm["positive_indicators"], red=False)
        if llm.get("recommended_action"): st.info(f"💡 {llm['recommended_action']}")

    # Groq consensus
    if groq.get("api_available") and cons:
        cc = cons.get("consensus_color","#f59e0b")
        gs,grs = cons.get("gemini_score","—"), cons.get("groq_score","—")
        st.markdown(f'<div class="cons-box" style="background:rgba(13,10,30,.95);border-color:{cc}33;"><div style="font-size:.65rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:{cc};margin-bottom:.4rem;">⚡ Dual-LLM Consensus</div><div style="font-size:.95rem;font-weight:700;color:#e2e0f0;margin-bottom:.3rem;">{cons.get("consensus_label","")}</div><div style="font-size:.8rem;color:#9d94c8;">{cons.get("explanation","")}</div><div style="display:flex;gap:2rem;margin-top:.7rem;"><div style="text-align:center;"><div style="font-size:.6rem;color:#3d3660;text-transform:uppercase;">Gemini</div><div style="font-size:1.4rem;font-weight:900;color:{vc(gs if isinstance(gs,int) else 50)};">{gs}</div></div><div style="align-self:center;color:#2d2850;">vs</div><div style="text-align:center;"><div style="font-size:.6rem;color:#3d3660;text-transform:uppercase;">Llama-3</div><div style="font-size:1.4rem;font-weight:900;color:{vc(grs if isinstance(grs,int) else 50)};">{grs}</div></div></div></div>', unsafe_allow_html=True)
        if groq.get("summary"):
            with st.expander("🦙 Llama-3 Details"):
                st.markdown(f'<p style="font-size:.85rem;color:#9d94c8;">{groq["summary"]}</p>', unsafe_allow_html=True)
                if groq.get("top_red_flags"): flag_list(groq["top_red_flags"])
                if groq.get("top_positives"): flag_list(groq["top_positives"], red=False)

    st.markdown("<hr>", unsafe_allow_html=True)

    # Layer 3 — ML
    if bert.get("api_available"):
        lhdr("🧠","ML Classifier","RoBERTa · LIAR dataset · 15%", bert.get("score",50))
        if bert.get("error"): st.warning(f"⚠️ {bert['error']}")
        signals(bert.get("signals",[]))
        if bert.get("fake_probability"):
            b1,b2=st.columns(2)
            with b1: sbar(round(bert["real_probability"]*100),"Real Probability")
            with b2: sbar(round(bert["fake_probability"]*100),"Fake Probability")
        st.markdown("<hr>", unsafe_allow_html=True)

    # Layer 4 — Fact Check
    lhdr("🔍","Fact-Check Database","Google Fact Check · 15%", fc.get("score",50))
    if fc.get("error"): st.warning(f"⚠️ {fc['error']}")
    signals(fc.get("signals",[]))
    if fc.get("claims"):
        RC={"TRUE":"#8b5cf6","FALSE":"#ef4444","MISLEADING":"#f59e0b","UNKNOWN":"#3d3660"}
        with st.expander(f"📋 {len(fc['claims'])} Fact-Check Record(s)", expanded=True):
            for c in fc["claims"]:
                rc=RC.get(c.get("rating","UNKNOWN"),"#3d3660")
                st.markdown(f'<div class="acard"><div style="display:flex;gap:.5rem;align-items:center;margin-bottom:.3rem;"><span style="font-size:.65rem;font-weight:800;padding:.1rem .4rem;border-radius:4px;background:{rc}18;border:1px solid {rc}44;color:{rc};">{c.get("rating","?")}</span><span style="font-size:.68rem;color:#f59e0b;font-weight:700;">{c.get("publisher","")} {c.get("date","")}</span></div><div class="acard-title">{c.get("claim","")[:180]}</div></div>', unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    # Layer 5 — News
    lhdr("📰","News Cross-Reference",f"{news.get('api_used','NewsAPI')} · 15%", news.get("score",50))
    if news.get("error"): st.warning(f"⚠️ {news['error']}")
    if news.get("query_used"): st.markdown(f'<p style="font-size:.76rem;color:#3d3660;">🔍 Query: <code style="color:#f59e0b;">{news["query_used"]}</code></p>', unsafe_allow_html=True)
    signals(news.get("signals",[]))
    if news.get("articles"):
        with st.expander(f"📋 {len(news['articles'])} Matching Stories", expanded=True): art_cards(news["articles"])
    st.markdown("<hr>", unsafe_allow_html=True)

    # Layer 6 — Source
    lhdr("🌐","Source Credibility","Domain DB + WHOIS · 10%", src.get("score",50))
    if src.get("domain"):
        CC={"credible":"#8b5cf6","satire":"#f59e0b","fake_news":"#ef4444","highly_biased":"#f97316","unknown":"#3d3660"}
        cat=src.get("category","unknown"); cc=CC.get(cat,"#3d3660")
        st.markdown(f'<div style="margin-bottom:.7rem;"><span style="font-size:.82rem;color:#6b6490;">Domain: </span><code style="color:#f59e0b;">{src["domain"]}</code> <span style="font-size:.68rem;font-weight:700;background:{cc}18;border:1px solid {cc}44;color:{cc};padding:.1rem .38rem;border-radius:4px;text-transform:uppercase;">{cat.replace("_"," ")}</span></div>', unsafe_allow_html=True)
    signals(src.get("signals",[]))

    # Entity check
    if ent.get("verified") or ent.get("unverified"):
        st.markdown("<hr>", unsafe_allow_html=True)
        lhdr("🏷️","Entity Verification","Wikipedia · Context", ent.get("score",50))
        signals(ent.get("signals",[]))
        ev, eu = ent.get("verified",[]), ent.get("unverified",[])
        if ev or eu:
            e1,e2=st.columns(2)
            with e1:
                st.markdown(f'<p style="font-size:.75rem;font-weight:700;color:#8b5cf6;">✅ Verified ({len(ev)})</p>', unsafe_allow_html=True)
                for v in ev: st.markdown(f'<div style="background:rgba(139,92,246,0.05);border:1px solid rgba(139,92,246,0.15);border-radius:8px;padding:.45rem .7rem;margin-bottom:.35rem;"><div style="font-size:.78rem;font-weight:600;color:#e2e0f0;">{v["entity"]}</div><div style="font-size:.68rem;color:#3d3660;">{v.get("snippet","")[:75]}…</div></div>', unsafe_allow_html=True)
            with e2:
                st.markdown(f'<p style="font-size:.75rem;font-weight:700;color:#ef4444;">❓ Unverified ({len(eu)})</p>', unsafe_allow_html=True)
                for u in eu: st.markdown(f'<div style="background:rgba(239,68,68,0.04);border:1px solid rgba(239,68,68,0.15);border-radius:8px;padding:.45rem .7rem;margin-bottom:.35rem;"><div style="font-size:.78rem;color:#9d94c8;">{u}</div></div>', unsafe_allow_html=True)


# ── Sidebar (no API inputs — keys from .env only) ──────────────────────────
with st.sidebar:
    st.markdown('<div style="padding:.5rem 0 1.2rem;"><div style="font-family:Space Grotesk,sans-serif;font-size:1.3rem;font-weight:800;background:linear-gradient(135deg,#a78bfa,#f59e0b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">🔍 TruthLens</div><div style="font-size:.72rem;color:#3d3660;margin-top:.15rem;">AI Fake News Detector v2</div></div>', unsafe_allow_html=True)

    # API Status (read-only)
    st.markdown('<p style="font-size:.68rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#3d3660;margin-bottom:.5rem;">API Status</p>', unsafe_allow_html=True)
    apis = [
        ("Gemini 1.5 Flash", bool(os.getenv("GEMINI_API_KEY"))),
        ("NewsAPI", bool(os.getenv("NEWS_API_KEY"))),
        ("Groq / Llama-3", bool(os.getenv("GROQ_API_KEY"))),
        ("HuggingFace ML", bool(os.getenv("HUGGINGFACE_API_KEY"))),
        ("Google Fact Check", bool(os.getenv("GOOGLE_FACTCHECK_API_KEY"))),
        ("GNews (backup)", bool(os.getenv("GNEWS_API_KEY"))),
    ]
    for name, ok in apis:
        st.markdown(f'<div class="api-row"><div class="{"dot-on" if ok else "dot-off"}"></div><span style="color:{"#c4bfe8" if ok else "#3d3660"};">{name}</span></div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<p style="font-size:.68rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#3d3660;margin-bottom:.5rem;">Recent Analyses</p>', unsafe_allow_html=True)
    if not st.session_state.history:
        st.markdown('<p style="font-size:.78rem;color:#2d2850;">No analyses yet.</p>', unsafe_allow_html=True)
    else:
        for h in reversed(st.session_state.history[-5:]):
            st.markdown(f'<div class="hist-item"><div class="hist-v" style="color:{h["color"]};">{h["icon"]} {h["verdict"]} — {h["score"]}/100</div><div class="hist-s">{h["text"]}</div></div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:.7rem;color:#2d2850;line-height:1.7;"><strong style="color:#3d3660;">6-Layer Pipeline:</strong><br>🤖 Gemini 1.5 Flash (25%)<br>⚡ Groq Llama-3 (20%)<br>🧠 RoBERTa ML (15%)<br>🔍 Fact Check DB (15%)<br>📰 NewsAPI+GNews (15%)<br>🌐 Source DB (10%)</div>', unsafe_allow_html=True)


# ── Hero ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-title">🔍 TruthLens</div>
  <div class="hero-sub">6-layer AI analysis — Gemini + Llama-3 + RoBERTa + Fact Checkers + NewsAPI + Source DB. Paste any article, headline, or claim.</div>
  <div>
    <span class="hero-tag">6-Layer AI</span><span class="hero-tag">Gemini 1.5 Flash</span>
    <span class="hero-tag">Groq Llama-3</span><span class="hero-tag">Fact Check DB</span>
    <span class="hero-tag">NewsAPI + GNews</span><span class="hero-tag">Wikipedia NER</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Input panel ────────────────────────────────────────────────────────────
st.markdown('<div class="input-card">', unsafe_allow_html=True)
tab1, tab2 = st.tabs(["\U0001f4dd  Paste Article / Headline", "\U0001f517  Analyse by URL"])

with tab1:
    # Pre-fill text_area via session_state key before widget renders
    if st.session_state.get("run_example"):
        st.session_state["textarea_val"] = EXAMPLE
        st.session_state["run_example"] = False

    user_text = st.text_area("", value=st.session_state.get("textarea_val",""),
        placeholder="Paste any news article, headline, or claim here\u2026",
        height=200, label_visibility="collapsed", key="_ta")
    # Sync back so value persists across reruns
    st.session_state["textarea_val"] = user_text

    c1, c2 = st.columns([2,1])
    with c1: btn_text = st.button("\U0001f50d  Analyze", key="btn_t", use_container_width=True)
    with c2:
        if st.button("\U0001f4cb  Load Example", key="btn_ex", use_container_width=True):
            st.session_state["run_example"] = True
            st.rerun()

with tab2:
    user_url = st.text_input("", placeholder="https://example.com/article", label_visibility="collapsed")
    btn_url = st.button("\U0001f50d  Fetch & Analyze", key="btn_u", use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)
# ── Run analysis ───────────────────────────────────────────────────────────
inp = None
if btn_text and user_text and user_text.strip(): inp = user_text.strip()
elif btn_url and user_url and user_url.strip(): inp = user_url.strip()
elif btn_text and not (user_text and user_text.strip()): st.error("Please enter some text first.")
elif btn_url and not (user_url and user_url.strip()): st.error("Please enter a URL first.")

if inp:
    from src.analyzer import run_full_analysis
    ph = st.empty()
    STEPS = ["","🔍 Resolving input…","🔎 Checking source…","🤖 Running AI analysis…","📰 Cross-referencing news…","🧮 Computing verdict…","✅ Done!"]

    def _prog(step, msg):
        bars = "".join(
            f'<div style="display:flex;align-items:center;gap:.55rem;padding:.35rem 0;opacity:{"1" if i<=step else "0.2"};">'
            f'<span style="font-size:.82rem;">{"✅" if i<step else ("⟳" if i==step else "○")}</span>'
            f'<span style="font-size:.82rem;color:{"#e2e0f0" if i<=step else "#2d2850"};">{STEPS[i]}</span></div>'
            for i in range(1,7))
        ph.markdown(f'<div style="background:rgba(13,10,30,.95);border:1px solid rgba(139,92,246,.25);border-radius:16px;padding:1.1rem 1.4rem;margin-bottom:1rem;"><div style="font-size:.68rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#8b5cf6;margin-bottom:.7rem;">⚡ Analysis Pipeline</div>{bars}</div>', unsafe_allow_html=True)

    with st.spinner(""):
        res = run_full_analysis(inp, progress_callback=_prog)
    ph.empty()

    if res.get("error"): st.error(f"❌ {res['error']}")
    else:
        st.session_state.result = res
        st.session_state.history.append({"text":(res.get("title") or inp)[:70], "verdict":res["verdict"],
            "score":res["final_score"], "icon":res["verdict_icon"], "color":res["verdict_color"]})
        st.rerun()

# ── Show results ───────────────────────────────────────────────────────────
if st.session_state.result and not inp:
    r = st.session_state.result
    if r.get("title"): st.markdown(f'<h3 style="font-size:1rem;font-weight:700;color:#6b6490;margin-bottom:1rem;">📄 {r["title"]}</h3>', unsafe_allow_html=True)
    render_results(r)
    if st.button("🗑️  Clear & Analyze Another", key="btn_clr"): st.session_state.result = None; st.rerun()

