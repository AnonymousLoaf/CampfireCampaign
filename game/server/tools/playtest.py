"""Automated playtest: two bot players play a short session and the game's rules are checked after every step.

    python tools/playtest.py                       # offline scripted DM: free, ~20 s
    python tools/playtest.py --engine claude_code  # the real Claude Code DM on this PC (uses your Claude plan)
    python tools/playtest.py --rounds 12 --seed 7

It runs on a throwaway data folder (never the real game), registers two players (a cleric and a fighter), starts
a game and plays: exploring, searching (rolls), casting Cure Wounds, shopping, fighting, resting. After every step
it checks:
  - the game view loads and the phase never gets stuck (someone can always act, or the DM is writing);
  - hit points stay within 0..max and spell slots used never exceed what the character has;
  - a leveled spell a player casts spends a slot (catches the DM narrating spells for free);
  - healing comes with dice (catches the DM picking a healing number);
  - every pending roll belongs to someone who can roll it.
It prints a report and exits 1 if any check failed, so it can run on a schedule.
"""
from __future__ import annotations

import argparse
import os
import random
import re
import sys
import tempfile
import time
from pathlib import Path

os.environ["GAME_DATA_DIR"] = tempfile.mkdtemp(prefix="campfire-playtest-")
os.environ.setdefault("GAME_TICK_SECONDS", "0.2")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)

from app.main import app  # noqa: E402

ACTIONS = [
    "I look around carefully and search for anything hidden.",
    "I cast Cure Wounds on {ally}.",
    "We head to the market to buy supplies.",
    "We attack the bandits lurking by the road!",
    "I listen at the door and investigate the strange markings.",
    "We make camp and rest for the night.",
]


class Problems(list):
    casts_checked = 0

    def add(self, step: str, what: str) -> None:
        self.append(f"[{step}] {what}")
        print(f"  ✗ {what}")


def _player(name: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"username": name, "password": "playtest123", "display_name": name.title()})
    r.raise_for_status()
    return c


def _character(c: TestClient, name: str, cls: str) -> str:
    opts = c.get("/api/rules/creator?ruleset=2024").json()
    k = next(x for x in opts["classes"] if x["index"] == cls)
    bg = opts["backgrounds"][0]
    race = opts["races"][0]
    sc = k.get("spellcasting") or {}
    p = {"ruleset": "2024", "name": name, "race": race["index"], "class": cls, "background": bg["index"],
         "ability_method": "standard", "abilities": {"STR": 14, "DEX": 12, "CON": 13, "INT": 8, "WIS": 15, "CHA": 10},
         "skills": [s for s in k["skill_choices"]["options"] if s not in bg["skills"]][:k["skill_choices"].get("choose", 2)],
         "equipment_option": k["equipment_options"][0]["id"], "fighting_style": "Defense",
         "background_asi": {bg["ability_options"][0]: 2, bg["ability_options"][1]: 1}}
    if sc:
        p["cantrips"] = [x["index"] for x in sc.get("cantrips", [])][: sc.get("cantrips_known", 0)]
        spells = [x["index"] for x in sc.get("spells", [])]
        p["spells"] = (["cure-wounds"] if "cure-wounds" in spells else []) + \
            [x for x in spells if x != "cure-wounds"][: max(0, sc.get("spells_at_l1", 0) - 1)]
    if race.get("subraces"):
        p["subrace"] = race["subraces"][0]["index"]
    r = c.post("/api/characters", json=p)
    if r.status_code != 200:
        raise SystemExit(f"couldn't make {name}: {r.text}")
    return r.json()["id"]


def _wait(c: TestClient, gid: str, timeout: float) -> dict:
    """Until the DM has finished writing (or timeout)."""
    t0 = time.time()
    v = c.get(f"/api/games/{gid}/view").json()
    while time.time() - t0 < timeout:
        v = c.get(f"/api/games/{gid}/view").json()
        if v["phase"]["type"] != "dm" and not v["dm"]["busy"]:
            return v
        time.sleep(0.2)
    return v


