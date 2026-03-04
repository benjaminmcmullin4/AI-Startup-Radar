"""Configuration constants, color palette, and settings."""

from __future__ import annotations

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "data" / "startup_radar.db"
DATA_DIR = PROJECT_ROOT / "data"
EXAMPLES_DIR = PROJECT_ROOT / "examples"

# ── Branding ──────────────────────────────────────────────────────────
FIRM_NAME = "Growth Equity Radar"
APP_TITLE = "Deal Sourcing & Screening"
APP_SUBTITLE = "AI-powered startup pipeline management for growth equity"

# ── Design System ──────────────────────────────────────────────────────
COLORS = {
    "navy": "#0A0A0A",
    "steel_blue": "#333333",
    "teal": "#1ABC9C",
    "red_accent": "#E74C3C",
    "gold_accent": "#D4A338",
    "bg": "#FAFBFC",
    "text": "#1A1A1A",
    "muted": "#777777",
    "light_gray": "#ECF0F1",
    "white": "#FFFFFF",
}

FONT = "Inter"

TIER_COLORS = {
    "hot": "#E74C3C",
    "warm": "#D4A338",
    "monitor": "#1ABC9C",
    "pass": "#777777",
}

# ── LLM Settings ───────────────────────────────────────────────────────
DEFAULT_MODEL = "claude-sonnet-4-20250514"

# ── Pipeline ───────────────────────────────────────────────────────────
PIPELINE_STAGES = ["new", "screening", "deep_dive", "ic_review", "pass", "monitor"]
TIERS = {"hot": (8.0, 10.0), "warm": (6.0, 7.99), "monitor": (4.0, 5.99), "pass": (0, 3.99)}

STAGE_LABELS = {
    "new": "New",
    "screening": "Screening",
    "deep_dive": "Deep Dive",
    "ic_review": "IC Review",
    "pass": "Pass",
    "monitor": "Monitor",
}

DEFAULT_THESIS_NAME = "Growth Equity Core"

SECTOR_ATTRACTIVENESS = {
    "Cybersecurity": 9, "Enterprise SaaS": 8, "Healthcare IT": 8,
    "Data & Analytics": 8, "Fintech": 7, "DevOps & Infrastructure": 7,
    "Supply Chain & Logistics": 7, "Climate & Energy Tech": 7,
    "HR Tech": 6, "MarTech & AdTech": 6, "Legal Tech": 6, "PropTech": 5,
}


def _get_secret(key: str) -> str:
    """Read from Streamlit secrets first, then environment."""
    try:
        import streamlit as st
        val = st.secrets.get(key, "")
        if val:
            return str(val)
    except Exception:
        pass
    return os.environ.get(key, "")


OPENAI_API_KEY = _get_secret("OPENAI_API_KEY")
ANTHROPIC_API_KEY = _get_secret("ANTHROPIC_API_KEY")
TAVILY_API_KEY = _get_secret("TAVILY_API_KEY")
DEMO_MODE = not (OPENAI_API_KEY or ANTHROPIC_API_KEY)
