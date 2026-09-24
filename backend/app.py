"""
app.py — Flask application for the AI-Driven Voice Assistant for Livelihood
Mapping & Skilling Recommendations (SIH26097).

Built on the same stack as SwagatAI (Flask + SQLite + gTTS/Whisper), adapted
for the PM-AJAY beneficiary skilling-recommendation flow.
"""
import os
import sys
from flask import Flask, request, jsonify, send_file, send_from_directory

sys.path.insert(0, os.path.dirname(__file__))
import database
import stt
import tts
import recommender

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

database.init_db()

# In-memory conversation state per session (fine for a single-demo prototype)
SESSIONS = {}


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/dashboard")
def dashboard():
    return send_from_directory(FRONTEND_DIR, "dashboard.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "trades_loaded": len(recommender.load_trades())})


@app.route("/api/questions")
def get_questions():
    lang = request.args.get("lang", "en")
    return jsonify({"questions": recommender.QUESTIONS, "language": lang})


@app.route("/api/session/start", methods=["POST"])
def start_session():
    import uuid
    session_id = uuid.uuid4().hex[:10]
    lang = (request.json or {}).get("language", "en")
    SESSIONS[session_id] = {"language": lang, "qa": [], "answers": {}}
    return jsonify({"session_id": session_id, "questions": recommender.QUESTIONS})


@app.route("/transcribe", methods=["POST"])
def transcribe():
    """
    Accepts either:
    - multipart/form-data with 'audio' file (browser MediaRecorder blob), or
    - JSON {"text": "..."} as a typed-text fallback (used if mic/Whisper fails on stage)
    Also expects 'question_id' and 'session_id' form/json fields.
    """
    if "audio" in request.files:
        lang = request.form.get("language", "en")
        question_id = request.form.get("question_id")
        session_id = request.form.get("session_id")
        try:
            text = stt.transcribe_audio_file(request.files["audio"], language=lang)
        except Exception as e:
            return jsonify({"error": str(e), "fallback": "use_text_input"}), 200
    else:
        payload = request.get_json(force=True)
        text = payload.get("text", "")
        question_id = payload.get("question_id")
        session_id = payload.get("session_id")

    extracted = recommender.extract_field(question_id, text)

    if session_id in SESSIONS:
        q_text = next((q["text"] for q in recommender.QUESTIONS if q["id"] == question_id), question_id)
        SESSIONS[session_id]["qa"].append({"question": q_text, "answer_raw": text, "answer_extracted": extracted})
        SESSIONS[session_id]["answers"][question_id] = extracted

    return jsonify({"transcript": text, "extracted_value": extracted, "question_id": question_id})


@app.route("/api/recommend", methods=["POST"])
def recommend():
    payload = request.get_json(force=True)
    session_id = payload.get("session_id")

    if session_id in SESSIONS:
        profile = SESSIONS[session_id]["answers"]
        qa_pairs = SESSIONS[session_id]["qa"]
        language = SESSIONS[session_id]["language"]
    else:
        profile = payload.get("profile", {})
        qa_pairs = []
        language = payload.get("language", "en")

    recs = recommender.recommend_trades(profile, top_n=3)
    log_id = database.log_session(language, qa_pairs, profile, recs)

    return jsonify({"profile": profile, "recommendations": recs, "session_log_id": log_id})


@app.route("/speak", methods=["POST"])
def speak():
    payload = request.get_json(force=True)
    text = payload.get("text", "")
    lang = payload.get("language", "en")
    if not text:
        return jsonify({"error": "no text provided"}), 400
    try:
        audio_path = tts.synthesize_speech(text, lang=lang)
        mimetype = "audio/mpeg" if audio_path.endswith(".mp3") else "audio/wav"
        return send_file(audio_path, mimetype=mimetype)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboard/sessions")
def dashboard_sessions():
    return jsonify(database.get_all_sessions())


@app.route("/api/dashboard/trade_counts")
def dashboard_trade_counts():
    return jsonify(database.get_trade_recommendation_counts())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
