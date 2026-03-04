import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "startup_radar.db"
DATA_DIR = BASE_DIR / "data"


def get_api_key(key_name: str) -> str:
    """Retrieve an API key from Streamlit secrets first, then environment variables."""
    try:
        import streamlit as st
        if key_name in st.secrets:
            return st.secrets[key_name]
    except (ImportError, AttributeError, FileNotFoundError):
        pass
    return os.getenv(key_name, "")


OPENAI_API_KEY = get_api_key("OPENAI_API_KEY")
ANTHROPIC_API_KEY = get_api_key("ANTHROPIC_API_KEY")
TAVILY_API_KEY = get_api_key("TAVILY_API_KEY")

DEMO_MODE = not (OPENAI_API_KEY or ANTHROPIC_API_KEY)

DEFAULT_THESIS_NAME = "Growth Equity Core"

PIPELINE_STAGES = ["new", "screening", "deep_dive", "ic_review", "pass", "monitor"]
TIERS = {"hot": (8.0, 10.0), "warm": (6.0, 7.99), "monitor": (4.0, 5.99), "pass": (0, 3.99)}

TIER_COLORS = {
    "hot": "#ef4444",
    "warm": "#f59e0b",
    "monitor": "#3b82f6",
    "pass": "#6b7280",
}

STAGE_LABELS = {
    "new": "New",
    "screening": "Screening",
    "deep_dive": "Deep Dive",
    "ic_review": "IC Review",
    "pass": "Pass",
    "monitor": "Monitor",
}
