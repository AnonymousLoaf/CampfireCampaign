"""Paths and settings for the game server."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
GAME_DIR = SERVER_DIR.parent
REPO_DIR = GAME_DIR.parent

SKILL_DIR = REPO_DIR / "skills" / "dnd"
SRD_PATH = SKILL_DIR / "data" / "dnd5e_srd.json"
SRD_2024_PATH = SERVER_DIR / "rulesdata" / "dnd5e_srd_2024.json"  # built with skills/dnd/scripts/build_srd.py --ruleset 2024
SKILL_SCRIPTS = SKILL_DIR / "scripts"

DATA_DIR = Path(os.environ.get("GAME_DATA_DIR", SERVER_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = os.environ.get("GAME_DB_URL", f"sqlite:///{(DATA_DIR / 'game.db').as_posix()}")
SECRET_PATH = DATA_DIR / "secret.key"

WEB_DIST = GAME_DIR / "web" / "dist"

PORT = int(os.environ.get("GAME_PORT", "8787"))

# How often the deadline checker runs (seconds).
TICK_SECONDS = float(os.environ.get("GAME_TICK_SECONDS", "5"))

MODELS = [
    {"id": "claude-opus-5-5", "label": "Claude Opus 5.5 (best)"},
    {"id": "claude-sonnet-5-5", "label": "Claude Sonnet 5.5 (cheaper)"},
]
DEFAULT_MODEL = "claude-opus-5-5"


def claude_cli_available() -> bool:
    return shutil.which("claude") is not None
