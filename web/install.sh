#!/bin/bash
# One-command setup — mirrors SwagatAI's install flow
set -e
echo "Setting up Livelihood Skilling Voice Assistant..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo ""
echo "NOTE: openai-whisper also requires ffmpeg on your system:"
echo "  Ubuntu/Debian: sudo apt install ffmpeg"
echo "  Mac:           brew install ffmpeg"
echo ""
echo "Setup complete. Run with: source venv/bin/activate && python run.py"
