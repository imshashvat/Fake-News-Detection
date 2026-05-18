# TruthLens — AI Fake News Detector

A premium, **3-layer AI-powered fake news detection** system built with Streamlit and Google Gemini 1.5 Flash.

## ✨ Features
- **AI Content Analysis** — Gemini 1.5 Flash reasons about writing quality, emotional language, logical consistency, and claim specificity
- **News Cross-Reference** — Validates claims against real headlines from 60,000+ sources via NewsAPI.org
- **Source Credibility** — Domain database of 200+ known fake/satire/biased sites + HTTPS & domain age checks
- **Session History** — Last 5 analyses saved in the sidebar
- **Demo Mode** — Works without API keys (heuristics-only fallback)

## 🚀 Quick Start

### 1. Get Free API Keys

| API | Link | Free Tier |
|-----|------|-----------|
| Google Gemini | [aistudio.google.com](https://aistudio.google.com/app/apikey) | 1,500 req/day |
| NewsAPI.org | [newsapi.org/register](https://newsapi.org/register) | 100 req/day |

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Keys
```bash
copy .env.example .env
# Edit .env and add your keys
```

Or just paste them in the sidebar when the app opens.

### 4. Run
```bash
streamlit run app.py
```

## 📁 Project Structure
```
Fake News Detector/
├── app.py                  # Main Streamlit app
├── requirements.txt
├── .env.example            # Key template
├── .streamlit/config.toml  # Dark theme
├── src/
│   ├── analyzer.py         # 3-layer pipeline orchestrator
│   ├── gemini_client.py    # Gemini 1.5 Flash integration
│   ├── news_checker.py     # NewsAPI cross-reference
│   ├── source_checker.py   # Domain credibility scoring
│   └── utils.py            # Text extraction & helpers
└── data/
    └── known_sources.json  # 200+ known fake/satire/biased sites
```

## 🧪 How It Works

```
Article Text / URL
       │
       ▼
┌─────────────────────────────────────────┐
│  Layer 1: AI Analysis (45%)             │
│  Gemini 1.5 Flash — writing quality,    │
│  emotional language, logical reasoning  │
└─────────────────────────────────────────┘
       │
┌─────────────────────────────────────────┐
│  Layer 2: News Cross-Reference (30%)    │
│  NewsAPI.org — validates claims         │
│  against real trusted headlines         │
└─────────────────────────────────────────┘
       │
┌─────────────────────────────────────────┐
│  Layer 3: Source Credibility (25%)      │
│  Domain DB + HTTPS + WHOIS age check    │
└─────────────────────────────────────────┘
       │
       ▼
  Final Verdict + Score (0-100)
```

## 🌐 Deploy Free on Streamlit Cloud
1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo, set `app.py` as the main file
4. Add `GEMINI_API_KEY` and `NEWS_API_KEY` in the Secrets section
