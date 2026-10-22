import os
from pathlib import Path

from dotenv import load_dotenv

# Load keys before any module imports opik, so tracing config is settled up front.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
os.environ.setdefault("OPIK_PROJECT_NAME", "sentinel")
if not os.getenv("OPIK_API_KEY"):
    os.environ.setdefault("OPIK_TRACK_DISABLE", "true")
