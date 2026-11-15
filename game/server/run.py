"""Start the game server: python run.py  (add --lan to let other devices on your network join)."""
import sys

import uvicorn

from app.config import PORT

if __name__ == "__main__":
    host = "0.0.0.0" if "--lan" in sys.argv else "127.0.0.1"
    uvicorn.run("app.main:app", host=host, port=PORT, reload="--reload" in sys.argv)
