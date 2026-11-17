"""Backups: a consistent database copy plus art and portraits, without secrets, old ones pruned."""
import sqlite3
import zipfile

from tools import backup


def _data(tmp_path):
    d = tmp_path / "data"
    (d / "art").mkdir(parents=True)
    (d / "portraits").mkdir()
    db = sqlite3.connect(str(d / "game.db"))
    db.execute("pragma journal_mode=wal")
    db.execute("create table games (id text, name text)")
    db.execute("insert into games values ('g1', 'Necropolis')")
    db.commit()  # left open, like the running server (data sits in the WAL)
    (d / "art" / "a.webp").write_bytes(b"art")
    (d / "art" / "b.webp.tmp").write_bytes(b"half-written")
    (d / "portraits" / "p.webp").write_bytes(b"face")
    (d / "secret.key").write_bytes(b"do-not-copy")
    return d, db


def test_backup_zip_contents_and_pruning(tmp_path):
    d, db = _data(tmp_path)
    out1, out2 = tmp_path / "b1", tmp_path / "b2"
    for i in range(3):
        (out1 / f"campfire-2026-01-0{i + 1}-0400.zip").parent.mkdir(exist_ok=True)
        (out1 / f"campfire-2026-01-0{i + 1}-0400.zip").write_bytes(b"old")
    assert backup.main(["--data", str(d), "--dest", str(out1), "--dest", str(out2), "--keep", "2"]) == 0
    db.close()
    zips = sorted(out1.glob("campfire-*.zip"))
    assert len(zips) == 2 and zips[-1].read_bytes()[:2] == b"PK"  # newest kept, oldest pruned
    assert [p.name for p in out2.glob("*.zip")] == [zips[-1].name]
    with zipfile.ZipFile(zips[-1]) as z:
        names = set(z.namelist())
        assert names == {"game.db", "art/a.webp", "portraits/p.webp"}
        (tmp_path / "restore").mkdir()
        z.extract("game.db", tmp_path / "restore")
    got = sqlite3.connect(str(tmp_path / "restore" / "game.db")).execute("select name from games").fetchall()
    assert got == [("Necropolis",)]


def test_with_secrets_is_opt_in(tmp_path):
    d, db = _data(tmp_path)
    assert backup.main(["--data", str(d), "--dest", str(tmp_path / "b"), "--with-secrets"]) == 0
    db.close()
    z = zipfile.ZipFile(next((tmp_path / "b").glob("*.zip")))
    assert "secret.key" in z.namelist()