def check_view(v: dict, step: str, problems: Problems, players: dict[str, TestClient]) -> None:
    p = v["phase"]
    for c in v["characters"].values():
        if not 0 <= c["hp"] <= c["hp_max"]:
            problems.add(step, f"{c['name']} has {c['hp']}/{c['hp_max']} HP")
        sc = c.get("spellcasting") or {}
        for lvl, s in (sc.get("slots") or {}).items():
            if s["used"] > s["max"]:
                problems.add(step, f"{c['name']} used {s['used']} of {s['max']} level-{lvl} slots")
    if p["type"] in ("exploration", "roll", "shop", "combat") and not p["waiting_on"] and not v["dm"]["busy"]:
        problems.add(step, f"stuck: {p['type']} phase is waiting on nobody")
    for r in p.get("pending_rolls") or []:
        if not r.get("result") and r.get("user_id") not in players:
            problems.add(step, f"roll '{r['label']}' belongs to nobody who can roll it")
    if p.get("error"):
        problems.add(step, f"DM error: {p['error']}")


SPELLS = r"\bcast (cure wounds|healing word|bless|magic missile|shield of faith)"


def _slots(v: dict, cid: str) -> tuple[int, int]:
    """(slots used, slots left) for a character."""
    sc = (v["characters"].get(cid) or {}).get("spellcasting") or {}
    slots = (sc.get("slots") or {}).values()
    return sum(s["used"] for s in slots), sum(s["max"] - s["used"] for s in slots)


def watch_spells(before: dict, said: dict[str, str], step: str, pending: list) -> None:
    """Remember casts to check once their rolls are done (in a fight the slot is spent when the player rolls)."""
    for cid, text in said.items():
        m = re.search(SPELLS, text.lower())
        if m:
            used, left = _slots(before, cid)
            if left > 0:
                pending.append({"cid": cid, "spell": m.group(1), "used": used, "step": step,
                                "log_id": before["log"][-1]["id"] if before["log"] else 0})


def settle_spells(after: dict, pending: list, problems: Problems) -> None:
    """Once nothing is waiting on a roll or the DM, every remembered cast must have spent a slot."""
    if after["phase"]["type"] in ("roll", "dm") or after["dm"]["busy"]:
        return
    for c in list(pending):
        used, _ = _slots(after, c["cid"])
        if used <= c["used"]:
            refused = any(l["id"] > c["log_id"] and ("doesn't come" in l["text"] or "can't" in l["text"].lower())
                          for l in after["log"])
            if not refused:
                problems.add(c["step"], f"{after['characters'][c['cid']]['name']} cast {c['spell']} but no spell slot "
                                        f"was spent")
        pending.remove(c)
        problems.casts_checked += 1


def check_spells(before: dict, after: dict, said: dict[str, str], step: str, problems: Problems) -> None:
    """Healing a player character asked for must come with dice."""
    new = [l for l in after["log"] if l["id"] > (before["log"][-1]["id"] if before["log"] else 0)]
    for l in new:
        if re.search(r"regains \d+ HP\.?$", l["text"]) and l["kind"] == "event":
            near = [x for x in new if x["kind"] in ("roll", "combat") and "healing" in x["text"].lower()]
            if not near and any("cure wounds" in t.lower() for t in said.values()):
                problems.add(step, f"healing without dice: '{l['text']}'")


