"""
stt.py — Speech-to-Text pipeline.

Primary: OpenAI Whisper (configurable model size, default "small" for materially
better accuracy than "base" on accented/rural Indian English — see WHISPER_MODEL_SIZE).
Fallback: Vosk (fully offline, no model download at runtime) if Whisper is not
installed, fails to load, or throws during transcription.

Both engines are PRELOADED at import time via preload_models(), which app.py calls
once at server startup — a broken/missing model shows up in your terminal before
you're on stage, not as a silent mid-demo failure.

Accuracy measures applied (beyond just "run whisper"):
  1. Domain vocabulary priming — an initial_prompt seeded with trade names and
     phrasing from this project's own questions, which measurably reduces Whisper
     mis-hearing domain terms (e.g. "NSQF", "tailoring", "PM-AJAY") as something else.
  2. temperature=0, condition_on_previous_text=False — short, isolated Q&A clips
     are exactly the case where Whisper's default settings are prone to hallucinating
     repeated/invented text; these two settings suppress that.
  3. Audio normalization — every clip is converted to 16kHz mono PCM and volume-
     normalized before transcription, so a quiet phone/laptop mic doesn't tank
     accuracy the way a raw, low-gain recording would.
  4. Confidence flagging — Whisper's own no_speech_prob / avg_logprob per segment
     are used to mark a transcript "low_confidence" instead of silently trusting it,
     so the frontend can prompt "didn't catch that clearly, try again" rather than
     feeding a bad guess into the recommender.
"""
import os
import json
import wave
import tempfile

# ---------------------------------------------------------------------------
# Engine availability + loaded model handles
# ---------------------------------------------------------------------------
_whisper_model = None
_whisper_error = None
_WHISPER_AVAILABLE = True

_vosk_model = None
_vosk_error = None
_VOSK_AVAILABLE = True

# "small" gives a noticeably better word-error-rate than "base" on accented speech
# and non-studio mics, at a real but tolerable CPU cost. Drop to "base" via env var
# if a laptop is too slow for live demo latency.
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")

# You must download a Vosk model folder yourself (vosk does not ship model weights
# via pip). Small English model (~40MB): https://alphacephei.com/vosk/models
VOSK_MODEL_PATH = os.environ.get("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15")

# Domain vocabulary hint fed to Whisper as an initial_prompt. This is the single
# highest-leverage accuracy lever available without training anything: Whisper
# biases its decoding toward words/phrases that appear in the prompt.
DOMAIN_PROMPT = (
    "PM-AJAY, NSQF, skill training, tailoring, electrician, plumbing, beautician, "
    "driving, mobile repair, computer basics, food processing, handicrafts, "
    "agriculture, welding, carpentry, masonry, dairy farming, education level, "
    "self employment, wage employment, village, mobility."
)

try:
    import whisper
except ImportError:
    _WHISPER_AVAILABLE = False
    _whisper_error = "openai-whisper not installed (pip install openai-whisper)"

try:
    import vosk
    vosk.SetLogLevel(-1)  # silence vosk's own console spam
except ImportError:
    _VOSK_AVAILABLE = False
    _vosk_error = "vosk not installed (pip install vosk)"

try:
    from pydub import AudioSegment
    from pydub.effects import normalize as pydub_normalize
    _PYDUB_AVAILABLE = True
except ImportError:
    _PYDUB_AVAILABLE = False


def preload_models():
    """
    Load both engines once, eagerly, at server startup. Call this from app.py
    right after the Flask app is created — NOT lazily on first request. That
    way a missing/broken model surfaces as a clear log line before you ever
    walk on stage, instead of as a mystery failure during the live demo.
    """
    global _whisper_model, _whisper_error, _vosk_model, _vosk_error

    if _WHISPER_AVAILABLE:
        try:
            print(f"[stt] Loading Whisper '{WHISPER_MODEL_SIZE}' model...")
            _whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
            print("[stt] Whisper ready.")
        except Exception as e:
            _whisper_error = f"Whisper failed to load: {e}"
            print(f"[stt] WARNING: {_whisper_error}")

    if _VOSK_AVAILABLE:
        if os.path.isdir(VOSK_MODEL_PATH):
            try:
                print(f"[stt] Loading Vosk model from {VOSK_MODEL_PATH} ...")
                _vosk_model = vosk.Model(VOSK_MODEL_PATH)
                print("[stt] Vosk ready (fallback engine).")
            except Exception as e:
                _vosk_error = f"Vosk failed to load: {e}"
                print(f"[stt] WARNING: {_vosk_error}")
        else:
            _vosk_error = (
                f"Vosk model folder not found at '{VOSK_MODEL_PATH}'. Download one from "
                "https://alphacephei.com/vosk/models, unzip it, and set VOSK_MODEL_PATH."
            )
            print(f"[stt] NOTE: {_vosk_error} (Vosk fallback disabled until this is fixed)")

    status = get_stt_status()
    if not status["whisper_ready"] and not status["vosk_ready"]:
        print(
            "[stt] *** NEITHER Whisper nor Vosk is ready. Voice input will NOT work — "
            "only the text-fallback input will function. Fix this before your demo. ***"
        )
    return status


