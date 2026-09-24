"""
tts.py — Text-to-Speech pipeline.

Primary: gTTS (Google TTS, needs internet) — simplest to set up, per project brief.
Fallback: pyttsx3 (fully offline) if gTTS fails (no internet during demo).
"""
import os
import uuid
import tempfile

AUDIO_DIR = os.path.join(tempfile.gettempdir(), "livelihood_tts_cache")
os.makedirs(AUDIO_DIR, exist_ok=True)


def synthesize_speech(text, lang="en"):
    """
    Returns the filesystem path to a generated mp3/wav file.
    Tries gTTS first, falls back to pyttsx3 (offline, saves wav) on failure.
    """
    out_path = os.path.join(AUDIO_DIR, f"{uuid.uuid4().hex}.mp3")

    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang)
        tts.save(out_path)
        return out_path
    except Exception:
        # Offline fallback
        try:
            import pyttsx3
            wav_path = out_path.replace(".mp3", ".wav")
            engine = pyttsx3.init()
            engine.save_to_file(text, wav_path)
            engine.runAndWait()
            return wav_path
        except Exception as e:
            raise RuntimeError(f"Both gTTS and pyttsx3 failed: {e}")
