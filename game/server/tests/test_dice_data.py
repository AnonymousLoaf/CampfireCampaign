"""Hits record each damage die, so the table can throw them (and healing records its dice notation)."""
from app.game import combat


def test_a_hit_records_its_damage_dice(monkeypatch):
    rolls = iter([15])  # the attack's d20: a sure hit against AC 12
    monkeypatch.setattr(combat.dice, "d20", lambda bonus=0, adv="normal": {
        "rolls": [next(rolls, 15)], "natural": 15, "modifier": bonus, "total": 15 + bonus, "advantage": adv,
        "crit": False, "fumble": False})
    enc = {"tokens": {}, "round": 1}
    att = {"id": "m1", "name": "Ogre", "kind": "monster", "x": 0, "y": 0, "hp": 30, "hp_max": 30, "conditions": []}
    tgt = {"id": "m2", "name": "Goblin", "kind": "monster", "x": 1, "y": 0, "hp": 30, "hp_max": 30, "conditions": [],
           "ac": 12}
    enc["tokens"] = {"m1": att, "m2": tgt}
    lines = combat.resolve_attack(enc, {}, att, tgt, name="Greatclub", to_hit=4, dmg="2d8+4", dtype="bludgeoning",
                                  ranged=False, normal=None, weapon=True)
    data = lines[0]["data"]
    assert data["hit"] and len(data["damage_dice"]) == 2
    assert all(d["sides"] == 8 and 1 <= d["value"] <= 8 for d in data["damage_dice"])
