"""M2: all classes to level 5, level-up choices, preparation, AoE, reactions, features, shops, loot."""
import pytest

from app.game import combat
from app.rules import character as ch
from app.rules import dice, loot, shop, srd
from app.rules.character import RulesError
from app.rules.classes import CLASSES
from app.world import battlemap


def setup_module():
    dice.set_seed(77)


def build(cls: str, level: int = 1, **kw) -> dict:
    """Make a valid character of any class using the creator's own options."""
    opts = next(c for c in ch.creator_options()["classes"] if c["index"] == cls)
    skills = [s for s in opts["skill_choices"]["options"] if s not in ("Insight", "Religion")][: opts["skill_choices"]["count"]]
    payload = {"name": f"T-{cls}", "race": "human", "class": cls, "background": "acolyte", "ability_method": "standard",
               "abilities": {"STR": 15, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8},
               "skills": skills, "equipment_option": opts["equipment_options"][0]["id"]}
    prim = CLASSES[cls]["primary"][0]
    order = [prim] + [a for a in ("STR", "DEX", "CON", "INT", "WIS", "CHA") if a != prim]
    payload["abilities"] = dict(zip(order, [15, 14, 13, 12, 10, 8]))
    if opts["fighting_styles"]:
        payload["fighting_style"] = "Defense"
    sc = opts["spellcasting"]
    if sc:
        payload["cantrips"] = [c["index"] for c in sc["cantrips"]][: sc["cantrips_known"]]
        payload["spells"] = [s["index"] for s in sc["spells"]][: sc["spells_at_l1"] or 0]
        if not sc["known"] and sc["prepares"] and cls != "wizard":
            payload["spells"] = [s["index"] for s in sc["spells"]][:2] if sc["spells"] else []
    payload.update(kw)
    return ch.create(payload, starting_level=level)


@pytest.mark.parametrize("cls", list(CLASSES))
def test_every_class_to_level_5(cls):
    s = build(cls, 5)
    v = ch.view("x", "u", None, s)
    assert v["level"] == 5 and v["hp_max"] > 20
    assert v["subclass"]
    assert v["pending_level_up"] is None
    if CLASSES[cls]["spellcasting"]:
        assert v["spellcasting"]["max_spell_level"] >= 1
    if cls in ("fighter", "barbarian", "paladin", "ranger", "monk"):
        assert ch.extra_attacks(s) == 2


def test_level_up_flow_and_asi():
    s = build("fighter", 3)
    assert ch.level_offer(s) is None
    assert ch.award_xp(s, 3000)  # enough for level 4 (and 5 needs 6500)
    offer = ch.level_offer(s)
    assert offer["to_level"] == 4 and offer["asi"]
    with pytest.raises(RulesError):
        ch.level_up(s, {"hp_method": "average"})  # ASI required
    str_before = s["abilities"]["STR"]
    r = ch.level_up(s, {"hp_method": "average", "asi": {"STR": 2}})
    assert r["level"] == 4 and s["abilities"]["STR"] == str_before + 2
    assert ch.level_offer(s) is None  # 3900 XP < 6500


def test_known_caster_level_up_learns_spells():
    s = build("sorcerer", 1)
    ch.award_xp(s, 300)
    offer = ch.level_offer(s)
    assert offer["spells"] == 1 and offer["spell_options"]
    pick = offer["spell_options"][0]["index"]
    ch.level_up(s, {"hp_method": "roll", "spells": [pick]})
    assert pick in s["spells"]["spells"]


def test_prepare_spells():
    s = build("cleric", 3)
    opts = ch.prep_options(s)
    mx = ch.prepared_max(s)
    ch.prepare(s, opts[:mx])
    assert len(s["spells"]["spells"]) == mx
    with pytest.raises(RulesError):
        ch.prepare(s, opts[: mx + 1])
    with pytest.raises(RulesError):
        ch.prepare(build("bard"), [])


