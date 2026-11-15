"""Every test run gets its own empty data folder (database, keys) — never the real game/server/data."""
import os
import tempfile

os.environ["GAME_DATA_DIR"] = tempfile.mkdtemp(prefix="dndgame-tests-")
os.environ.setdefault("GAME_TICK_SECONDS", "0.2")
