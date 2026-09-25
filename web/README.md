# 🎙️ AI-Driven Voice Assistant for Livelihood Mapping & Skilling Recommendations
### Smart India Hackathon 2026 — Problem Statement SIH26097
### Ministry of Social Justice and Empowerment · PM-AJAY Scheme

Built on the same lightweight stack as **SwagatAI** (Flask + SQLite + gTTS/Whisper +
vanilla JS), adapted for matching PM-AJAY beneficiaries to NSQF-aligned skill trades
through a fully spoken interview.

---

## Quick Start

```bash
cd livelihood_SIH/web
bash install.sh
source venv/bin/activate
python run.py
```

Open `http://localhost:5000` for the beneficiary voice interview.
Open `http://localhost:5000/dashboard` for the officer-facing dashboard.

> **No mic / no internet on stage?** Every question has a text-input fallback right next
> to the record button, and TTS falls back from gTTS → pyttsx3 (fully offline) automatically.

---

## What This Prototype Does (Working End-to-End)

1. **Voice input** — browser records the beneficiary's spoken answer (`MediaRecorder` API)
2. **Speech-to-text** — Whisper (`base` model) transcribes the answer
3. **Structured extraction** — keyword/slot extraction pulls out education, occupation,
   interest, employment preference, and mobility from free-form speech
4. **NSQF matching** — a weighted rule-based scoring engine (also has a TF-IDF cosine
   similarity mode) matches the profile against 18 mock NSQF trades and returns the top 3
5. **Voice output** — the recommendation is spoken back via gTTS/pyttsx3
6. **Officer dashboard** — every session (Q&A, extracted profile, recommendations) is
   logged to SQLite and shown as a table + a bar chart of most-recommended trades

---

## Project Structure

```
livelihood_SIH/web/
├── run.py                  ← Launch server (python run.py)
├── install.sh              ← One-command setup script
├── requirements.txt
├── frontend/
│   ├── index.html           ← Beneficiary voice interview UI
│   ├── dashboard.html        ← Officer dashboard (table + chart.js)
│   └── script.js
├── backend/
│   ├── app.py               ← Flask routes
│   ├── stt.py                ← Whisper speech-to-text
│   ├── tts.py                ← gTTS / pyttsx3 text-to-speech
│   ├── recommender.py        ← Extraction + NSQF matching engine
│   ├── database.py           ← SQLite session logging
│   └── trades.csv            ← Mock catalog of 18 NSQF trades
└── data/
    └── sessions.db           ← SQLite database (auto-created)
```

---

## REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Server health + trade catalog count |
| GET | `/api/questions?lang=en` | Get the fixed 5-question flow |
| POST | `/api/session/start` | Start a new beneficiary session |
| POST | `/transcribe` | Send audio blob (or `{"text":...}` fallback) → transcript + extracted field |
| POST | `/api/recommend` | Get top-3 trade recommendations for a session, logs to DB |
| POST | `/speak` | Get spoken audio (mp3/wav) of any text |
| GET | `/api/dashboard/sessions` | All logged sessions (for dashboard table) |
| GET | `/api/dashboard/trade_counts` | Aggregated recommendation counts (for chart) |

---

## The Fixed 5-Question Flow

1. What is your highest education level?
2. What is your current occupation or your family's occupation?
3. What kind of work interests you the most?
4. Are you looking for a job, or would you like to start your own business?
5. Can you travel outside your village for training, or do you need something local?

## Recommendation Logic

Weighted rule scoring across four factors per trade:
- **Education fit** (trade's `min_education` ≤ beneficiary's level)
- **Interest/occupation match** against each trade's tag list
- **Employment-type match** (self-employment vs. wage-employment)
- **Mobility match** (local-only vs. willing to travel)

A TF-IDF cosine-similarity alternative (`recommender.recommend_trades(profile, method="cosine")`)
is also implemented to show judges an ML-based approach is available, without requiring
a trained model.

---

## Built With

- **Python 3.11+** · Flask · SQLite
- **Voice**: OpenAI Whisper (STT) · gTTS with pyttsx3 offline fallback (TTS) · browser `MediaRecorder` API
- **Matching**: pandas + scikit-learn (TF-IDF / cosine similarity) + weighted rule scoring
- **Frontend**: Vanilla HTML/CSS/JS · Chart.js (dashboard)

---

## Scope Notes for Judges — What's Mocked & What's Future Roadmap

**Mocked for tonight's prototype:**
- 18-row NSQF trade catalog (`trades.csv`) — a real deployment would pull from the
  live NSQF/Skill India database via API
- Keyword/slot-based answer extraction — a real deployment could use an LLM for more
  robust free-speech understanding across dialects
- Single-officer, localhost dashboard, no authentication

**Future roadmap (not built tonight, by design — see PROJECT_BRIEF):**
- Real IVR/phone integration (Twilio or similar) so beneficiaries can call in on any
  basic phone — no smartphone or app required
- WhatsApp Business API integration for a text+voice hybrid channel
- Multiple simultaneous regional languages/dialects (Odia, and others) with dialect-aware STT
- A trained NLU/intent model (upgrading past keyword extraction) fine-tuned on rural
  Indian speech patterns
- Full authentication + role-based access for officers vs. beneficiaries
- Cloud deployment with autoscaling for state-wide rollout
- Live integration with the official NSQF trade database and PM-AJAY beneficiary records

---

## Suggested Live Demo Script

1. Open `/`, select language, click **Start Beneficiary Interview**
2. Answer the 5 questions by voice (or type, as a safety net) — e.g. a persona:
   *"10th pass, my family does farming, I'm interested in electrical work, I want a job,
   I can travel for training"*
3. Show the transcript + extracted structured value appearing after each answer
4. After Q5, show the top-3 recommended trades with match scores
5. Click **Play Recommendation Aloud** to demonstrate spoken output
6. Switch to `/dashboard` to show the logged session, profile summary, and the
   trade-recommendation bar chart updating live
7. Close with the scope-notes slide (IVR/WhatsApp/multi-language future roadmap)

Prepare 2–3 personas in advance (see step 2) so the demo doesn't depend on unpredictable
live audio — this is explicitly recommended in the project brief.
