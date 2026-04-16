"""GEO CLI Backend — Configuration."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Directories
DATA_DIR = Path(os.getenv("GEO_DATA_DIR", str(ROOT / "data")))
PROMPTS_DIR = ROOT / "prompts"
ENV_FILE = ROOT / ".env"
DB_PATH = ROOT / "geo_cli.db"

# API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEO_MODEL = os.getenv("GEO_MODEL", "claude-sonnet-4-6")

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
PROMPTS_DIR.mkdir(exist_ok=True)
