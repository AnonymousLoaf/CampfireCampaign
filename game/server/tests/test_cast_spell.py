"""Spells cast outside combat: the slot is spent and the caster rolls the dice."""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.dm.tools import ToolBox, roll_pending
from app.game.state import load
from app.main import app

from .test_chat import _client


def _cleric(c, name):
    opts = c.get("/api/rules/creator?ruleset=2024").json()
    cl = next(x for x in opts["classes"] if x["index"] == "cleric")
    bg = opts["backgrounds"][0]
    race = opts["races"][0]
    sc = cl.get("spellcasting") or {}
    p = {"ruleset": "2024", "name": name, "race": race["index"], "class": "cleric", "background": bg["index"],
         "ability_method": "standard", "abilities": {"STR": 10, "DEX": 12, "CON": 13, "INT": 8, "WIS": 15, "CHA": 14},
         "skills": [s for s in cl["skill_choices"]["options"] if s not in bg["skills"]][:2],
         "equipment_option": cl["equipment_options"][0]["id"],
         "background_asi": {bg["ability_options"][0]: 2, bg["ability_options"][1]: 1},
         "cantrips": [x["index"] for x in sc.get("cantrips", [])][:3],
         "spells": ["cure-wounds"] + [x["index"] for x in sc.get("spells", []) if x["index"] != "cure-wounds"][:3]}
    if race["subraces"]:
        p["subrace"] = race["subraces"][0]["index"]
    r = c.post("/api/characters", json=p)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_cure_wounds_outside_combat_spends_a_slot_and_asks_for_the_roll():
    with TestClient(app):
        host = _client("casthost")
        cid = _cleric(host, "Mira")
        gid = host.post("/api/games", json={"name": "C", "character_id": cid,
                                            "settings": {"ruleset": "2024"}}).json()["id"]
        db = SessionLocal()
        try:
            ctx = load(db, gid)
            s = ctx.chars[cid]
            s["hp"] = 1
            tb = ToolBox(ctx)
            assert tb.call("cast_spell", {"caster": "Mira", "spell": "Fireball"}).startswith("Error")
            out = tb.call("cast_spell", {"caster": "Mira", "spell": "Cure Wounds", "target": "Mira"})
            wis = (s["abilities"]["WIS"] - 10) // 2
            assert out.startswith("Roll requested") and f"2d8{wis:+d}" in out
            assert s["slots_used"] == {"1": 1}
            roll = tb.pending_rolls[0]
            assert roll["dice"] == "2d8" and roll["bonus"] == wis and roll["user_id"]
            roll_pending(ctx, roll)
            res = roll["result"]
            assert 2 + wis <= res["total"] <= 16 + wis and s["hp"] == min(s["hp_max"], 1 + res["total"])
            assert "regains" in res["text"]
            # an NPC target: the amount goes to the DM to describe
            ctx.settings["rolls"] = "auto"
            out = tb.call("cast_spell", {"caster": "Mira", "spell": "cure wounds", "target": "Pim"})
            assert "healing for Pim" in out and s["slots_used"] == {"1": 2}
        finally:
            db.close()
