"""run.py — Launch entrypoint. Usage: python run.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🎙️  Livelihood Skilling Voice Assistant running at http://localhost:{port}")
    print(f"📊  Officer dashboard at http://localhost:{port}/dashboard\n")
    app.run(host="0.0.0.0", port=port, debug=True)
