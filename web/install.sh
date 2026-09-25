#!/bin/bash
# One-command setup — mirrors SwagatAI's install flow
set -e
echo "Setting up Livelihood Skilling Voice Assistant..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo ""
echo "NOTE: openai-whisper (and Vosk's WAV conversion) require ffmpeg:"
echo "  Ubuntu/Debian: sudo apt install ffmpeg"
echo "  Mac:           brew install ffmpeg"
echo ""

# --- Vosk fallback model (used automatically if Whisper fails to load/transcribe) ---
VOSK_DIR="models/vosk-model-small-en-us-0.15"
if [ ! -d "$VOSK_DIR" ]; then
  echo "Downloading Vosk fallback model (~40MB, one-time)..."
  mkdir -p models
  curl -L -o /tmp/vosk-model.zip "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
  unzip -q /tmp/vosk-model.zip -d models
  rm /tmp/vosk-model.zip
  echo "Vosk model ready at $VOSK_DIR"
else
  echo "Vosk model already present at $VOSK_DIR — skipping download."
fi

echo ""
echo "Setup complete. Run with: source venv/bin/activate && python run.py"
echo "Then check http://localhost:5000/api/stt_status to confirm Whisper/Vosk both loaded"
echo "BEFORE you rely on live mic input for the demo."
