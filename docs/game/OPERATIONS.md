# Running the game: backups and playtests

## Backups

`game/server/tools/backup.py` makes a zip of the game. It holds a consistent copy of the database, taken with
SQLite's online backup, so it is safe while the server runs. It also holds the `art/` and `portraits/` folders.
Old zips are pruned.

```
python tools/backup.py --dest C:\Backups [--dest D:\More] [--keep 14] [--with-secrets]
```

Secrets are left out unless `--with-secrets` is given: `secret.key`, which encrypts saved API keys, and
`vapid_private.pem`, the web-push key. A lost backup then can't unlock anyone's API keys. A restore without
them means players re-enter their Claude/Grok keys and turn push notifications on again.

**Restore:** stop the server and unzip into `game/server/data`, replacing `game.db`. Delete `game.db-wal` and
`game.db-shm`, then start the server.

On the hosting PC, a scheduled task called "Campfire backup" runs this nightly at 4:00 AM. If the PC was off at that
time, it runs at the next chance. The zips go to `C:\Users\<you>\CampfireBackups` and `OneDrive\CampfireBackups`,
14 kept in each, and the log is in `CampfireHost\backup.log`.

## Automated playtests

`game/server/tools/playtest.py` plays a short session with two bot players on a throwaway data folder. It explores,
searches, casts Cure Wounds, shops, fights and rests. After every step it checks the rules:

- the phase never gets stuck;
- HP stays in range;
- spell slots never go over;
- a leveled spell spends a slot;
- healing comes with dice;
- every pending roll belongs to someone.

It exits 1 when a check fails.

```
python tools/playtest.py                       # offline scripted DM: free, ~20 s (also run by the test suite)
python tools/playtest.py --engine claude_code  # the real Claude Code DM on this PC (uses your Claude plan)
```
