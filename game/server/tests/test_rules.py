from app.game import combat
from app.rules import character as ch
from app.rules import dice, shop, srd
from app.rules.character import RulesError

import pytest


def make(cls="fighter", **kw):
    base = {"name": "Brakka", "race": "dwarf", "subrace": "hill-dwarf", "class": cls, "background": "soldier",
            "ability_method": "standard",
            "abilities": {"STR": 15, "DEX": 13, "CON": 14, "INT": 8, "WIS": 12, "CHA": 10},
            "skills": {"fighter": ["Perception", "Survival"], "rogue": ["Stealth", "Acrobatics", "Perception", "Insight"],
                       "cleric": ["Medicine", "Religion"], "wizard": ["Arcana", "Investigation"]}[cls],
            "equipment_option": {"fighter": "defender", "rogue": "duelist", "cleric": "warpriest", "wizard": "scholar"}[cls]}
    if cls == "cleric":
        base.update(cantrips=["sacred-flame", "guidance", "light"], spells=["healing-word", "guiding-bolt"],
                    abilities={"STR": 13, "DEX": 10, "CON": 14, "INT": 8, "WIS": 15, "CHA": 12})
    if cls == "wizard":
        base.update(cantrips=["fire-bolt", "ray-of-frost", "mage-hand"],
                    spells=["magic-missile", "sleep", "burning-hands", "shield", "mage-armor", "thunderwave"],
                    abilities={"STR": 8, "DEX": 14, "CON": 13, "INT": 15, "WIS": 12, "CHA": 10}, background="sage")
    base.update(kw)
    if base["race"] != "dwarf" and base.get("subrace") == "hill-dwarf":
        base["subrace"] = None
    return base


def setup_module():
    dice.set_seed(1234)


def test_dice():
    r = dice.roll("4d6kh3")
    assert len(r.rolls) == 4 and len(r.kept) == 3 and 3 <= r.total <= 18
    assert dice.roll("2d6+3").modifier == 3
    with pytest.raises(ValueError):
        dice.roll("banana")


def test_fighter_creation():
    s = ch.create(make())
    v = ch.view("c1", "u1", None, s)
    assert v["abilities"]["CON"] == 16  # dwarf +2
    assert v["abilities"]["WIS"] == 13  # hill dwarf +1
    assert v["hp_max"] == 10 + 3 + 1  # d10 + CON 3 + Dwarven Toughness
    assert v["ac"] == 16 + 2 + 1  # chain mail + shield + Defense
    assert any(a["name"] == "Longsword" for a in v["attacks"])
    assert "Athletics" in v["skill_profs"]  # from background


def test_level_three_and_spells():
    s = ch.create(make("wizard", race="elf", subrace="high-elf"), starting_level=3)
    v = ch.view("c2", "u1", None, s)
    assert v["level"] == 3 and v["spellcasting"]["slots"] == {"1": {"max": 4, "used": 0}, "2": {"max": 2, "used": 0}}
    book = v["spellcasting"]["spellbook"]
    assert len(book) == 10  # 6 at level 1 + 2 per level
    assert any(sp["level"] == 2 for sp in book)


def test_bad_creation():
    with pytest.raises(RulesError):
        ch.create(make(abilities={"STR": 18, "DEX": 13, "CON": 14, "INT": 8, "WIS": 12, "CHA": 10}))
    with pytest.raises(RulesError):
        ch.create(make(skills=["Arcana", "Survival"]))


def test_shop_buy_sell():
    s = ch.create(make())
    store = {"type": "general", "sell_rate": 0.5, "stock": shop.generate("general", "town", seed=3)}
    with pytest.raises(RulesError):
        shop.buy(s, store, "potion-of-healing", 1)  # a soldier starts with 10 gp
    s["gold_cp"] = gold = 10000
    shop.buy(s, store, "potion-of-healing", 1)
    assert s["gold_cp"] == gold - 5000
    pot = next(i for i in s["inventory"] if i["key"] == "potion-of-healing")
    shop.sell(s, store, pot["id"], 1)
    with pytest.raises(RulesError):
        shop.buy(s, store, "potion-of-healing", 999)


def test_monster_actions_parse():
    gob = srd.find_monster("goblins")
    acts = srd.monster_actions(gob)
    assert {a["name"] for a in acts} >= {"Scimitar", "Shortbow"}
    assert any(a["ranged"] and a["range"] == 80 for a in acts)


@pytest.mark.parametrize("mode", ["side", "classic"])
def test_auto_fight(mode):
    party = [("a", ch.create(make())), ("b", ch.create(make("wizard", race="elf"))),
             ("c", ch.create(make("cleric", race="human", subrace=None)))]
    chars = dict(party)
    enc, lines = combat.start([("goblin", 3)], "forest", party, mode=mode, seed=9)
    assert lines
    for _ in range(200):
        if combat.check_end(enc, chars):
            break
        for cid in chars:
            tid = f"pc-{cid}"
            if combat.can_act(enc, tid, chars):
                combat.auto_turn(enc, chars, tid, "ai")
                lines += combat.advance(enc, chars)
    assert combat.check_end(enc, chars) in ("victory", "defeat")


def test_spells_in_combat():
    wiz = ch.create(make("wizard", race="elf"))
    chars = {"w": wiz}
    enc, _ = combat.start([("goblin", 2)], "road", [("w", wiz)], mode="side", seed=4)
    tid = "pc-w"
    gob = next(t for t in enc["tokens"].values() if t["kind"] == "monster")
    out = combat.cast(enc, chars, tid, "magic-missile", gob["id"], 1)
    assert any("darts" in l["text"] for l in out)
    with pytest.raises(RulesError):
        combat.cast(enc, chars, tid, "fire-bolt", gob["id"], None)  # action already used
