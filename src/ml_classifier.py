"""
HuggingFace Inference API — RoBERTa fine-tuned on fake news datasets.
Model: hamzab/roberta-fake-news-classification
"""

import os
import requests

HF_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
HF_MODEL_URL = "https://api-inference.huggingface.co/models/hamzab/roberta-fake-news-classification"
HF_FALLBACK = "https://api-inference.huggingface.co/models/GonzaloA/fake_news_detector"


def classify_with_bert(article_text: str) -> dict:
    api_key = os.getenv("HUGGINGFACE_API_KEY", "")
    result = {
        "score": 50,
        "fake_probability": 0.5,
        "real_probability": 0.5,
        "label": "Unclassified",
        "model_used": "",
        "api_available": bool(api_key and api_key not in ("", "your_key_here")),
        "signals": [],
        "error": None,
    }

    if not result["api_available"]:
        result["error"] = "HuggingFace API key not configured."
        result["signals"].append({
            "icon": "🔑", "label": "ML Classifier Not Configured",
            "detail": "Add HUGGINGFACE_API_KEY to .env for RoBERTa-based classification.",
            "positive": None,
        })
        return result

    headers = {"Authorization": f"Bearer {api_key}"}
    text_input = article_text[:512]

    raw = None
    for url in [HF_MODEL_URL, HF_FALLBACK]:
        try:
            resp = requests.post(url, headers=headers, json={"inputs": text_input}, timeout=25)
            if resp.status_code == 200:
                raw = resp.json()
                result["model_used"] = url.split("/models/")[-1]
                break
            if resp.status_code == 503:
                continue  # model loading
        except Exception:
            continue

    if not raw:
        result["error"] = "HuggingFace models unavailable (may be loading — retry in ~30s)."
        result["signals"].append({
            "icon": "⚠️", "label": "ML Model Loading",
            "detail": "Free tier models need ~20s to warm up. Try again shortly.",
            "positive": None,
        })
        return result

    try:
        preds = raw[0] if isinstance(raw[0], list) else raw
        fake_prob, real_prob = 0.5, 0.5
        for pred in preds:
            lbl = pred.get("label", "").upper()
            sc = float(pred.get("score", 0.5))
            if any(x in lbl for x in ["FAKE", "0", "LABEL_0"]):
                fake_prob = sc
            elif any(x in lbl for x in ["REAL", "1", "LABEL_1"]):
                real_prob = sc

        total = fake_prob + real_prob
        if total > 0:
            fake_prob /= total
            real_prob /= total

        result.update({
            "fake_probability": round(fake_prob, 3),
            "real_probability": round(real_prob, 3),
            "score": round(real_prob * 100),
        })

        if real_prob >= 0.72:
            result["label"] = "Likely Real"
            result["signals"].append({
                "icon": "✅",
                "label": f"ML: Likely Real ({real_prob:.0%} conf.)",
                "detail": f"RoBERTa trained on LIAR/FakeNewsNet classifies this as real.",
                "positive": True,
            })
        elif fake_prob >= 0.72:
            result["label"] = "Likely Fake"
            result["signals"].append({
                "icon": "🚫",
                "label": f"ML: Likely Fake ({fake_prob:.0%} conf.)",
                "detail": f"RoBERTa trained on LIAR/FakeNewsNet classifies this as fake.",
                "positive": False,
            })
        else:
            result["label"] = "Uncertain"
            result["signals"].append({
                "icon": "🟡",
                "label": f"ML: Uncertain (Real {real_prob:.0%} / Fake {fake_prob:.0%})",
                "detail": "Low confidence — text features are ambiguous.",
                "positive": None,
            })
    except Exception as e:
        result["error"] = f"Parse error: {e}"

    return result
