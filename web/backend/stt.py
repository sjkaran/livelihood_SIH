"""
stt.py — Speech-to-Text pipeline.

Primary: OpenAI Whisper (small/base model) — matches SwagatAI's voice engine choice.
Fallback: if whisper isn't installed / too slow / fails to load, we degrade gracefully
so the demo never dies on stage — the frontend can also just send typed text via
the same /transcribe contract (see app.py).
"""
import os
import tempfile

_whisper_model = None
_WHISPER_AVAILABLE = True

try:
    import whisper
except ImportError:
    _WHISPER_AVAILABLE = False


def _load_model():
    global _whisper_model
    if _whisper_model is None and _WHISPER_AVAILABLE:
        # "base" balances speed vs accuracy for a live demo on a laptop CPU
        _whisper_model = whisper.load_model("base")
    return _whisper_model


def transcribe_audio_file(file_storage, language="en"):
    """
    file_storage: werkzeug FileStorage object from the Flask request (browser MediaRecorder blob)
    language: 'en' or 'hi' (ISO code passed to whisper for better accuracy)
    Returns: transcribed text (str)
    """
    if not _WHISPER_AVAILABLE:
        raise RuntimeError(
            "Whisper not installed. Run: pip install openai-whisper "
            "(or use the text-input fallback in the UI)."
        )

    # Save uploaded blob to a temp file — whisper needs a filesystem path
    suffix = os.path.splitext(file_storage.filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file_storage.save(tmp.name)
        tmp_path = tmp.name

    try:
        model = _load_model()
        result = model.transcribe(tmp_path, language=language, fp16=False)
        return result.get("text", "").strip()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
