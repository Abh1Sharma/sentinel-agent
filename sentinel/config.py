"""Shared clients and settings. Everything reads from .env so keys never live in code."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BRIEF_MODEL = os.getenv("SENTINEL_BRIEF_MODEL", "claude-opus-5-5")
GUARD_MODEL = os.getenv("SENTINEL_GUARD_MODEL", "claude-opus-5-5")
OPIK_PROJECT = os.getenv("OPIK_PROJECT_NAME", "sentinel")

# Replay mode serves every Nimble call from the on-disk cache. Use it on stage
# when the venue Wi-Fi dies: run everything once at home, then flip this on.
REPLAY = os.getenv("SENTINEL_REPLAY", "0") == "1"
CACHE_DIR = ROOT / ".cache"

# Fallback on refusal is a server-side beta on Opus 5.5.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@lru_cache
def anthropic_client():
    import anthropic
    from opik.integrations.anthropic import track_anthropic

    return track_anthropic(anthropic.Anthropic(), project_name=OPIK_PROJECT)


@lru_cache
def nimble_client():
    from nimble_python import Nimble

    # The SDK's own retries are off: web.py owns retry policy so it can honor
    # Retry-After and log each attempt to the trace.
    return Nimble(api_key=os.environ.get("NIMBLE_API_KEY", "replay-mode"), max_retries=0)


def configure_opik():
    """Point Opik at the cloud workspace if a key is present, else stay local-only."""
    import opik

    if os.getenv("OPIK_API_KEY"):
        opik.configure(
            api_key=os.environ["OPIK_API_KEY"],
            workspace=os.getenv("OPIK_WORKSPACE"),
            use_local=False,
            force=True,
            automatic_approvals=True,
            project_name=OPIK_PROJECT,
        )
    else:
        opik.set_tracing_active(False)