def get_stt_status():
    return {
        "whisper_ready": _whisper_model is not None,
        "vosk_ready": _vosk_model is not None,
        "whisper_model_size": WHISPER_MODEL_SIZE,
        "whisper_error": _whisper_error,
        "vosk_error": _vosk_error,
    }


# ---------------------------------------------------------------------------
# Audio normalization: browser sends webm/ogg opus blobs. We convert to a
# clean 16kHz mono WAV with volume normalization ONCE, then feed that same
# clean audio to whichever engine handles the request. This helps Whisper's
# accuracy too, not just Vosk's compatibility — a normalized, resampled clip
# is closer to what both models were trained/tuned against.
# ---------------------------------------------------------------------------
def _to_wav_16k_mono(src_path):
    if not _PYDUB_AVAILABLE:
        return None
    try:
        audio = AudioSegment.from_file(src_path)
        audio = pydub_normalize(audio)  # even out quiet/loud mic input
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        out_path = src_path + ".16k.wav"
        audio.export(out_path, format="wav")
        return out_path
    except Exception as e:
        print(f"[stt] Audio conversion to WAV failed: {e}")
        return None


def _transcribe_with_whisper(path, language):
    result = _whisper_model.transcribe(
        path,
        language=language,
        fp16=False,
        temperature=0,                      # deterministic, less prone to hallucinated riffing
        condition_on_previous_text=False,    # each answer is an isolated clip, not a continuous stream
        initial_prompt=DOMAIN_PROMPT,        # bias decoding toward this project's vocabulary
    )
    text = result.get("text", "").strip()

    # Confidence check: average no_speech_prob / avg_logprob across segments.
    # A high no_speech_prob or very negative avg_logprob usually means Whisper
    # transcribed silence/noise into something plausible-looking but wrong.
    segments = result.get("segments") or []
    low_confidence = False
    if segments:
        avg_no_speech = sum(s.get("no_speech_prob", 0) for s in segments) / len(segments)
        avg_logprob = sum(s.get("avg_logprob", 0) for s in segments) / len(segments)
        if avg_no_speech > 0.6 or avg_logprob < -1.0:
            low_confidence = True
    elif not text:
        low_confidence = True

    return text, low_confidence


def _transcribe_with_vosk(wav_path):
    wf = wave.open(wav_path, "rb")
    rec = vosk.KaldiRecognizer(_vosk_model, wf.getframerate())
    rec.SetWords(False)
    text_parts = []
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            text_parts.append(json.loads(rec.Result()).get("text", ""))
    text_parts.append(json.loads(rec.FinalResult()).get("text", ""))
    wf.close()
    return " ".join(p for p in text_parts if p).strip()


def transcribe_audio_file(file_storage, language="en"):
    """
    file_storage: werkzeug FileStorage object from the Flask request (browser MediaRecorder blob)
    language: 'en' or 'hi' (ISO code; passed to Whisper — Vosk's small-en model is
              English-only, so the Vosk fallback will be weak on Hindi audio; that's
              an inherent limit of a free offline Hindi model, not a bug here).
    Returns: (text, engine_used, low_confidence)
      engine_used: "whisper" or "vosk"
      low_confidence: True if the transcript looks unreliable and the UI should
                       prompt the beneficiary to try again rather than proceed.
    Raises RuntimeError only if BOTH engines are unavailable or BOTH fail.
    """
    suffix = os.path.splitext(file_storage.filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file_storage.save(tmp.name)
        tmp_path = tmp.name

    wav_path = None
    errors = []
    try:
        # Normalize once, up front — improves both engines' accuracy/compatibility.
        wav_path = _to_wav_16k_mono(tmp_path)
        whisper_input = wav_path or tmp_path

        # --- Try Whisper first (better accuracy) ---
        if _whisper_model is not None:
            try:
                text, low_conf = _transcribe_with_whisper(whisper_input, language)
                if text:
                    return text, "whisper", low_conf
                errors.append("Whisper returned empty transcript")
            except Exception as e:
                errors.append(f"Whisper error: {e}")

        # --- Fall back to Vosk (needs the normalized WAV) ---
        if _vosk_model is not None:
            if wav_path is None:
                errors.append("Could not convert audio for Vosk (is ffmpeg installed?)")
            else:
                try:
                    text = _transcribe_with_vosk(wav_path)
                    if text:
                        return text, "vosk", False
                    errors.append("Vosk returned empty transcript")
                except Exception as e:
                    errors.append(f"Vosk error: {e}")

        if _whisper_model is None and _vosk_model is None:
            raise RuntimeError(
                "No STT engine is ready. "
                f"Whisper: {_whisper_error or 'not loaded'}. "
                f"Vosk: {_vosk_error or 'not loaded'}. "
                "Use the text-input fallback in the UI, or fix setup and restart the server."
            )
        raise RuntimeError("Both STT engines failed on this audio clip: " + "; ".join(errors))
    finally:
        for p in (tmp_path, wav_path):
            if p:
                try:
                    os.remove(p)
                except OSError:
                    pass