def test_half_elf_and_dragonborn():
    h = build("bard", race="half-elf", bonus_abilities=["DEX", "CON"])
    assert h["abilities"]["CHA"] >= 10 and h["bonus_abilities"] == ["DEX", "CON"]
    with pytest.raises(RulesError):
        build("bard", race="half-elf", bonus_abilities=["CHA", "CON"])
    d = build("fighter", race="dragonborn", ancestry="Red")
    assert "fire" in ch.resistances(d)
    assert any(a["id"] == "breath_weapon" for a in ch.actions(d))


def test_unarmored_defense():
    b = build("barbarian")
    for it in b["inventory"]:
        if it["key"] == "shield":
            it["equipped"] = False
    assert ch.armor_class(b) == 10 + ch.mod(b["abilities"]["DEX"]) + ch.mod(b["abilities"]["CON"])
    m = build("monk")
    assert ch.armor_class(m) == 10 + ch.mod(m["abilities"]["DEX"]) + ch.mod(m["abilities"]["WIS"])
    assert any(a["id"] == "unarmed" for a in ch.attacks(m))


def test_area_shapes():
    enc = battlemap.generate("road", 1)
    sphere = combat.area_cells(enc, (2, 6), (10, 6), {"shape": "sphere", "size_ft": 20}, False)
    assert (10, 6) in sphere and (14, 6) in sphere and (15, 6) not in sphere
    cone = combat.area_cells(enc, (2, 6), (10, 6), {"shape": "cone", "size_ft": 15}, True)
    assert (5, 6) in cone and (2, 6) not in cone and (1, 6) not in cone
    line = combat.area_cells(enc, (2, 6), (10, 6), {"shape": "line", "size_ft": 30}, True)
    assert (8, 6) in line and (9, 6) not in line and (5, 7) not in line


def test_fireball_hits_area():
    wiz = build("wizard", 5)
    wiz["spells"]["spellbook"].append("fireball")
    wiz["spells"]["spells"].append("fireball")
    chars = {"w": wiz}
    enc, _ = combat.start([("goblin", 4)], "road", [("w", wiz)], mode="side", seed=3)
    gobs = [t for t in enc["tokens"].values() if t["kind"] == "monster"]
    tx, ty = gobs[0]["x"], gobs[0]["y"]
    # bring the caster within 150 ft if needed
    enc["tokens"]["pc-w"]["x"] = max(0, tx - 10)
    out = combat.cast(enc, chars, "pc-w", "fireball", None, 3, tx, ty)
    assert sum(1 for l in out if "save" in l["text"]) >= 1
    assert wiz["slots_used"].get("3") == 1


def test_extra_attack_and_opportunity_attack():
    f = build("fighter", 5)
    chars = {"f": f}
    enc, _ = combat.start([("goblin", 1)], "road", [("f", f)], mode="side", seed=5)
    t = enc["tokens"]["pc-f"]
    g = next(x for x in enc["tokens"].values() if x["kind"] == "monster")
    t["x"], t["y"] = g["x"] - 1, g["y"]
    if not combat.can_act(enc, "pc-f", chars):
        combat._begin_side(enc, chars, "party")
    melee = next(a for a in ch.attacks(f) if a["kind"] == "melee")
    combat.attack(enc, chars, "pc-f", melee["id"], g["id"])
    if combat.alive(g, chars):
        assert t["budget"]["attacks_left"] == 1
        combat.attack(enc, chars, "pc-f", melee["id"], g["id"])
    with pytest.raises(RulesError):
        combat.attack(enc, chars, "pc-f", melee["id"], g["id"])
    # opportunity attack: a fresh goblin next to a fighter who walks away
    enc2, _ = combat.start([("goblin", 1)], "road", [("f", f)], mode="side", seed=6)
    t2 = enc2["tokens"]["pc-f"]
    g2 = next(x for x in enc2["tokens"].values() if x["kind"] == "monster")
    if not combat.can_act(enc2, "pc-f", chars):
        combat._begin_side(enc2, chars, "party")
    t2["x"], t2["y"] = g2["x"] - 1, g2["y"]
    away = (t2["x"] - 3, t2["y"])
    out = combat.move(enc2, chars, "pc-f", *away) if away in combat.reachable_for(enc2, "pc-f", chars) else []
    if out is not None and away in [(t2["x"], t2["y"])]:
        assert any("opportunity" in l["text"] for l in out)


