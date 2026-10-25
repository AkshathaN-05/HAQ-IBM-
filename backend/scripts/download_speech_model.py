"""Download the offline speech-to-text model once, so voice notes work without internet later.

Usage (from the backend folder):  .venv\\Scripts\\python scripts\\download_speech_model.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_settings  # noqa: E402
from app.evidence_files import load_stt_model, stt_available  # noqa: E402


def main() -> None:
    name = load_settings().stt_model
    if name == "off":
        print("STT_MODEL is off. Nothing to download.")
        return
    if not stt_available():
        sys.exit("faster-whisper is not installed. Run: .venv\\Scripts\\pip install faster-whisper")
    print(f"Downloading the '{name}' speech model (one time only)...")
    load_stt_model(name)
    print("Done. Voice notes will now be turned into text, even without internet.")


if __name__ == "__main__":
    main()
