"""
recommender.py — Answer extraction + NSQF trade matching/recommendation engine.

Two responsibilities:
1. extract_field(question_id, raw_answer_text) -> structured value
   (simple keyword/slot extraction — no heavy NLP needed for the demo)
2. recommend_trades(profile) -> top-3 scored trades from trades.csv
   (weighted rule scoring; a cosine-similarity variant is provided too)
"""
import os
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

TRADES_CSV = os.path.join(os.path.dirname(__file__), "trades.csv")

EDUCATION_RANK = {
    "no formal education": 0, "illiterate": 0,
    "5th pass": 1, "below 5th": 1, "primary": 1,
    "8th pass": 2, "middle": 2,
    "10th pass": 3, "matric": 3, "secondary": 3,
    "12th pass": 4, "senior secondary": 4,
    "graduate": 5, "degree": 5,
}

INTEREST_KEYWORDS = {
    "tailoring/stitching": ["tailor", "stitch", "sewing", "cloth", "fashion", "sew"],
    "electrical": ["electric", "wiring", "current", "fan", "switch"],
    "plumbing": ["plumb", "pipe", "tap", "water leak"],
    "beauty": ["beauty", "salon", "makeup", "parlour", "parlor", "hair"],
    "driving": ["driv", "vehicle", "car", "taxi", "auto"],
    "mobile/electronics repair": ["mobile", "phone repair", "electronic", "gadget"],
    "computer/it": ["computer", "laptop", "typing", "internet", "data entry"],
    "food processing": ["cook", "food", "pickle", "kitchen", "catering"],
    "handicrafts": ["craft", "weav", "handloom", "art", "handmade"],
    "agriculture": ["farm", "agricultur", "crop", "field", "cattle"],
    "construction": ["construct", "mason", "build", "labour", "labor"],
    "welding": ["weld", "metal", "fabricat"],
    "retail/sales": ["shop", "sales", "retail", "store", "business"],
    "healthcare": ["health", "nurse", "patient", "care", "hospital"],
}

EMPLOYMENT_KEYWORDS = {
    # order matters: check the more specific "wage job" phrasing first so
    # "I want a job, not my own business" doesn't falsely match "own business"
    "wage-employment": ["job", "salary", "work for", "company", "naukri", "employ"],
    "self-employment": ["own business", "start my own", "shop of my own", "entrepreneur", "self employ"],
}

MOBILITY_KEYWORDS = {
    # negations / explicit "can't travel" phrasing checked first
    "local": ["can't travel", "cant travel", "cannot travel", "no travel", "not travel",
              "at home", "near my", "close to home"],
    "travel": ["travel", "outside", "anywhere", "any city", "relocate", "move away"],
    # generic locality words checked last so they don't shadow "willing to travel" answers
    "local_fallback": ["local", "village", "near"],
}

QUESTIONS = [
    {"id": "education", "text": "What is your highest education level?"},
    {"id": "occupation", "text": "What is your current occupation or your family's occupation?"},
    {"id": "interest", "text": "What kind of work interests you the most?"},
    {"id": "employment_pref", "text": "Are you looking for a job, or would you like to start your own business?"},
    {"id": "mobility", "text": "Can you travel outside your village for training, or do you need something local?"},
]


def _match_keywords(text, keyword_map, default="unspecified"):
    text_l = (text or "").lower()
    for label, keywords in keyword_map.items():
        if any(k in text_l for k in keywords):
            return label
    return default


def extract_field(question_id, raw_answer_text):
    """Keyword/slot-based extraction — deliberately simple & robust for a live demo."""
    text_l = (raw_answer_text or "").lower()

    if question_id == "education":
        for label in EDUCATION_RANK:
            if label in text_l:
                return label
        return "8th pass"  # safe default if unclear

    if question_id == "occupation":
        return _match_keywords(text_l, INTEREST_KEYWORDS, default=text_l[:40] or "unspecified")

    if question_id == "interest":
        return _match_keywords(text_l, INTEREST_KEYWORDS, default=text_l[:40] or "unspecified")

    if question_id == "employment_pref":
        return _match_keywords(text_l, EMPLOYMENT_KEYWORDS, default="wage-employment")

    if question_id == "mobility":
        result = _match_keywords(text_l, MOBILITY_KEYWORDS, default="local")
        return "local" if result == "local_fallback" else result

    return raw_answer_text


def load_trades():
    return pd.read_csv(TRADES_CSV)


def recommend_trades(profile, top_n=3, method="weighted"):
    """
    profile: dict with keys education, occupation, interest, employment_pref, mobility
    method: 'weighted' (rule scoring, default) or 'cosine' (TF-IDF similarity)
    Returns list of dicts: trade_id, trade_name, score, description
    """
    df = load_trades()
    if method == "cosine":
        return _recommend_cosine(df, profile, top_n)
    return _recommend_weighted(df, profile, top_n)


def _recommend_weighted(df, profile, top_n):
    edu_level = EDUCATION_RANK.get(profile.get("education", "8th pass"), 2)
    interest = profile.get("interest", "unspecified")
    occupation = profile.get("occupation", "unspecified")
    employment_pref = profile.get("employment_pref", "wage-employment")
    mobility = profile.get("mobility", "local")

    scored = []
    for _, row in df.iterrows():
        score = 0.0
        # Education fit: trade should require <= user's education level (else unreachable)
        trade_edu = EDUCATION_RANK.get(str(row["min_education"]).strip().lower(), 2)
        if trade_edu <= edu_level:
            score += 3.0
            score -= (edu_level - trade_edu) * 0.3  # slight penalty for being overqualified
        else:
            score -= 2.0  # trade needs more education than user has

        # Interest match against interests_tags
        tags = str(row["interests_tags"]).lower().split("|")
        if interest != "unspecified" and any(interest.split("/")[0] in t or t in interest for t in tags):
            score += 4.0
        if occupation != "unspecified" and any(occupation.split("/")[0] in t or t in occupation for t in tags):
            score += 2.0

        # Employment type match
        if str(row["employment_type"]).strip().lower() == employment_pref:
            score += 2.5

        # Mobility match
        if str(row["mobility_requirement"]).strip().lower() == mobility:
            score += 1.5

        scored.append({
            "trade_id": row["trade_id"],
            "trade_name": row["trade_name"],
            "category": row["category"],
            "score": round(score, 2),
            "description": row["description"],
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


def _recommend_cosine(df, profile, top_n):
    profile_text = " ".join([
        str(profile.get("education", "")),
        str(profile.get("occupation", "")),
        str(profile.get("interest", "")),
        str(profile.get("employment_pref", "")),
        str(profile.get("mobility", "")),
    ])
    trade_texts = (
        df["interests_tags"].str.replace("|", " ", regex=False) + " " +
        df["employment_type"] + " " + df["mobility_requirement"] + " " + df["min_education"]
    )
    corpus = list(trade_texts) + [profile_text]
    vec = TfidfVectorizer()
    tfidf = vec.fit_transform(corpus)
    sims = cosine_similarity(tfidf[-1], tfidf[:-1]).flatten()

    df = df.copy()
    df["score"] = [round(float(s) * 10, 2) for s in sims]
    df = df.sort_values("score", ascending=False)

    return [
        {
            "trade_id": r["trade_id"], "trade_name": r["trade_name"],
            "category": r["category"], "score": r["score"], "description": r["description"],
        }
        for _, r in df.head(top_n).iterrows()
    ]