def test_class_features():
    b = build("barbarian", 2)
    chars = {"b": b}
    enc, _ = combat.start([("goblin", 1)], "road", [("b", b)], mode="side", seed=8)
    if not combat.can_act(enc, "pc-b", chars):
        combat._begin_side(enc, chars, "party")
    combat.feature(enc, chars, "pc-b", "rage")
    assert enc["tokens"]["pc-b"]["raging"]
    with pytest.raises(RulesError):
        combat.feature(enc, chars, "pc-b", "rage")
    combat.feature(enc, chars, "pc-b", "reckless")
    p = build("paladin", 2)
    chars = {"p": p}
    enc, _ = combat.start([("goblin", 1)], "road", [("p", p)], mode="side", seed=9)
    if not combat.can_act(enc, "pc-p", chars):
        combat._begin_side(enc, chars, "party")
    p["hp"] -= 5
    combat.feature(enc, chars, "pc-p", "lay_on_hands", "pc-p")
    assert p["hp"] == p["hp_max"]


def test_multiattack_parse():
    wolf = srd.find_monster("Dire Wolf") or srd.find_monster("Brown Bear")
    bear = srd.find_monster("Brown Bear")
    assert srd.monster_multiattack(bear) == 2
    assert srd.monster_multiattack(srd.find_monster("Goblin")) == 1
    assert wolf


def test_shop_types_services_and_haggle():
    s = build("cleric", 1)
    s["gold_cp"] = 100000
    for t in shop.SHOP_TYPES:
        stock = shop.generate(t, "city", "high")
        assert stock, t
    temple = {"type": "temple", "stock": shop.generate("temple", "town"), "sell_rate": 0.5}
    s["hp"] = 1
    r = shop.buy(s, temple, "svc-heal", 1, "c1")
    assert s["hp"] == s["hp_max"] and r["effect"]
    with pytest.raises(RulesError):
        shop.buy(s, temple, "svc-heal", 1, "c1")  # already full
    h = shop.haggle(s, temple, "c1", "town")
    assert h["discount"] in (-0.2, -0.1, 0.0, 0.1)
    with pytest.raises(RulesError):
        shop.haggle(s, temple, "c1", "town")
    magic = shop.generate("magic", "city", "high")
    assert any(srd.item(e["key"]).get("rarity") == "Uncommon" for e in magic if not e.get("service"))


def test_loot():
    tr = loot.roll_treasure([{"cr": 1, "ctype": "humanoid"}, {"cr": 0.25, "ctype": "humanoid"}], "high")
    assert tr["cp"] > 0
    beasts = loot.roll_treasure([{"cr": 0.25, "ctype": "beast"}], "low")
    assert beasts["cp"] == 0


def test_concentration_breaks():
    c = build("cleric", 1, spells=["bless", "healing-word"])
    chars = {"c": c}
    enc, _ = combat.start([("goblin", 1)], "road", [("c", c)], mode="side", seed=10)
    if not combat.can_act(enc, "pc-c", chars):
        combat._begin_side(enc, chars, "party")
    combat.cast(enc, chars, "pc-c", "bless", "pc-c", 1)
    assert c["concentration"] and "Blessed" in c["conditions"]
    t = enc["tokens"]["pc-c"]
    for _ in range(30):
        combat.apply_damage(enc, chars, t, 3, "slashing")
        if not c["concentration"]:
            break
    assert not c["concentration"] and "Blessed" not in c["conditions"]