def play(rounds: int, engine: str, seed: int, timeout: float) -> Problems:
    random.seed(seed)
    problems = Problems()
    with TestClient(app):
        a, b = _player("tester_a"), _player("tester_b")
        ca, cb = _character(a, "Mira", "cleric"), _character(b, "Brakka", "fighter")
        me_a, me_b = a.get("/api/me").json()["id"], b.get("/api/me").json()["id"]
        players = {me_a: a, me_b: b}
        g = a.post("/api/games", json={"name": "Playtest", "character_id": ca,
                                       "settings": {"ruleset": "2024", "dm_engine": engine, "rolls": "players",
                                                    "round_timer_minutes": 60}})
        if g.status_code != 200:
            raise SystemExit(f"couldn't create the game: {g.text}")
        gid = g.json()["id"]
        code = a.get(f"/api/games/{gid}/view").json()["game"]["invite_code"]
        b.post("/api/games/join", json={"invite_code": code, "character_id": cb}).raise_for_status()
        a.post(f"/api/games/{gid}/start").raise_for_status()
        v = _wait(a, gid, timeout)
        check_view(v, "opening", problems, players)
        names = {ca: "Mira", cb: "Brakka"}
        pending: list = []
        step_n = 0
        while step_n < rounds * 4:
            step_n += 1
            v = _wait(a, gid, timeout)
            p = v["phase"]
            step = f"step {step_n} ({p['type']})"
            print(step)
            if p["type"] == "dm":
                problems.add(step, f"the DM took over {timeout:.0f}s")
                break
            said: dict[str, str] = {}
            if p["type"] == "exploration":
                act = ACTIONS[(step_n // 1) % len(ACTIONS)]
                for uid, cid, other in ((me_a, ca, "Brakka"), (me_b, cb, "Mira")):
                    if uid in p["waiting_on"]:
                        text = act.format(ally=other) if cid == ca or "cast" not in act else "I keep watch."
                        said[cid] = text
                        r = players[uid].post(f"/api/games/{gid}/action", json={"text": text})
                        if r.status_code != 200:
                            problems.add(step, f"action refused: {r.text[:200]}")
            elif p["type"] == "roll":
                for r in p["pending_rolls"]:
                    if not r.get("result"):
                        res = players[r["user_id"]].post(f"/api/games/{gid}/roll", json={"roll_id": r["id"]})
                        if res.status_code != 200:
                            problems.add(step, f"roll refused: {res.text[:200]}")
            elif p["type"] == "shop":
                for uid in list(p["waiting_on"]):
                    players[uid].post(f"/api/games/{gid}/ready", json={"ready": True})
            elif p["type"] == "combat":
                enc = v.get("encounter") or {}
                actor = next((t for t in enc.get("tokens", []) if t["id"] == (enc.get("turn") or {}).get("actor_id")), None)
                uid = next((u for u in p["waiting_on"]), None)
                if not uid:
                    problems.add(step, "combat with nobody to act")
                    a.post(f"/api/games/{gid}/force-resolve")
                else:
                    text = "I attack the nearest enemy with my weapon." if random.random() < 0.8 else "I take the Dodge action."
                    if actor and actor.get("character_id") == ca and random.random() < 0.3:
                        text = "I cast Cure Wounds on Brakka."
                    if actor and actor.get("character_id"):
                        said[actor["character_id"]] = text
                    r = players[uid].post(f"/api/games/{gid}/action", json={"text": text})
                    if r.status_code != 200:
                        problems.add(step, f"combat action refused: {r.text[:200]}")
            after = _wait(a, gid, timeout)
            check_view(after, step, problems, players)
            if said:
                watch_spells(v, said, step, pending)
                check_spells(v, after, said, step, problems)
            settle_spells(after, pending, problems)
        print(f"\nPlayed {step_n} steps; characters: "
              + ", ".join(f"{names.get(c['id'], c['name'])} {c['hp']}/{c['hp_max']} HP"
                          for c in after["characters"].values()))
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", default="offline", choices=["offline", "claude_code", "api_key"])
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=None, help="seconds to wait for each DM turn")
    a = ap.parse_args(argv)
    timeout = a.timeout or (20 if a.engine == "offline" else 240)
    problems = play(a.rounds, a.engine, a.seed, timeout)
    print()
    print(f"Spell casts checked for a spent slot: {problems.casts_checked}")
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(" -", p)
        return 1
    print("No problems found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
