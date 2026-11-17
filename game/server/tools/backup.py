"""Back up the game: a consistent copy of the database plus the art and portraits, zipped, with old ones pruned.

    python tools/backup.py --dest C:\\Backups [--dest D:\\More] [--keep 14] [--with-secrets]

The database is copied with SQLite's online backup, so it's safe while the server is running. Secrets (the key that
encrypts saved API keys, the web-push key) are left out unless --with-secrets is given: a lost backup then can't
unlock anyone's API keys. Restoring without them just means players re-enter their keys and re-enable push.

Restore: stop the server, unzip into game/server/data (replacing game.db; delete game.db-wal and game.db-shm), start.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
SECRETS = ("secret.key", "vapid_private.pem")


def make_zip(data: Path, out: Path, with_secrets: bool = False) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    target = out / f"campfire-{stamp}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "game.db"
        src = sqlite3.connect(str(data / "game.db"))
        dst = sqlite3.connect(str(snap))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        out.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(".zip.part")
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "game.db")
            for folder in ("art", "portraits"):
                for f in sorted((data / folder).glob("*")) if (data / folder).exists() else []:
                    if f.is_file() and not f.name.endswith((".tmp", ".part")):
                        z.write(f, f"{folder}/{f.name}")
            if with_secrets:
                for name in SECRETS:
                    if (data / name).exists():
                        z.write(data / name, name)
        partial.replace(target)
    return target


def prune(out: Path, keep: int) -> list[Path]:
    old = sorted(out.glob("campfire-*.zip"))[:-keep] if keep > 0 else []
    for f in old:
        f.unlink(missing_ok=True)
    return old


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", action="append", required=True, help="folder to write the backup to (repeatable)")
    ap.add_argument("--keep", type=int, default=14, help="how many backups to keep in each folder (default 14)")
    ap.add_argument("--data", default=str(DATA), help="the game's data folder")
    ap.add_argument("--with-secrets", action="store_true", help="also include the encryption and push keys")
    a = ap.parse_args(argv)
    data = Path(a.data)
    if not (data / "game.db").exists():
        print(f"no game.db in {data}", file=sys.stderr)
        return 1
    ok = True
    first: Path | None = None
    for d in a.dest:
        out = Path(d)
        try:
            if first is None:
                first = make_zip(data, out, a.with_secrets)
                made = first
            else:  # same snapshot to every destination
                out.mkdir(parents=True, exist_ok=True)
                made = out / first.name
                made.write_bytes(first.read_bytes())
            gone = prune(out, a.keep)
            print(f"backed up to {made} ({made.stat().st_size // 1024} KB); pruned {len(gone)} old")
        except OSError as e:
            ok = False
            print(f"backup to {out} failed: {e}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
